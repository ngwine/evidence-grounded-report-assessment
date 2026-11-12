"""Private file-backed state for the localhost-only two-pipeline demo.

This is deliberately not the MongoDB model or the reviewed /api/v1 contract.
Only server-generated opaque identifiers become paths. The worker is the sole
writer of job state; review state is stored separately to avoid lost updates.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from typing import Any, Iterator
from uuid import uuid4


REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_ROOT = REPO_ROOT / "var" / "app-local"
RUN_ID_PATTERN = re.compile(r"[0-9a-f]{32}\Z")
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
METHOD_WARNINGS = {
    "bm25-smoke": (
        "BM25-only integration smoke test: Dense, RRF and Cross-Encoder are "
        "disabled. This is not the full proposed method or a validated verdict."
    ),
    "research-v0": (
        "Locked research-v0 retrieval configuration; similarity labels and "
        "rubric outcomes remain uncalibrated proposals requiring human review."
    ),
}
CONFIG_FILES = {
    "bm25-smoke": REPO_ROOT / "services" / "backend" / "configs" / "bm25-smoke.json",
    "research-v0": REPO_ROOT / "research" / "configs" / "core-mvp-v0.json",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_private_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".state-", dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ValueError("Stored JSON must be an object")
    return value


class LocalStore:
    def __init__(self, root: Path | str | None = None) -> None:
        self.root = Path(root or os.environ.get("KLTN_LOCAL_APP_ROOT", DEFAULT_ROOT)).resolve()
        self.runs = self.root / "runs"
        self.approvals = self.root / "source-approvals"
        for directory in (self.root, self.runs, self.approvals):
            # Never chmod an existing broad/user-supplied path such as a repo
            # root. Refuse it if not already private instead.
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            if not directory.is_dir() or stat.S_IMODE(directory.stat().st_mode) & 0o077:
                raise ValueError(f"Local app directory is not private (0700): {directory}")

    def run_dir(self, run_id: str) -> Path:
        if RUN_ID_PATTERN.fullmatch(run_id) is None:
            raise ValueError("Invalid run ID")
        return self.runs / run_id

    def approval_path(self, digest: str) -> Path:
        if SHA256_PATTERN.fullmatch(digest) is None:
            raise ValueError("Invalid SHA-256")
        return self.approvals / f"{digest}.json"

    def approve_source(self, path: Path, *, approver: str, rationale: str) -> dict[str, Any]:
        if not path.is_file():
            raise ValueError("Source must be a regular file")
        if not approver.strip() or not rationale.strip():
            raise ValueError("Approver and rights rationale are required")
        digest = sha256_path(path)
        record = {
            "sha256": digest,
            "status": "LOCAL_PRIVATE_TEST_APPROVED",
            "approver": approver.strip(),
            "rationale": rationale.strip(),
            "approved_at": utc_now(),
            "scope": "private-local-feasibility-only; no publication or dataset redistribution",
        }
        atomic_json(self.approval_path(digest), record)
        return record

    def source_is_approved(self, digest: str) -> bool:
        path = self.approval_path(digest)
        if not path.is_file():
            return False
        try:
            record = read_json(path)
        except (OSError, ValueError, json.JSONDecodeError):
            return False
        return record.get("sha256") == digest and record.get("status") == "LOCAL_PRIVATE_TEST_APPROVED"

    def create_run(
        self,
        *,
        report: tuple[str, bytes],
        sources: list[tuple[str, bytes]],
        rubric: bytes,
        config_id: str,
        report_display_name: str | None = None,
        source_display_names: list[str] | None = None,
    ) -> dict[str, Any]:
        if config_id not in CONFIG_FILES:
            raise ValueError("Unknown config_id")
        run_id = uuid4().hex
        directory = self.run_dir(run_id)
        directory.mkdir(mode=0o700)
        os.chmod(directory, 0o700)
        inputs = directory / "inputs"
        inputs.mkdir(mode=0o700)
        report_name = f"report{report[0]}"
        source_names = [f"source-{index + 1}{suffix}" for index, (suffix, _) in enumerate(sources)]
        write_private_bytes(inputs / report_name, report[1])
        for name, (_, data) in zip(source_names, sources, strict=True):
            write_private_bytes(inputs / name, data)
        write_private_bytes(inputs / "rubric.json", rubric)
        config_data = CONFIG_FILES[config_id].read_bytes()
        write_private_bytes(inputs / "config.json", config_data)
        source_hashes = [sha256_bytes(data) for _, data in sources]
        record: dict[str, Any] = {
            "run_id": run_id,
            "job_id": run_id,
            "status": "QUEUED",
            "config_id": config_id,
            "method_warning": METHOD_WARNINGS[config_id],
            "created_at": utc_now(),
            "updated_at": utc_now(),
            "input_names": {"report": report_name, "sources": source_names},
            "input_display_names": {
                "report": report_display_name or report_name,
                "sources": source_display_names or source_names,
            },
            "input_hashes": {
                "report": sha256_bytes(report[1]),
                "sources": source_hashes,
                "rubric": sha256_bytes(rubric),
                "config": sha256_bytes(config_data),
            },
            "error": None,
        }
        # Queue publication is last: a worker never sees partial inputs.
        atomic_json(directory / "job.json", record)
        return record

    def get_job(self, run_id: str) -> dict[str, Any]:
        return read_json(self.run_dir(run_id) / "job.json")

    def write_job(self, job: dict[str, Any]) -> None:
        job["updated_at"] = utc_now()
        atomic_json(self.run_dir(job["run_id"]) / "job.json", job)

    def pending_jobs(self) -> Iterator[dict[str, Any]]:
        for directory in sorted(self.runs.iterdir()):
            if not directory.is_dir() or RUN_ID_PATTERN.fullmatch(directory.name) is None:
                continue
            path = directory / "job.json"
            if not path.is_file():
                continue
            try:
                job = read_json(path)
            except (OSError, ValueError, json.JSONDecodeError):
                continue
            if job.get("run_id") == directory.name and job.get("status") == "QUEUED":
                yield job

    @contextmanager
    def worker_lock(self) -> Iterator[None]:
        fd = os.open(self.root / "worker.lock", os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    @contextmanager
    def review_lock(self, run_id: str) -> Iterator[None]:
        fd = os.open(self.run_dir(run_id) / "review.lock", os.O_RDWR | os.O_CREAT, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def get_review(self, run_id: str) -> dict[str, Any]:
        path = self.run_dir(run_id) / "review.json"
        if not path.is_file():
            return {"review": None, "revision": 0}
        return read_json(path)

    def write_review(self, run_id: str, record: dict[str, Any]) -> None:
        atomic_json(self.run_dir(run_id) / "review.json", record)
