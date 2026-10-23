"""Synthetic document ingestion; no user reports, secrets or dataset approvals."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import mongomock
import pytest
from bson import ObjectId

from research.core_mvp.bounded_documents import parse_document_bounded
from research.core_mvp.documents import parse_document
from services.backend.src.kltn_ai.db.mongo_jobs import MongoJobQueue
from services.backend.src.kltn_ai.domain.documents import DocumentService, _common
from services.backend.src.kltn_ai.domain.errors import DomainError
from services.backend.src.kltn_ai.worker.mongo_worker import MongoParseWorker

PAYLOAD = (b"Evidence-grounded report assessment retains source spans and document versions.\n\n"
           b"A durable queue reclaims expired leases without duplicating a parser generation.\n")


def in_process_parser(path, **options):
    options.pop("limits", None)
    return parse_document(path, **options)


@pytest.fixture
def state(tmp_path):
    db = mongomock.MongoClient(tz_aware=True).kltn
    student, other, lecturer, workspace = ObjectId(), ObjectId(), ObjectId(), ObjectId()
    for user in (student, other, lecturer):
        db.users.insert_one({"_id": user, "status": "ACTIVE"})
    db.workspaces.insert_one({"_id": workspace, "status": "ACTIVE", "default_purpose": "INTERNAL_TEST"})
    for user, role in ((student, "STUDENT"), (other, "STUDENT"), (lecturer, "LECTURER")):
        db.memberships.insert_one({"workspace_id": workspace, "user_id": user,
                                  "roles": [role], "status": "ACTIVE"})
    db.documents.create_index([("workspace_id", 1), ("kind", 1), ("document_key", 1)], unique=True)
    db.document_versions.create_index([("document_id", 1), ("version_no", 1)], unique=True)
    db.document_operations.create_index([("actor_id", 1), ("workspace_id", 1), ("operation", 1), ("idempotency_key", 1)], unique=True)
    db.document_elements.create_index([("document_version_id", 1), ("generation_key", 1), ("element_key", 1)], unique=True)
    db.chunks.create_index([("document_version_id", 1), ("generation_key", 1), ("chunk_key", 1)], unique=True)
    MongoJobQueue(db.jobs).ensure_indexes()
    service = DocumentService(db, tmp_path / "private", transactional=False)
    return db, service, student, other, lecturer, workspace


def approval(db, workspace, *, document_id=None, **changes):
    record = {"_id": ObjectId(), "workspace_id": workspace, "resource_type": "DOCUMENT",
              "resource_id": document_id or ObjectId(), "status": "APPROVED",
              "rights_basis": "INTERNAL_APPROVAL", "allowed_purposes": ["INTERNAL_TEST"],
              "approver_id": ObjectId(), "approved_at": datetime.now(UTC),
              "valid_from": None, "valid_until": None, "retention_policy": {}, "anonymization": {}}
    record.update({**_common(record["approver_id"] or ObjectId(), datetime.now(UTC)), "record_version": 1,
        "data_owner": {"kind": "SYNTHETIC_TEST"}, "license_id": None,
        "rights_evidence": {"kind": "COMMITTED_SYNTHETIC_FIXTURE"}, "redistribution": "ALLOWED",
        "data_class": "INTERNAL"})
    record.update(changes)
    db.governance_records.insert_one(record)
    return record


def upload(state, *, actor=None, kind="REPORT", key="report", token="one", payload=PAYLOAD, rights=None, **changes):
    db, service, student, _, _, workspace = state
    record = rights or approval(db, workspace)
    return service.upload(actor or student, workspace, kind=kind, document_key=key,
        title="Synthetic report", filename="report.txt", payload=payload,
        idempotency_key=token, request_id="fixture-request", governance_record_id=record["_id"], **changes)


def worker(state, parser=in_process_parser, **options):
    db, service, *_ = state
    return MongoParseWorker(db, service.root, transactional=False, parser=parser, **options)


def test_upload_private_immutable_version_and_atomic_metadata_shape(state):
    db, service, student, other, lecturer, workspace = state
    created = upload(state)
    document, version, job = (created[key] for key in ("document", "version", "job"))
    assert document["owner_user_id"] == student
    assert document["current_version_id"] == version["_id"]
    assert version["processing_state"] == "QUEUED"
    assert job["resource_ref"]["version_id"] == version["_id"]
    metadata = db.file_objects.find_one({"_id": version["file_object_id"]})
    stored = service.storage_path(metadata)
    assert stored.name.startswith(str(metadata["_id"]))
    assert stored.read_bytes() == PAYLOAD and stored.stat().st_mode & 0o777 == 0o600
    assert metadata["content_sha256"] == hashlib.sha256(PAYLOAD).hexdigest()
    assert all(not isinstance(value, bytes) for value in metadata.values())
    assert db.audit_events.find_one({})["action"] == "DOCUMENT_UPLOADED"
    assert service.get(lecturer, workspace, document["_id"])["_id"] == document["_id"]
    with pytest.raises(DomainError) as error:
        service.get(other, workspace, document["_id"])
    assert error.value.status == 404
    with pytest.raises(DomainError) as error:
        service.get(student, ObjectId(), document["_id"])
    assert error.value.status == 404


def test_upload_idempotency_body_conflict_and_new_version_lineage(state):
    db, service, student, _, _, workspace = state
    rights = approval(db, workspace)
    first = upload(state, rights=rights)
    again = upload(state, rights=rights)
    assert again["version"]["_id"] == first["version"]["_id"]
    assert db.file_objects.count_documents({}) == db.jobs.count_documents({}) == 1
    with pytest.raises(DomainError) as error:
        upload(state, rights=rights, payload=PAYLOAD + b"changed")
    assert error.value.code == "IDEMPOTENCY_CONFLICT"
    second = upload(state, rights=rights, token="two", payload=PAYLOAD + b"new version")
    assert second["document"]["_id"] == first["document"]["_id"]
    assert second["version"]["version_no"] == 2
    assert second["version"]["supersedes_version_id"] == first["version"]["_id"]
    assert service.get_version(student, workspace, first["document"]["_id"], first["version"]["_id"])["content_sha256"] == hashlib.sha256(PAYLOAD).hexdigest()


def test_create_endpoint_cannot_implicitly_create_version_and_if_match_conflict(state):
    db, *_, workspace = state
    rights = approval(db, workspace)
    first = upload(state, rights=rights, create_only=True)
    assert upload(state, rights=rights, create_only=True)["job"]["_id"] == first["job"]["_id"]
    with pytest.raises(DomainError) as error:
        upload(state, rights=rights, token="new-create", create_only=True)
    assert error.value.code == "DOCUMENT_KEY_CONFLICT"
    with pytest.raises(DomainError) as error:
        upload(state, rights=rights, token="stale", document_id=first["document"]["_id"], expected_revision=99)
    assert error.value.code == "REVISION_CONFLICT"
    second = upload(state, rights=rights, token="next", document_id=first["document"]["_id"],
                    expected_revision=first["document"]["revision"])
    assert second["version"]["version_no"] == 2


@pytest.mark.parametrize("changes", [{"status": "PENDING"}, {"rights_basis": "UNKNOWN"},
    {"approver_id": None}, {"allowed_purposes": ["OTHER"]},
    {"valid_until": datetime.now(UTC) - timedelta(seconds=1)},
    {"anonymization": {"required": True, "status": "PENDING"}}])
def test_governance_fail_closed_before_any_file_or_queue(state, changes):
    db, service, *_, workspace = state
    with pytest.raises(DomainError) as error:
        upload(state, rights=approval(db, workspace, **changes))
    assert error.value.code == "GOVERNANCE_NOT_APPROVED"
    assert db.jobs.count_documents({}) == db.file_objects.count_documents({}) == 0
    assert list(service.files.iterdir()) == []


def test_student_cannot_upload_sources_or_replace_another_students_report(state):
    db, _, _student, other, lecturer, _workspace = state
    with pytest.raises(DomainError) as error:
        upload(state, kind="CORPUS_SOURCE")
    assert error.value.status == 403
    source = upload(state, actor=lecturer, kind="CORPUS_SOURCE", key="source")
    assert source["document"]["kind"] == "CORPUS_SOURCE"
    first = upload(state)
    rights = db.governance_records.find_one({"_id": first["version"]["governance_record_id"]})
    with pytest.raises(DomainError) as error:
        upload(state, actor=other, rights=rights, token="steal")
    assert error.value.status == 404


def test_actual_bounded_parser_worker_persists_bson_provenance_and_does_not_mark_index_ready(state):
    db, service, student, _, _, workspace = state
    created = upload(state)
    assert worker(state, parser=parse_document_bounded).process_one() is True
    job = db.jobs.find_one({"_id": created["job"]["_id"]})
    assert job["state"] == "SUCCEEDED", job
    version = service.get_version(student, workspace, created["document"]["_id"], created["version"]["_id"])
    assert version["processing_state"] == "PARSED" and version["ready_at"] is None
    assert version["chunk_count"] > 0 and version["element_count"] == 2
    chunks = service.get_chunks(student, workspace, created["document"]["_id"], version["_id"])
    assert len(chunks) == version["chunk_count"]
    for chunk in chunks:
        assert chunk["document_version_id"] == version["_id"]
        assert all(isinstance(identity, ObjectId) for identity in chunk["element_ids"])
        for span in chunk["source_spans"]:
            element = db.document_elements.find_one({"_id": span["element_id"]})
            assert element is not None and element["document_version_id"] == version["_id"]
            assert span["stable_element_key"] == element["element_key"]
            assert element["raw_text"][span["element_raw_char_start"]:span["element_raw_char_end"]]
        assert chunk["normalization_map"]
    assert worker(state).process_one() is False


@pytest.mark.parametrize("suffix", ["pdf", "docx"])
def test_pdf_docx_worker_normalizes_legacy_source_refs_for_canonical_storage(state, suffix):
    db, service, student, _, _, workspace = state
    fixture = Path(__file__).resolve().parent / "fixtures" / f"sample_thesis.{suffix}"
    rights = approval(db, workspace)
    uploaded = service.upload(student, workspace, kind="REPORT", document_key="format-alias-regression",
        title="Synthetic canonical locator regression", filename=f"fixture.{suffix}", payload=fixture.read_bytes(),
        idempotency_key="format-one", request_id="format-test", governance_record_id=rights["_id"])
    assert worker(state, parser=parse_document_bounded).process_one() is True
    assert db.jobs.find_one({"_id": uploaded["job"]["_id"]})["state"] == "SUCCEEDED"
    for chunk in db.chunks.find({"document_version_id": uploaded["version"]["_id"]}):
        assert chunk["source_refs"] and all(isinstance(locator, dict) for locator in chunk["source_refs"])
        assert all(locator["source_kind"] == suffix for locator in chunk["source_refs"])
        assert all(isinstance(element, ObjectId) for locator in chunk["source_refs"] for element in locator["source_element_ids"])


@pytest.mark.parametrize("revocation", ["membership", "governance", "tombstone", "tamper"])
def test_worker_rechecks_authority_tombstone_and_content_before_parser(state, revocation):
    db, service, student, _, _, _workspace = state
    created = upload(state)
    if revocation == "membership":
        db.memberships.update_one({"user_id": student}, {"$set": {"status": "REVOKED"}})
    elif revocation == "governance":
        db.governance_records.update_one({"_id": created["version"]["governance_record_id"]}, {"$set": {"status": "REVOKED"}})
    elif revocation == "tombstone":
        db.tombstones.insert_one({"resource_type": "DOCUMENT", "resource_id": created["document"]["_id"]})
    else:
        file = db.file_objects.find_one({"_id": created["version"]["file_object_id"]})
        # Synthetic fixture deliberately modified to reproduce integrity rejection.
        path = service.storage_path(file)
        with path.open("ab") as stream:
            stream.write(b"tampered")
    calls = []
    def parser(*args, **kwargs):
        calls.append(True)
        return in_process_parser(*args, **kwargs)
    assert worker(state, parser=parser).process_one() is True
    assert calls == [] and db.chunks.count_documents({}) == 0
    assert db.jobs.find_one({"_id": created["job"]["_id"]})["state"] == "FAILED_FINAL"


def test_revocation_during_parse_discards_artifacts(state):
    db, *_ = state
    created = upload(state)
    def parser(*args, **options):
        parsed = in_process_parser(*args, **options)
        db.governance_records.update_one({"_id": created["version"]["governance_record_id"]}, {"$set": {"status": "REVOKED"}})
        return parsed
    assert worker(state, parser=parser).process_one() is True
    assert db.chunks.count_documents({}) == db.document_elements.count_documents({}) == 0
    assert db.jobs.find_one({})["error_code"] == "GOVERNANCE_NOT_APPROVED"


def test_stale_worker_cannot_publish_and_recovered_attempt_is_deterministic(state):
    db, *_ = state
    created = upload(state)
    queue = MongoJobQueue(db.jobs)
    def parser(*args, **options):
        parsed = in_process_parser(*args, **options)
        db.jobs.update_one({"_id": created["job"]["_id"]}, {"$set": {
            "lease_expires_at": datetime.now(UTC) - timedelta(seconds=1)}})
        replacement = queue.claim(owner="replacement", lease_seconds=120, job_type="PARSE")
        assert replacement is not None
        return parsed
    assert worker(state, parser=parser).process_one() is True
    assert db.chunks.count_documents({}) == 0
    assert db.jobs.find_one({})["state"] == "CLAIMED"
    db.jobs.update_one({"_id": created["job"]["_id"]}, {"$set": {
        "lease_expires_at": datetime.now(UTC) - timedelta(seconds=1)}})
    assert worker(state, owner="recovery").process_one() is True
    assert db.jobs.find_one({})["state"] == "SUCCEEDED"
    before = [(row["_id"], row["chunk_key"]) for row in db.chunks.find({})]
    # Re-enqueue exactly this immutable version to exercise replay/upsert rather
    # than inventing new sequential chunk IDs on recovery.
    db.jobs.update_one({"_id": created["job"]["_id"]}, {"$set": {"state": "QUEUED", "attempt": 0,
        "available_at": datetime.now(UTC)}, "$inc": {"revision": 1}})
    db.document_versions.update_one({"_id": created["version"]["_id"]}, {"$set": {"processing_state": "QUEUED"}})
    assert worker(state).process_one() is True
    assert [(row["_id"], row["chunk_key"]) for row in db.chunks.find({})] == before


def test_parse_worker_does_not_claim_analysis_jobs(state):
    db, *_ = state
    MongoJobQueue(db.jobs).enqueue(workspace_id=ObjectId(), job_type="ANALYZE",
        resource_ref={"type": "ANALYSIS_RUN", "id": ObjectId(), "version_id": ObjectId()},
        config_ref=None, idempotency_scope="analysis", idempotency_key="one", correlation_id="safe")
    assert worker(state).process_one() is False
    assert db.jobs.find_one({})["state"] == "QUEUED"


def test_exhausted_lease_recovery_updates_version_once_without_parsing(state):
    db, *_ = state
    created = upload(state)
    queue = MongoJobQueue(db.jobs)
    first = queue.claim(owner="dead-worker", job_type="PARSE")
    assert first is not None
    db.jobs.update_one({"_id": created["job"]["_id"]}, {"$set": {"attempt": 3,
        "lease_expires_at": datetime.now(UTC) - timedelta(seconds=1)}})
    db.document_versions.update_one({"_id": created["version"]["_id"]}, {"$set": {"processing_state": "PARSING"}})
    assert worker(state).process_one() is True
    assert db.jobs.find_one({})["state"] == "FAILED_FINAL"
    assert db.document_versions.find_one({})["processing_state"] == "FAILED"
    revision = db.document_versions.find_one({})["revision"]
    assert worker(state).process_one() is False
    assert db.document_versions.find_one({})["revision"] == revision
    assert db.audit_events.count_documents({"reason_code": "LEASE_EXHAUSTED"}) == 1


def test_storage_refuses_broad_or_nonprivate_directory_without_chmod(tmp_path):
    db = mongomock.MongoClient().kltn
    public = tmp_path / "existing-shared"
    public.mkdir(mode=0o755)
    with pytest.raises(ValueError, match="already be private"):
        DocumentService(db, public, transactional=False)
    assert public.stat().st_mode & 0o777 == 0o755
    with pytest.raises(ValueError, match="dedicated"):
        DocumentService(db, Path(__file__).resolve().parents[3], transactional=False)


def test_replayed_upload_with_revoked_governance_is_not_an_authorization_bypass(state):
    db, *_, workspace = state
    rights = approval(db, workspace)
    upload(state, rights=rights)
    db.governance_records.update_one({"_id": rights["_id"]}, {"$set": {"status": "REVOKED"}})
    with pytest.raises(DomainError) as error:
        upload(state, rights=rights)
    assert error.value.code == "GOVERNANCE_NOT_APPROVED"
    assert db.document_versions.count_documents({}) == 1


def test_existing_generation_is_verified_not_silently_accepted(state):
    db, *_ = state
    created = upload(state)
    assert worker(state).process_one() is True
    db.chunks.update_one({}, {"$set": {"normalized_text": "Corrupted persisted chunk"}})
    db.jobs.update_one({"_id": created["job"]["_id"]}, {"$set": {"state": "QUEUED", "attempt": 0,
        "available_at": datetime.now(UTC)}, "$inc": {"revision": 1}})
    db.document_versions.update_one({"_id": created["version"]["_id"]}, {"$set": {"processing_state": "QUEUED"}})
    assert worker(state).process_one() is True
    assert db.jobs.find_one({})["state"] == "FAILED_FINAL"
    assert db.jobs.find_one({})["error_code"] == "PROVENANCE_INVALID"
    assert db.document_versions.find_one({})["processing_state"] == "FAILED"


def test_canonical_parser_identity_stability_and_cross_version_separation(tmp_path):
    source = tmp_path / "synthetic.txt"
    source.write_bytes(PAYLOAD)
    first = parse_document(source, role="report", document_id="document-1", document_version_id="version-1")
    same = parse_document(source, role="report", document_id="document-1", document_version_id="version-1")
    changed = parse_document(source, role="report", document_id="document-1", document_version_id="version-2")
    assert first == same
    assert first.elements[0]["element_key"] != changed.elements[0]["element_key"]
    assert first.chunks[0]["chunk_key"] != changed.chunks[0]["chunk_key"]
    assert first.chunks[0]["source_spans"][0]["document_version_id"] == "version-1"


@pytest.mark.parametrize("invalid", ["", "../secret", "/path", "with spaces", 42, True])
def test_canonical_parser_identity_not_path(tmp_path, invalid):
    source = tmp_path / "synthetic.txt"
    source.write_bytes(PAYLOAD)
    with pytest.raises(ValueError, match="identities"):
        parse_document(source, role="report", document_version_id=invalid)


def test_real_replica_set_document_upload_and_parse_transaction(tmp_path, monkeypatch):
    import os

    from pymongo import MongoClient
    from pymongo.collection import Collection

    from services.backend.src.kltn_ai.db.application_schema import apply_schema_v2
    from services.backend.src.kltn_ai.db.document_schema import apply_schema_v3
    from services.backend.src.kltn_ai.db.migrations import apply_schema_v1

    uri = os.environ.get("KLTN_MONGO_TEST_URI")
    if not uri:
        pytest.skip("Set KLTN_MONGO_TEST_URI for replica-set document flow")
    client = MongoClient(uri, tz_aware=True, serverSelectionTimeoutMS=3000)
    name = "kltn_document_flow_test_" + uuid4().hex
    db = client[name]
    try:
        student, workspace = ObjectId(), ObjectId()
        for migrate in (apply_schema_v1, apply_schema_v2, apply_schema_v3):
            migrate(db, code_commit="a" * 40, applied_by="synthetic-test")
        common = _common(student, datetime.now(UTC))
        db.users.insert_one({"_id": student, **common, "status": "ACTIVE", "email_normalized": "synthetic@example.invalid",
                            "display_name": "Synthetic fixture", "system_roles": [], "auth_subject": None})
        db.workspaces.insert_one({"_id": workspace, **common, "status": "ACTIVE", "default_purpose": "INTERNAL_TEST",
                                 "workspace_key": "synthetic-test", "kind": "RESEARCH", "name": "Synthetic fixture"})
        db.memberships.insert_one({"_id": ObjectId(), **common, "workspace_id": workspace, "user_id": student,
                                   "status": "ACTIVE", "roles": ["STUDENT"], "valid_from": None, "valid_until": None})
        service = DocumentService(db, tmp_path / "mongo-private")
        record = approval(db, workspace)
        first = service.upload(student, workspace, kind="REPORT", document_key="real-transaction",
            title="Synthetic transaction fixture", filename="report.txt", payload=PAYLOAD,
            idempotency_key="one", request_id="live-test", governance_record_id=record["_id"])
        original_update = Collection.update_one
        def fail_during_generation(collection, *args, **options):
            if collection.database.name == name and collection.name == "chunks":
                raise RuntimeError("Synthetic injected failure after elements, before chunks")
            return original_update(collection, *args, **options)
        with monkeypatch.context() as failure:
            failure.setattr(Collection, "update_one", fail_during_generation)
            assert MongoParseWorker(db, service.root).process_one() is True
        assert db.chunks.count_documents({}) == db.document_elements.count_documents({}) == 0
        failed_attempt = db.jobs.find_one({"_id": first["job"]["_id"]})
        assert failed_attempt["state"] == "QUEUED" and failed_attempt["error_code"] == "PARSE_INTERNAL_ERROR"
        assert db.audit_events.count_documents({"action": "DOCUMENT_PARSED"}) == 0
        assert MongoParseWorker(db, service.root).process_one() is True
        assert db.jobs.find_one({"_id": first["job"]["_id"]})["state"] == "SUCCEEDED"
        assert db.document_versions.find_one({"_id": first["version"]["_id"]})["processing_state"] == "PARSED"
        assert db.chunks.count_documents({"document_version_id": first["version"]["_id"]}) > 0
    finally:
        client.drop_database(name)
        client.close()


@pytest.mark.parametrize("suffix", ["pdf", "docx"])
def test_real_replica_set_pdf_docx_schema_provenance_with_bounded_parser(tmp_path, suffix):
    """Exercise actual format-specific fields against strict migration 003."""
    import json
    import os

    from pymongo import MongoClient

    from services.backend.src.kltn_ai.db.application_schema import apply_schema_v2
    from services.backend.src.kltn_ai.db.document_schema import apply_schema_v3
    from services.backend.src.kltn_ai.db.migrations import apply_schema_v1

    uri = os.environ.get("KLTN_MONGO_TEST_URI")
    if not uri:
        pytest.skip("Set KLTN_MONGO_TEST_URI for strict PDF/DOCX ingestion")
    tests_root = Path(__file__).resolve().parent
    manifest = json.loads((tests_root / "golden/parser_chunking_v1/manifest.json").read_text())
    expected = next(item for item in manifest["fixtures"] if item["format"] == suffix)
    fixture = tests_root / expected["path"]
    payload = fixture.read_bytes()
    assert hashlib.sha256(payload).hexdigest() == expected["sha256"]
    client = MongoClient(uri, tz_aware=True, serverSelectionTimeoutMS=3000)
    name = "kltn_format_ingestion_test_" + uuid4().hex
    db = client[name]
    try:
        for migrate in (apply_schema_v1, apply_schema_v2, apply_schema_v3):
            migrate(db, code_commit="a" * 40, applied_by="synthetic-format-test")
        student, workspace = ObjectId(), ObjectId()
        common = _common(student, datetime.now(UTC))
        db.users.insert_one({"_id": student, **common, "status": "ACTIVE", "email_normalized": "format@example.invalid",
            "display_name": "Synthetic format fixture", "system_roles": [], "auth_subject": None})
        db.workspaces.insert_one({"_id": workspace, **common, "status": "ACTIVE", "default_purpose": "INTERNAL_TEST",
            "workspace_key": "synthetic-format-test", "kind": "RESEARCH", "name": "Synthetic fixture"})
        db.memberships.insert_one({"_id": ObjectId(), **common, "workspace_id": workspace, "user_id": student,
            "status": "ACTIVE", "roles": ["STUDENT"], "valid_from": None, "valid_until": None})
        service = DocumentService(db, tmp_path / "private-format-store")
        rights = approval(db, workspace)
        uploaded = service.upload(student, workspace, kind="REPORT", document_key="synthetic-format",
            title="Committed synthetic parser fixture", filename=f"fixture.{suffix}", payload=payload,
            idempotency_key="format-one", request_id="format-fixture", governance_record_id=rights["_id"])
        # No injected parser: the default must spawn the bounded PDF/DOCX child.
        assert MongoParseWorker(db, service.root).process_one() is True
        job = db.jobs.find_one({"_id": uploaded["job"]["_id"]})
        assert job["state"] == "SUCCEEDED", job.get("error_code")
        version = service.get_version(student, workspace, uploaded["document"]["_id"], uploaded["version"]["_id"])
        assert version["processing_state"] == "PARSED" and version["content_sha256"] == expected["sha256"]
        elements = list(db.document_elements.find({"document_version_id": version["_id"]}))
        assert len(elements) == expected["expected"]["element_count"]
        headings = [item for item in elements if item["type"] == "heading"]
        assert headings and all(isinstance(item["level"], int) for item in headings)
        assert all("level" not in item for item in elements if item["type"] == "paragraph")
        if suffix == "docx":
            tables = [item for item in elements if item["type"] == "table"]
            assert len(tables) == 1 and tables[0]["raw_rows"] and tables[0]["rows"]
            assert all(isinstance(item["para_index"], int) for item in elements)
            assert all(item["locator"]["page_index"] is None for item in elements)
        else:
            assert {item["locator"]["page_index"] for item in elements} == {0, 1}
            assert all(isinstance(item["page"], int) and item["locator"]["bbox"] for item in elements)
        chunks = service.get_chunks(student, workspace, uploaded["document"]["_id"], version["_id"])
        assert chunks and all(chunk["element_ids"] for chunk in chunks)
        for chunk in chunks:
            assert chunk["document_version_id"] == version["_id"] and chunk["normalization_map"]
            assert all(isinstance(locator, dict) for locator in chunk["source_refs"])
            assert all(locator["source_element_ids"] for locator in chunk["source_refs"])
            for span in chunk["source_spans"]:
                element = db.document_elements.find_one({"_id": span["element_id"]})
                assert element is not None and element["element_key"] == span["stable_element_key"]
                assert element["locator"]["source_kind"] == suffix
                assert 0 <= span["element_raw_char_start"] < span["element_raw_char_end"] <= len(element["raw_text"])
    finally:
        client.drop_database(name)
        client.close()
