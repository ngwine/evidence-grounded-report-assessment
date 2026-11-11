"""Dependency-light worker checks against synthetic committed fixtures."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

from services.backend.src.kltn_ai.local_store import LocalStore
from services.backend.src.kltn_ai.worker.local_worker import process_one, recover_interrupted


FIXTURES = Path(__file__).resolve().parents[3] / "research" / "tests" / "fixtures" / "core_mvp"


def test_worker_executes_both_pipelines_with_private_approved_inputs(tmp_path):
    store = LocalStore(tmp_path / "private-app")
    sources = [FIXTURES / "source-overlap.txt", FIXTURES / "source-unrelated.txt"]
    for path in sources:
        store.approve_source(path, approver="fixture-test", rationale="Synthetic public repo fixture")
    job = store.create_run(
        report=(".txt", (FIXTURES / "report.txt").read_bytes()),
        sources=[(".txt", path.read_bytes()) for path in sources],
        rubric=(FIXTURES / "rubric.json").read_bytes(),
        config_id="bm25-smoke",
    )

    # Exercise the actual separate worker process, not just its task function.
    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "services.backend.src.kltn_ai.worker.local_worker",
            "--root",
            str(store.root),
            "--once",
        ],
        cwd=Path(__file__).resolve().parents[3],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    with store.worker_lock():
        assert process_one(store) is False
    result = store.get_job(job["run_id"])
    assert result["status"] == "SUCCEEDED", result["error"]
    output = store.run_dir(job["run_id"]) / "output"
    for name in ("mvp-summary.json", "similarity-report.json", "assessment-report.json", "run-manifest.json"):
        assert (output / name).is_file()
        assert (output / name).stat().st_mode & 0o077 == 0


def test_interrupted_job_is_not_automatically_retried(tmp_path):
    store = LocalStore(tmp_path / "private-app")
    job = store.create_run(
        report=(".txt", b"Report example"),
        sources=[(".txt", b"Different source")],
        rubric=b"{}",
        config_id="bm25-smoke",
    )
    job["status"] = "RUNNING"
    store.write_job(job)
    with store.worker_lock():
        recover_interrupted(store)
        assert process_one(store) is False
    assert store.get_job(job["run_id"])["status"] == "FAILED"
