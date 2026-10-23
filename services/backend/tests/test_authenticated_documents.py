"""Synthetic HTTP uploads, durable parse results and scoped provenance DTOs."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

import mongomock
import pytest
import yaml
from bson import ObjectId
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from research.core_mvp.documents import parse_document
from services.backend.src.kltn_ai.api.app import PREFIX, create_app
from services.backend.src.kltn_ai.auth.service import AuthService, create_local_user
from services.backend.src.kltn_ai.db.mongo_jobs import MongoJobQueue
from services.backend.src.kltn_ai.domain.documents import MAX_DOCUMENT_BYTES
from services.backend.src.kltn_ai.worker.mongo_worker import MongoParseWorker


ORIGIN = "http://127.0.0.1:5173"
PASSWORD = "synthetic-doc-test-password"
PAYLOAD = ("Evidence grounded assessment records document provenance and exact spans. " * 150
           + "\n\nA separate paragraph describes the measured benchmark and methods.\n").encode()
OPENAPI = Path(__file__).resolve().parents[3] / "docs/api/openapi-v1.yaml"


def component(name, value):
    document = yaml.safe_load(OPENAPI.read_text())
    Draft202012Validator({"components": document["components"],
                           "$ref": "#/components/schemas/" + name}).validate(value)


def in_process_parser(path, **options):
    options.pop("limits", None)
    return parse_document(path, **options)


@pytest.fixture
def context(tmp_path):
    db = mongomock.MongoClient(tz_aware=True).authenticated_documents
    db.users.create_index("email_normalized", unique=True)
    db.auth_credentials.create_index("user_id", unique=True)
    db.auth_sessions.create_index("token_sha256", unique=True)
    db.documents.create_index([("workspace_id", 1), ("kind", 1), ("document_key", 1)], unique=True)
    db.document_versions.create_index([("document_id", 1), ("version_no", 1)], unique=True)
    db.document_operations.create_index([("actor_id", 1), ("workspace_id", 1), ("operation", 1), ("idempotency_key", 1)], unique=True)
    db.document_elements.create_index([("document_version_id", 1), ("generation_key", 1), ("element_key", 1)], unique=True)
    db.chunks.create_index([("document_version_id", 1), ("generation_key", 1), ("chunk_key", 1)], unique=True)
    MongoJobQueue(db.jobs).ensure_indexes()

    def cheap_hash(password):
        return "test-only$" + hashlib.sha256(password.encode()).hexdigest()

    auth = AuthService(db, password_verifier=lambda password, encoded: cheap_hash(password) == encoded)
    identities = {}
    for role in ("lecturer", "student", "other"):
        identities[role] = ObjectId(create_local_user(db, role + "@example.invalid", "Synthetic " + role,
                                                    PASSWORD, password_hasher=cheap_hash)["id"])
    now = datetime.now(timezone.utc)
    workspace = db.workspaces.insert_one({"workspace_key": "synthetic-http-documents", "name": "Synthetic",
        "status": "ACTIVE", "kind": "RESEARCH", "default_purpose": "INTERNAL_TEST"}).inserted_id
    for role, actor_id in identities.items():
        db.memberships.insert_one({"workspace_id": workspace, "user_id": actor_id,
            "roles": ["LECTURER" if role == "lecturer" else "STUDENT"], "status": "ACTIVE",
            "valid_from": None, "valid_until": None, "created_at": now})
    private = tmp_path / "private-app"
    app = create_app(db, allow_test_client=True, auth_service=auth, transaction_mode=False, private_root=private)
    with TestClient(app) as client:
        result = {"db": db, "client": client, "app": app, "private": private,
                  "workspace": workspace, "identities": identities}
        sign_in(result, "lecturer")
        yield result


def sign_in(context, role):
    response = context["client"].post(PREFIX + "/auth/sessions", json={
        "email": role + "@example.invalid", "password": PASSWORD,
    }, headers={"Origin": ORIGIN})
    assert response.status_code == 200
    context["csrf"] = response.json()["csrf_token"]


def headers(context, key="synthetic-upload-0001", revision=None):
    result = {"Origin": ORIGIN, "X-CSRF-Token": context["csrf"], "Idempotency-Key": key}
    if revision:
        result["If-Match"] = revision
    return result


def path(context, suffix):
    return f"{PREFIX}/workspaces/{context['workspace']}/{suffix}"


def approval(context, *, document_id=None, **changes):
    now = datetime.now(timezone.utc)
    record = {"_id": ObjectId(), "workspace_id": context["workspace"],
              "resource_type": "DOCUMENT", "resource_id": document_id or ObjectId(),
              "status": "APPROVED", "rights_basis": "INTERNAL_APPROVAL", "allowed_purposes": ["INTERNAL_TEST"],
              "approver_id": context["identities"]["lecturer"], "approved_at": now,
              "valid_from": None, "valid_until": None, "retention_policy": {}, "anonymization": {},
              "schema_version": 1, "record_version": 1, "created_at": now, "created_by": None,
              "updated_at": now, "updated_by": None, "revision": 1,
              "data_owner": {"kind": "SYNTHETIC_TEST"}, "license_id": None,
              "rights_evidence": {"kind": "COMMITTED_SYNTHETIC_FIXTURE"}, "redistribution": "ALLOWED", "data_class": "INTERNAL"}
    record.update(changes)
    context["db"].governance_records.insert_one(record)
    return record


def upload(context, *, target="reports", document_key="report-one", rights=None, token="synthetic-upload-0001",
           payload=PAYLOAD, filename="report.txt", revision=None, create=True):
    rights = rights or approval(context)
    metadata = {"governance_record_id": str(rights["_id"])}
    if create:
        metadata.update({"document_key": document_key, "title": "Synthetic report"})
    response = context["client"].post(path(context, target), data=metadata,
        files={"file": (filename, payload, "text/plain")}, headers=headers(context, token, revision))
    return response, rights


def assert_error(response, status, code=None):
    assert response.status_code == status, response.text
    value = response.json()["error"]
    if code:
        assert value["code"] == code
    assert value["request_id"] == response.headers["x-request-id"]
    assert "Traceback" not in response.text and PASSWORD not in response.text
    return value


def test_upload_parse_get_dto_exact_spans_job_and_pagination(context):
    response, _ = upload(context)
    assert response.status_code == 202, response.text
    result = response.json()
    assert set(result) == {"document_id", "document_version_id", "job_id", "state"}
    report_url = path(context, "reports/" + result["document_id"])
    version_url = path(context, "document-versions/" + result["document_version_id"])
    job_url = path(context, "jobs/" + result["job_id"])
    report = context["client"].get(report_url)
    assert report.status_code == 200 and report.headers["etag"] == '"rev-1"'
    component("Report", report.json())
    queued = context["client"].get(job_url)
    assert queued.status_code == 200 and queued.json()["state"] == "QUEUED"
    component("Job", queued.json())
    initial = context["client"].get(version_url)
    component("DocumentVersion", initial.json())
    assert initial.json()["processing_state"] == "QUEUED"
    assert_error(context["client"].get(version_url + "/chunks"), 409, "DOCUMENT_NOT_PARSED")
    worker = MongoParseWorker(context["db"], context["private"], parser=in_process_parser, transactional=False)
    assert worker.process_one() is True
    assert worker.process_one() is False
    complete = context["client"].get(job_url)
    assert complete.status_code == 200 and complete.json()["state"] == "SUCCEEDED"
    component("Job", complete.json())
    parsed = context["client"].get(version_url)
    component("DocumentVersion", parsed.json())
    assert parsed.json()["processing_state"] == "PARSED"  # Not a false READY/index claim.
    assert parsed.json()["chunk_count"] > 1
    page = context["client"].get(version_url + "/chunks", params={"limit": 1})
    assert page.status_code == 200
    item = page.json()["items"][0]
    component("Chunk", item)
    assert item["document_version_id"] == result["document_version_id"]
    assert item["raw_text"] and item["normalization_map"] and item["source_spans"]
    assert page.json()["page"]["has_more"] is True
    second = context["client"].get(version_url + "/chunks", params={"limit": 1, "cursor": page.json()["page"]["next_cursor"]})
    assert second.status_code == 200 and second.json()["items"][0]["order"] > item["order"]
    assert "storage_key" not in repr([report.json(), parsed.json(), complete.json(), page.json()])
    assert all(field not in complete.json() for field in ("lease_owner", "lease_expires_at", "config_ref", "correlation_id"))
    assert all(field not in item for field in ("workspace_id", "created_by", "element_ids", "generation_key"))


def test_source_and_report_paths_are_distinct_and_governance_fail_closed(context):
    response, rights = upload(context, target="sources", document_key="source-one")
    assert response.status_code == 202
    identifier = response.json()["document_id"]
    source = context["client"].get(path(context, "sources/" + identifier))
    assert source.status_code == 200 and source.json()["governance_state"] == "APPROVED"
    component("Source", source.json())
    assert_error(context["client"].get(path(context, "reports/" + identifier)), 404)
    wrong_version, _ = upload(context, target="reports/" + identifier + "/versions", rights=rights,
                              create=False, token="wrong-kind-upload-0001", revision='"rev-1"')
    assert_error(wrong_version, 404)
    for target in ("reports", "sources"):
        rejected, _ = upload(context, target=target, document_key="pending-" + target,
                              rights=approval(context, status="PENDING"), token="pending-upload-" + target)
        assert_error(rejected, 409, "GOVERNANCE_NOT_APPROVED")
    assert context["db"].jobs.count_documents({}) == 1


def test_upload_idempotency_new_versions_if_match_and_lineage(context):
    created, rights = upload(context)
    first = created.json()
    replay, _ = upload(context, rights=rights)
    assert replay.status_code == 202 and replay.json() == first
    assert context["db"].file_objects.count_documents({}) == 1
    conflict, _ = upload(context, rights=rights, payload=PAYLOAD + b"changed")
    assert_error(conflict, 409, "IDEMPOTENCY_CONFLICT")
    duplicate_create, _ = upload(context, rights=rights, token="duplicate-create-0001")
    assert_error(duplicate_create, 409, "DOCUMENT_KEY_CONFLICT")
    target = "reports/" + first["document_id"] + "/versions"
    missing, _ = upload(context, target=target, rights=rights, create=False, token="missing-revision-0001")
    assert_error(missing, 428, "PRECONDITION_REQUIRED")
    stale, _ = upload(context, target=target, rights=rights, create=False,
                       token="stale-version-0001", revision='"rev-99"')
    assert_error(stale, 409, "REVISION_CONFLICT")
    second, _ = upload(context, target=target, rights=rights, create=False, payload=PAYLOAD + b"Second version.",
                        token="new-version-0001", revision='"rev-1"')
    assert second.status_code == 202
    assert second.json()["document_id"] == first["document_id"]
    assert second.json()["document_version_id"] != first["document_version_id"]
    row = context["db"].document_versions.find_one({"_id": ObjectId(second.json()["document_version_id"])})
    assert row["version_no"] == 2 and str(row["supersedes_version_id"]) == first["document_version_id"]
    assert context["db"].jobs.count_documents({}) == 2


def test_student_owner_scope_source_denial_job_and_version_hidden_from_other_student(context):
    sign_in(context, "student")
    created, rights = upload(context)
    assert created.status_code == 202
    first = created.json()
    assert context["client"].get(path(context, "reports/" + first["document_id"])).status_code == 200
    denied_source, _ = upload(context, target="sources", document_key="forbidden-source", token="forbidden-source-0001")
    assert_error(denied_source, 403)
    sign_in(context, "other")
    for suffix in ("reports/" + first["document_id"], "document-versions/" + first["document_version_id"],
                   "document-versions/" + first["document_version_id"] + "/chunks", "jobs/" + first["job_id"]):
        assert_error(context["client"].get(path(context, suffix)), 404)
    listing = context["client"].get(path(context, "reports"))
    assert listing.status_code == 200 and listing.json()["items"] == []
    stolen, _ = upload(context, target="reports/" + first["document_id"] + "/versions", rights=rights,
                        create=False, token="steal-version-0001", revision='"rev-1"')
    assert_error(stolen, 404)
    sign_in(context, "lecturer")
    assert context["client"].get(path(context, "reports/" + first["document_id"])).status_code == 200


def test_report_lists_pagination_and_no_cross_workspace_resource_confirmation(context):
    for index in range(3):
        created, _ = upload(context, document_key=f"report-{index}", token=f"create-report-{index}-0001")
        assert created.status_code == 202
    first = context["client"].get(path(context, "reports"), params={"limit": 2})
    assert first.status_code == 200 and len(first.json()["items"]) == 2
    assert first.json()["page"]["has_more"] is True
    second = context["client"].get(path(context, "reports"), params={"limit": 2, "cursor": first.json()["page"]["next_cursor"]})
    assert second.status_code == 200 and len(second.json()["items"]) == 1
    assert second.json()["page"]["has_more"] is False
    assert {item["id"] for item in first.json()["items"]}.isdisjoint({item["id"] for item in second.json()["items"]})
    hidden = context["client"].get(f"{PREFIX}/workspaces/{ObjectId()}/reports")
    assert_error(hidden, 404)
    assert_error(context["client"].get(path(context, "reports"), params={"limit": 101}), 400)
    assert_error(context["client"].get(path(context, "reports"), params={"cursor": "invalid"}), 400)


@pytest.mark.parametrize("missing", ["governance_record_id", "document_key", "title", "file"])
def test_missing_required_upload_fields_rejected_before_file_queue(context, missing):
    rights = approval(context)
    data = {"document_key": "synthetic", "title": "Synthetic", "governance_record_id": str(rights["_id"])}
    data.pop(missing, None)
    files = {"file": ("report.txt", PAYLOAD, "text/plain")} if missing != "file" else {}
    response = context["client"].post(path(context, "reports"), data=data, files=files, headers=headers(context))
    assert_error(response, 422 if files else 415)
    assert context["db"].jobs.count_documents({}) == 0


def test_duplicate_form_field_and_multiple_files_are_rejected(context):
    rights = approval(context)
    repeated = [("document_key", (None, "synthetic")), ("document_key", (None, "duplicate")),
                ("title", (None, "Synthetic")), ("governance_record_id", (None, str(rights["_id"]))),
                ("file", ("report.txt", PAYLOAD, "text/plain"))]
    response = context["client"].post(path(context, "reports"), files=repeated, headers=headers(context))
    assert_error(response, 422)
    repeated.append(("file", ("other.txt", PAYLOAD, "text/plain")))
    response = context["client"].post(path(context, "reports"), files=repeated, headers=headers(context))
    assert response.status_code in {400, 422}
    assert context["db"].jobs.count_documents({}) == 0


def test_upload_csrf_auth_and_body_limit_are_checked_before_queue_and_storage(context):
    rights = approval(context)
    metadata = {"document_key": "synthetic", "title": "Synthetic", "governance_record_id": str(rights["_id"])}
    bad_csrf = context["client"].post(path(context, "reports"), data=metadata,
        files={"file": ("report.txt", PAYLOAD, "text/plain")}, headers={"Origin": ORIGIN})
    assert_error(bad_csrf, 403, "CSRF_INVALID")
    large = context["client"].post(path(context, "reports"), content=b"ignored",
        headers={**headers(context), "Content-Type": "multipart/form-data; boundary=fake",
                 "Content-Length": str(MAX_DOCUMENT_BYTES + 65537)})
    assert_error(large, 413, "PAYLOAD_TOO_LARGE")
    context["client"].cookies.clear()
    unauthenticated = context["client"].post(path(context, "reports"), content=b"ignored",
        headers={"Origin": ORIGIN, "Content-Length": str(MAX_DOCUMENT_BYTES + 65537)})
    assert_error(unauthenticated, 401, "AUTHENTICATION_REQUIRED")
    assert context["db"].jobs.count_documents({}) == 0
    assert not list(context["private"].glob("document-files/*"))


def test_tombstone_and_governance_revocation_hide_chunks_before_retrieval(context):
    created, rights = upload(context)
    result = created.json()
    worker = MongoParseWorker(context["db"], context["private"], parser=in_process_parser, transactional=False)
    assert worker.process_one()
    chunk_path = path(context, "document-versions/" + result["document_version_id"] + "/chunks")
    assert context["client"].get(chunk_path).status_code == 200
    context["db"].governance_records.update_one({"_id": rights["_id"]}, {"$set": {"status": "REVOKED"}})
    assert_error(context["client"].get(chunk_path), 409, "GOVERNANCE_NOT_APPROVED")
    context["db"].tombstones.insert_one({"resource_type": "DOCUMENT", "resource_id": ObjectId(result["document_id"])})
    assert_error(context["client"].get(chunk_path), 404)
