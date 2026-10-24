"""Prepare only self-authored demo PDFs in the already provisioned local workspace.

No account, real-report permission or dataset approval is created here. Real
PARSE/INDEX/ANALYZE jobs are processed by the running production worker.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

from bson import ObjectId
import fitz

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services.backend.src.kltn_ai.api.runtime import connect_from_private_file  # noqa: E402
from services.backend.src.kltn_ai.domain.analysis import AnalysisService  # noqa: E402
from services.backend.src.kltn_ai.domain.audit import append_event  # noqa: E402
from services.backend.src.kltn_ai.domain.documents import DocumentService  # noqa: E402
from services.backend.src.kltn_ai.domain.indexes import IndexService  # noqa: E402
from services.backend.src.kltn_ai.domain.rubrics import RubricService  # noqa: E402

SHARED = (
    "Evidence-grounded assessment links every judgment to an exact passage in the report. "
    "The system retrieves candidate passages, checks each explicit requirement, and stores "
    "the document version with its evidence. A lecturer reviews the proposed assessment "
    "before accepting any conclusion. Retrieval similarity alone does not establish plagiarism."
)


def pdf(title: str, sections: list[tuple[str, str]]) -> bytes:
    with fitz.open() as doc:
        page = doc.new_page(width=595, height=842)
        page.insert_text((48, 52), "SELF-AUTHORED DEMO / NOT EMPIRICAL RESEARCH", fontsize=8, color=(.4, .5, .5))
        page.insert_textbox(fitz.Rect(48, 85, 548, 155), title, fontsize=22, fontname="hebo")
        top = 175
        for heading, paragraph in sections:
            page.insert_text((48, top), heading, fontsize=12, fontname="hebo")
            remaining = page.insert_textbox(fitz.Rect(48, top + 15, 548, top + 125), paragraph, fontsize=10, lineheight=1.5)
            if remaining < 0:
                raise ValueError("Demo PDF layout exceeded its authored budget")
            top += 155
        return doc.tobytes(no_new_id=True, garbage=4, deflate=True)


def oid(key: str) -> ObjectId:
    return ObjectId(hashlib.sha256(("ui-demo-v1:" + key).encode()).hexdigest()[:24])


def wait_job(database, identifier, timeout=150):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = database.jobs.find_one({"_id": ObjectId(identifier)})
        if job and job["state"] == "SUCCEEDED":
            return
        if job and job["state"] in {"FAILED_FINAL", "CANCELLED"}:
            raise RuntimeError("Demo worker did not finish; inspect safe job error codes")
        time.sleep(.5)
    raise RuntimeError("Demo job is queued; start scripts/run_mongo_worker.py and rerun seeding")


def seed():
    clients = []
    try:
        for role, filename in (("kltn_migration", "migration_app-uri"), ("kltn_api", "api_app-uri")):
            clients.append(connect_from_private_file(ROOT / "var/infra/mongodb" / filename, role=role))
        client, db = clients[0]
        api = clients[1][1]
        actor = db.users.find_one({"email_normalized": "demo@example.invalid", "status": "ACTIVE"})
        ws = db.workspaces.find_one({"workspace_key": "demo-midterm-20261024", "status": "ACTIVE", "default_purpose": "LOCAL_DEMO"})
        if actor is None or ws is None or db.memberships.find_one({"workspace_id": ws["_id"], "user_id": actor["_id"], "status": "ACTIVE", "roles": "LECTURER"}) is None:
            raise ValueError("Existing local demo account and workspace are required")
        actor_id, workspace = actor["_id"], ws["_id"]
        payloads = {
            "report": pdf("Student report: evidence retrieval", [
                ("1. Method", SHARED),
                ("2. Measured benchmark", "The report presents a measured benchmark on a self-authored illustration. Query time and exact source spans are recorded. These statements are fixture content, not actual scientific measurements."),
                ("3. Limitations", "Cross-source verification is not implemented. The current demonstration uses an explicit phrase baseline. The final assessment remains a proposal for lecturer review."),
            ]),
            "source": pdf("Reference note: evidence-grounded assessment", [
                ("1. Evidence-first workflow", SHARED),
                ("2. Review policy", "A valid result must retain its source version and the precise matching passage. Near-verbatim overlap is reported separately from an unverified semantic candidate. Human review is required."),
                ("3. Scope", "This note was authored solely as a local interface demonstration. It is not a publication, dataset sample or student submission."),
            ]),
        }
        documents = DocumentService(api, ROOT / "var/app-mongo")
        versions = {}
        for kind, payload in payloads.items():
            key, gid = "ui-demo-v1-" + kind, oid(kind + "-approval")
            record = db.governance_records.find_one({"_id": gid})
            if record is None:
                now = datetime.now(timezone.utc)
                common = {"schema_version": 1, "created_at": now, "created_by": actor_id, "updated_at": now, "updated_by": actor_id, "revision": 1}
                with client.start_session() as session, session.start_transaction():
                    db.governance_records.insert_one({"_id": gid, **common, "workspace_id": workspace, "resource_type": "DOCUMENT", "resource_id": oid(kind + "-document"), "record_version": 1, "data_owner": {"kind": "SELF_AUTHORED_UI_DEMO"}, "rights_basis": "INTERNAL_APPROVAL", "license_id": None, "rights_evidence": {"scope": "ONLY_SELF_AUTHORED_DEMO_BYTES", "sha256": hashlib.sha256(payload).hexdigest()}, "allowed_purposes": ["LOCAL_DEMO"], "redistribution": "ALLOWED", "data_class": "INTERNAL", "anonymization": {"required": False}, "retention_policy": {}, "approver_id": actor_id, "approved_at": now, "valid_from": None, "valid_until": None, "status": "APPROVED"}, session=session)
                    append_event(db, actor_id=actor_id, workspace_id=workspace, action="SELF_AUTHORED_DEMO_SEEDED", resource_type="GOVERNANCE_RECORD", resource_id=gid, request_id="ui-demo-seed", session=session)
            elif (record.get("rights_evidence", {}).get("sha256") != hashlib.sha256(payload).hexdigest()
                  or record.get("workspace_id") != workspace or record.get("resource_id") != oid(kind + "-document")):
                raise ValueError("Existing demo record differs; no data overwritten")
            operation = documents.upload(actor_id, workspace, kind="REPORT" if kind == "report" else "CORPUS_SOURCE", document_key=key,
                title="[DEMO] Báo cáo: truy xuất bằng chứng" if kind == "report" else "[DEMO] Tài liệu tham khảo: evidence-first",
                filename=kind + "-demo.pdf", payload=payload, idempotency_key="ui-demo-v1-upload-" + kind,
                request_id="ui-demo-seed", governance_record_id=gid, create_only=True)
            wait_job(db, operation["job"]["_id"])
            versions[kind] = {"document_id": str(operation["document"]["_id"]), "document_version_id": str(operation["version"]["_id"])}
        definition = {"max_score": 10, "criteria": [{"criterion_key": "C1", "title": "Phương pháp và kiểm chứng", "weight": 10, "scoring_mode": "PROPORTIONAL_CHECKLIST_V0", "checklists": [
            {"checklist_key": "C1.1", "statement": "Báo cáo trình bày benchmark đo lường", "evidence_mode": "LOCAL", "requirements": [{"requirement_id": "benchmark", "any_of": ["measured benchmark"]}]},
            {"checklist_key": "C1.2", "statement": "Đã hiện thực đối chiếu bằng chứng với nguồn ngoài", "evidence_mode": "LOCAL", "requirements": [{"requirement_id": "cross-source", "any_of": ["cross-source verification is implemented"]}], "contradiction_patterns": ["cross-source verification is not implemented"]},
            {"checklist_key": "C1.3", "statement": "Có kiểm chứng độc lập trên một tập test mới", "evidence_mode": "LOCAL", "requirements": [{"requirement_id": "held-out", "any_of": ["independent held-out evaluation"]}]},
        ]}]}
        rubrics = RubricService(api)
        rubric = rubrics.create(actor_id, workspace, {"rubric_key": "ui-demo-v1-rubric", "title": "[DEMO] Rubric phương pháp và kết quả", "definition": definition}, idempotency_key="ui-demo-v1-rubric-create", request_id="ui-demo-seed")
        version = api.rubric_versions.find_one({"_id": ObjectId(rubric["current_version_id"])})
        if version["definition"] != definition:
            raise ValueError("Existing demo rubric differs; no rubric overwritten")
        if version["status"] == "DRAFT":
            rubrics.publish_version(actor_id, workspace, version["_id"], expected_revision=version["revision"], idempotency_key="ui-demo-v1-rubric-publish", request_id="ui-demo-seed")
        index = IndexService(api, ROOT / "var/app-mongo").request(actor_id, workspace, versions["source"]["document_version_id"], "bm25-smoke", idempotency_key="ui-demo-v1-index", request_id="ui-demo-seed")
        wait_job(db, index["job"]["_id"])
        run = AnalysisService(api, ROOT / "var/app-mongo").create(actor_id, workspace, versions["report"]["document_id"], {"run_type": "BOTH", "report_version_id": versions["report"]["document_version_id"], "source_scope": {"source_version_ids": [versions["source"]["document_version_id"]]}, "rubric_version_id": str(version["_id"]), "config_id": "bm25-smoke"}, idempotency_key="ui-demo-v1-analysis", request_id="ui-demo-seed")
        wait_job(db, run["job"]["_id"])
        result = AnalysisService(api, ROOT / "var/app-mongo").get_result(actor_id, workspace, run["run"]["_id"])
        print(json.dumps({"workspace": ws["name"], "demo_only": True, "analysis_run_id": str(run["run"]["_id"]), "exact_match_coverage": result["similarity"]["exact_match_coverage_percentage"], "checklist_outcomes": result["assessment"]["checklist_outcome_counts"]}, ensure_ascii=False))
    finally:
        for connection, _ in clients:
            connection.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-self-authored-demo", action="store_true", required=True)
    parser.parse_args()
    try:
        seed()
    except Exception:
        raise SystemExit("Demo preparation failed safely; no credentials or document contents displayed. Check exact demo records and worker safe status.") from None
