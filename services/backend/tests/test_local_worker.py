"""Dependency-light worker checks against synthetic committed fixtures."""

from __future__ import annotations

from pathlib import Path
import json
import subprocess
import sys

from services.backend.src.kltn_ai.local_store import LocalStore
from services.backend.src.kltn_ai.worker.local_worker import process_one, recover_interrupted
from services.backend.src.kltn_ai.worker import local_worker


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


def test_worker_correlation_events_omit_raw_exception_and_input_text(tmp_path, monkeypatch, capsys):
    store = LocalStore(tmp_path / "private-app")
    request_id = "req-" + "a" * 32
    job = store.create_run(
        report=(".txt", b"private student content"),
        sources=[(".txt", b"source content")], rubric=b"{}",
        config_id="bm25-smoke", request_id=request_id,
    )
    def rejected(*_args):
        raise ValueError("PRIVATE_STUDENT_EXCERPT_DO_NOT_LOG")
    monkeypatch.setattr(local_worker, "_run_job", rejected)
    with store.worker_lock():
        assert process_one(store)
    logs = capsys.readouterr().err
    assert "PRIVATE_STUDENT_EXCERPT_DO_NOT_LOG" not in logs
    assert "private student content" not in logs
    events = [json.loads(line) for line in logs.splitlines()]
    assert [event["event"] for event in events] == ["JOB_STARTED", "JOB_FINISHED"]
    assert all(event["request_id"] == request_id and event["run_id"] == job["run_id"]
               for event in events)
    assert events[-1]["error_code"] == "PROCESSING_FAILED"
