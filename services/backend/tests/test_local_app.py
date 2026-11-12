"""Synthetic-fixture checks for the localhost app/API/worker integration."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from services.backend.src.kltn_ai.api.local_app import API_PREFIX, create_app
from services.backend.src.kltn_ai.local_store import LocalStore
from services.backend.src.kltn_ai.worker.local_worker import process_one


FIXTURES = Path(__file__).resolve().parents[3] / "research" / "tests" / "fixtures" / "core_mvp"
POST_HEADERS = {"X-KLTN-Local-UI": "1"}


def _upload_files() -> list[tuple[str, tuple[str, bytes, str]]]:
    return [
        ("report", ("report.txt", (FIXTURES / "report.txt").read_bytes(), "text/plain")),
        ("sources", ("source-overlap.txt", (FIXTURES / "source-overlap.txt").read_bytes(), "text/plain")),
        ("sources", ("source-unrelated.txt", (FIXTURES / "source-unrelated.txt").read_bytes(), "text/plain")),
        ("rubric", ("rubric.json", (FIXTURES / "rubric.json").read_bytes(), "application/json")),
    ]


def _approve_fixture_sources(store: LocalStore) -> None:
    for name in ("source-overlap.txt", "source-unrelated.txt"):
        store.approve_source(FIXTURES / name, approver="fixture-test", rationale="Synthetic public repo fixture")


def test_private_local_api_queue_worker_results_and_review(tmp_path):
    app_root = tmp_path / "private-app"
    store = LocalStore(app_root)
    app = create_app(root=app_root, allow_test_client=True)
    with TestClient(app) as client:
        blocked = client.post(f"{API_PREFIX}/runs", files=_upload_files(), headers=POST_HEADERS)
        assert blocked.status_code == 409
        assert "rights approval" in blocked.json()["detail"]
        assert list(store.runs.iterdir()) == []

        _approve_fixture_sources(store)
        created = client.post(
            f"{API_PREFIX}/runs",
            data={"config_id": "bm25-smoke"},
            files=_upload_files(),
            headers=POST_HEADERS,
        )
        assert created.status_code == 202, created.text
        run_id = created.json()["run_id"]
        assert created.json()["status"] == "QUEUED"
        assert "BM25-only" in created.json()["method_warning"]
        queued = client.get(f"{API_PREFIX}/runs/{run_id}")
        assert queued.status_code == 200
        assert queued.json()["summary"] is None

        premature = client.post(
            f"{API_PREFIX}/runs/{run_id}/review",
            json={"decision": "DEFER", "comment": "Wait", "expected_revision": 0, "reviewer_name": "Demo reviewer"},
            headers=POST_HEADERS,
        )
        assert premature.status_code == 409

        with store.worker_lock():
            assert process_one(store) is True
            assert process_one(store) is False
        result = client.get(f"{API_PREFIX}/runs/{run_id}")
        assert result.status_code == 200
        assert result.headers["Cache-Control"] == "no-store"
        body = result.json()
        assert body["status"] == "SUCCEEDED", body["error"]
        assert body["summary"]["pipeline"] == "both"
        assert body["similarity_report"]["matches"]
        assert body["assessment_report"]["checklist_results"]
        assert body["revision"] == 0
        assert body["review"] is None

        reviewed = client.post(
            f"{API_PREFIX}/runs/{run_id}/review",
            json={"decision": "DEFER", "comment": "Needs manual check", "expected_revision": 0, "reviewer_name": "Demo reviewer"},
            headers=POST_HEADERS,
        )
        assert reviewed.status_code == 200
        assert reviewed.json()["revision"] == 1
        assert reviewed.json()["review"]["identity_status"] == "UNVERIFIED_LOCAL_DEMO"
        assert reviewed.json()["review"]["effect"] == "NO_PUBLICATION_OR_OFFICIAL_GRADE"
        stale = client.post(
            f"{API_PREFIX}/runs/{run_id}/review",
            json={"decision": "ACCEPT", "comment": "", "expected_revision": 0, "reviewer_name": "Demo reviewer"},
            headers=POST_HEADERS,
        )
        assert stale.status_code == 409
        assert client.get(f"{API_PREFIX}/runs/{run_id}").json()["review"]["decision"] == "DEFER"


def test_api_rejects_invalid_input_origin_and_revoked_approval(tmp_path):
    app_root = tmp_path / "private-app"
    store = LocalStore(app_root)
    _approve_fixture_sources(store)
    app = create_app(root=app_root, allow_test_client=True)
    with TestClient(app) as client:
        assert client.get(f"{API_PREFIX}/health", headers={"Origin": "https://untrusted.example"}).status_code == 403
        assert client.get(f"{API_PREFIX}/health", headers={"Host": "untrusted.example"}).status_code == 403
        assert client.post(f"{API_PREFIX}/runs", files=_upload_files()).status_code == 403
        invalid = _upload_files()
        invalid[0] = ("report", ("report.pdf", b"not a pdf", "application/pdf"))
        assert client.post(f"{API_PREFIX}/runs", files=invalid, headers=POST_HEADERS).status_code == 422

        created = client.post(f"{API_PREFIX}/runs", files=_upload_files(), headers=POST_HEADERS)
        assert created.status_code == 202
        run_id = created.json()["run_id"]
        source_digest = store.get_job(run_id)["input_hashes"]["sources"][0]
        store.approval_path(source_digest).unlink()
        with store.worker_lock():
            assert process_one(store) is True
        result = client.get(f"{API_PREFIX}/runs/{run_id}").json()
        assert result["status"] == "FAILED"
        assert result["summary"] is None
        assert "approval" in result["error"]


def test_completed_results_are_withheld_after_source_approval_revocation(tmp_path):
    app_root = tmp_path / "private-app"
    store = LocalStore(app_root)
    _approve_fixture_sources(store)
    with TestClient(create_app(root=app_root, allow_test_client=True)) as client:
        created = client.post(f"{API_PREFIX}/runs", files=_upload_files(), headers=POST_HEADERS)
        assert created.status_code == 202
        run_id = created.json()["run_id"]
        with store.worker_lock():
            assert process_one(store) is True
        assert client.get(f"{API_PREFIX}/runs/{run_id}").json()["status"] == "SUCCEEDED"
        source_digest = store.get_job(run_id)["input_hashes"]["sources"][0]
        store.approval_path(source_digest).unlink()
        hidden = client.get(f"{API_PREFIX}/runs/{run_id}").json()
        assert hidden["status"] == "BLOCKED"
        assert hidden["summary"] is None
        assert hidden["similarity_report"] is None
        assert hidden["assessment_report"] is None
        review = client.post(
            f"{API_PREFIX}/runs/{run_id}/review",
            json={"decision": "ACCEPT", "comment": "", "expected_revision": 0, "reviewer_name": "Demo reviewer"},
            headers=POST_HEADERS,
        )
        assert review.status_code == 409


def test_upload_contract_rejects_duplicate_self_comparison_and_bad_payloads(tmp_path):
    app_root = tmp_path / "private-app"
    store = LocalStore(app_root)
    _approve_fixture_sources(store)
    app = create_app(root=app_root, allow_test_client=True)
    with TestClient(app) as client:
        duplicate = _upload_files()
        duplicate[2] = duplicate[1]
        response = client.post(
            f"{API_PREFIX}/runs", files=duplicate, headers=POST_HEADERS
        )
        assert response.status_code == 422
        assert "Duplicate source" in response.json()["detail"]

        self_comparison = _upload_files()
        report_bytes = (FIXTURES / "report.txt").read_bytes()
        self_comparison[1] = (
            "sources",
            ("same-as-report.txt", report_bytes, "text/plain"),
        )
        response = client.post(
            f"{API_PREFIX}/runs", files=self_comparison, headers=POST_HEADERS
        )
        assert response.status_code == 422
        assert "Report cannot" in response.json()["detail"]

        invalid_docx = _upload_files()
        invalid_docx[0] = (
            "report",
            (
                "report.docx",
                b"PK-not-a-docx",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
        )
        assert client.post(
            f"{API_PREFIX}/runs", files=invalid_docx, headers=POST_HEADERS
        ).status_code == 422

        nul_text = _upload_files()
        nul_text[0] = ("report", ("report.txt", b"safe\x00unsafe", "text/plain"))
        assert client.post(
            f"{API_PREFIX}/runs", files=nul_text, headers=POST_HEADERS
        ).status_code == 422

        invalid_rubric = _upload_files()
        invalid_rubric[-1] = (
            "rubric",
            ("rubric.json", b'{"schema_version": 1}', "application/json"),
        )
        assert client.post(
            f"{API_PREFIX}/runs", files=invalid_rubric, headers=POST_HEADERS
        ).status_code == 422

        assert client.post(
            f"{API_PREFIX}/runs",
            data={"config_id": "unknown"},
            files=_upload_files(),
            headers=POST_HEADERS,
        ).status_code == 422


@pytest.mark.parametrize(
    ("report_name", "source_name"),
    [
        ("sample_thesis.pdf", "sample_thesis.docx"),
        ("sample_thesis.docx", "sample_thesis.pdf"),
    ],
)
def test_upload_contract_accepts_committed_synthetic_pdf_and_docx(
    tmp_path, report_name, source_name
):
    fixture_dir = Path(__file__).parent / "fixtures"
    app_root = tmp_path / "private-app"
    store = LocalStore(app_root)
    store.approve_source(
        fixture_dir / source_name,
        approver="fixture-test",
        rationale="Synthetic committed parser fixture",
    )
    files = [
        (
            "report",
            (
                report_name,
                (fixture_dir / report_name).read_bytes(),
                "application/octet-stream",
            ),
        ),
        (
            "sources",
            (
                source_name,
                (fixture_dir / source_name).read_bytes(),
                "application/octet-stream",
            ),
        ),
        (
            "rubric",
            (
                "rubric.json",
                (FIXTURES / "rubric.json").read_bytes(),
                "application/json",
            ),
        ),
    ]
    with TestClient(create_app(root=app_root, allow_test_client=True)) as client:
        created = client.post(
            f"{API_PREFIX}/runs", files=files, headers=POST_HEADERS
        )
        assert created.status_code == 202, created.text
        job = store.get_job(created.json()["run_id"])
        assert job["status"] == "QUEUED"
        assert job["input_display_names"] == {
            "report": report_name,
            "sources": [source_name],
        }
