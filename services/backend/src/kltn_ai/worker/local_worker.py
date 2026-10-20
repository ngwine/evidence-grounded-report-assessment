"""Separate, single-owner worker for the private local app queue."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import time
from typing import Any

from research.core_mvp.runner import run_core_mvp
from services.backend.src.kltn_ai.local_store import LocalStore, sha256_path


class InputRejected(RuntimeError):
    """The uploaded bytes or approval state changed before processing."""


def _input_path(directory: Path, filename: str) -> Path:
    if Path(filename).name != filename:
        raise InputRejected("Input filename is not a basename")
    path = directory / "inputs" / filename
    if path.is_symlink() or not path.is_file():
        raise InputRejected("An immutable input is missing")
    return path


def _verify_input(path: Path, expected: str) -> None:
    if sha256_path(path) != expected:
        raise InputRejected("An immutable input changed after upload")


def _run_job(store: LocalStore, job: dict[str, Any]) -> None:
    run_id = job["run_id"]
    directory = store.run_dir(run_id)
    names = job["input_names"]
    hashes = job["input_hashes"]
    report = _input_path(directory, names["report"])
    sources = [_input_path(directory, name) for name in names["sources"]]
    rubric = _input_path(directory, "rubric.json")
    config = _input_path(directory, "config.json")
    if len(sources) != len(hashes["sources"]):
        raise InputRejected("Source inventory changed")
    _verify_input(report, hashes["report"])
    for source, digest in zip(sources, hashes["sources"], strict=True):
        _verify_input(source, digest)
        if not store.source_is_approved(digest):
            raise InputRejected("Comparison source approval is missing or revoked")
    _verify_input(rubric, hashes["rubric"])
    _verify_input(config, hashes["config"])
    run_core_mvp(
        report_path=report,
        source_paths=sources,
        rubric_path=rubric,
        config_path=config,
        output_dir=directory / "output",
        pipeline="both",
    )
    os.chmod(directory / "output", 0o700)
    for filename in ("mvp-summary.json", "similarity-report.json", "assessment-report.json", "run-manifest.json"):
        artifact = directory / "output" / filename
        if not artifact.is_file():
            raise RuntimeError("Core runner did not produce all required artifacts")
        os.chmod(artifact, 0o600)
    # A source may lose approval while a long model run is in progress.
    if not all(store.source_is_approved(digest) for digest in hashes["sources"]):
        raise InputRejected("Comparison source approval was revoked during processing")


def recover_interrupted(store: LocalStore) -> None:
    """Do not silently re-run a job whose previous worker died mid-execution."""

    for directory in sorted(store.runs.iterdir()):
        if not directory.is_dir():
            continue
        try:
            job = store.get_job(directory.name)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if job.get("status") == "RUNNING":
            job["status"] = "FAILED"
            job["error"] = "Worker stopped during this run. Submit a new run; partial output is not published."
            store.write_job(job)


def process_one(store: LocalStore) -> bool:
    """Process one queued run. Caller must hold ``worker_lock``."""

    job = next(store.pending_jobs(), None)
    if job is None:
        return False
    job["status"] = "RUNNING"
    job["started_at"] = datetime.now(timezone.utc).isoformat()
    store.write_job(job)
    try:
        _run_job(store, job)
    except InputRejected as exc:
        job["status"] = "FAILED"
        job["error"] = str(exc)
    except Exception as exc:  # Worker boundary must not leave a RUNNING job forever.
        print(f"Local run {job['run_id']} failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        job["status"] = "FAILED"
        job["error"] = "Processing failed. Inspect the local worker log; no result was published."
    else:
        job["status"] = "SUCCEEDED"
        job["error"] = None
    job["finished_at"] = datetime.now(timezone.utc).isoformat()
    store.write_job(job)
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=None, help="Private local state directory")
    parser.add_argument("--once", action="store_true", help="Process one queued run and exit")
    parser.add_argument("--poll-seconds", type=float, default=1.0)
    args = parser.parse_args(argv)
    if args.poll_seconds < 0.1:
        parser.error("--poll-seconds must be at least 0.1")
    store = LocalStore(args.root)
    try:
        with store.worker_lock():
            recover_interrupted(store)
            while True:
                worked = process_one(store)
                if args.once:
                    break
                if not worked:
                    time.sleep(args.poll_seconds)
    except BlockingIOError:
        print("Another local worker already owns this queue", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
