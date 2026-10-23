"""Product INDEX flow on self-authored text fixtures; no dataset claims."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta

import mongomock
import pytest
from bson import ObjectId

from research.core_mvp.documents import parse_document
from research.offline_retrieval.bm25 import rank_bm25
from services.backend.src.kltn_ai.db.mongo_jobs import MongoJobQueue
from services.backend.src.kltn_ai.domain.documents import DocumentService, _common
from services.backend.src.kltn_ai.domain.errors import DomainError
from services.backend.src.kltn_ai.domain.indexes import IndexService, locked_config
from services.backend.src.kltn_ai.integrations.local_ai.bounded_embeddings import EmbeddingRejected, encode_bounded
from services.backend.src.kltn_ai.worker.mongo_index_worker import MongoIndexWorker
from services.backend.src.kltn_ai.worker.mongo_worker import MongoParseWorker


def _parser(path, **options):
    options.pop("limits", None)
    return parse_document(path, **options)


@pytest.fixture
def state(tmp_path):
    db = mongomock.MongoClient(tz_aware=True).kltn_index_unit
    actor, student, workspace = ObjectId(), ObjectId(), ObjectId()
    for user, role in ((actor, "LECTURER"), (student, "STUDENT")):
        db.users.insert_one({"_id": user, "status": "ACTIVE"})
        db.memberships.insert_one({"_id": ObjectId(), "workspace_id": workspace,
            "user_id": user, "roles": [role], "status": "ACTIVE"})
    db.workspaces.insert_one({"_id": workspace, "status": "ACTIVE", "default_purpose": "INTERNAL_TEST"})
    db.index_heads.create_index([("workspace_id", 1), ("document_version_id", 1), ("config_id", 1)], unique=True)
    db.index_generations.create_index([("workspace_id", 1), ("document_version_id", 1), ("config_id", 1), ("generation_no", 1)], unique=True)
    db.index_operations.create_index([("actor_id", 1), ("workspace_id", 1), ("operation", 1), ("idempotency_key", 1)], unique=True)
    MongoJobQueue(db.jobs).ensure_indexes()
    documents = DocumentService(db, tmp_path / "private", transactional=False)
    right_id, document_id = ObjectId(), ObjectId()
    now = datetime.now(UTC)
    db.governance_records.insert_one({"_id": right_id, **_common(actor, now), "workspace_id": workspace,
        "resource_type": "DOCUMENT", "resource_id": document_id, "status": "APPROVED",
        "rights_basis": "SELF_AUTHORED", "allowed_purposes": ["INTERNAL_TEST"], "approver_id": actor,
        "approved_at": now, "valid_from": None, "valid_until": None, "retention_policy": {}, "anonymization": {},
        "record_version": 1, "data_owner": {"kind": "SYNTHETIC_TEST"}, "license_id": None,
        "rights_evidence": {"kind": "COMMITTED_SYNTHETIC_FIXTURE"}, "redistribution": "ALLOWED", "data_class": "INTERNAL"})
    created = documents.upload(actor, workspace, kind="CORPUS_SOURCE", document_key="synthetic-index-source",
        title="Self-authored indexing fixture", filename="source.txt",
        payload=(b"Evidence provenance retains stable chunk identifiers and exact source spans.\n\n"
                 b"Durable worker leases protect index generation activation from stale retries.\n"),
        governance_record_id=right_id, idempotency_key="upload-unit-one", request_id="index-unit-request")
    parser = MongoParseWorker(db, documents.root, transactional=False, parser=_parser)
    assert parser.process_one()
    service = IndexService(db, documents.root, transactional=False)
    return {"db": db, "actor": actor, "student": student, "workspace": workspace, "created": created,
            "service": service, "right": right_id, "root": documents.root}


def request(state, *, token="index-unit-one", config="bm25-smoke", **options):
    return state["service"].request(state["actor"], state["workspace"], state["created"]["version"]["_id"],
        config, idempotency_key=token, request_id="index-unit-request", **options)


def build(state, **options):
    worker = MongoIndexWorker(state["db"], state["root"], transactional=False, **options)
    assert worker.process_one()
    return worker


def test_actual_bm25_artifact_activation_and_search_match_reference(state):
    records = request(state)
    assert records["generation"]["state"] == "QUEUED"
    build(state)
    snapshot = state["service"].get_active_snapshot(state["actor"], state["workspace"],
        state["created"]["version"]["_id"], "bm25-smoke")
    generation = snapshot["generation"]
    assert generation["state"] == "ACTIVE" and snapshot["vectors"] is None
    assert snapshot["version"]["processing_state"] == "READY"
    artifact = state["service"].artifacts / generation["artifact_key"]
    assert artifact.stat().st_mode & 0o777 == 0o600
    assert hashlib.sha256(artifact.read_bytes()).hexdigest() == generation["artifact_sha256"]
    actual = state["service"].search(state["actor"], state["workspace"], generation["_id"], "stable provenance", top_k=10)
    expected = rank_bm25(snapshot["chunks"], [{"query_id": "q", "text": "stable provenance"}], top_k=10)["q"]
    assert [item["chunk"]["chunk_id"] for item in actual] == [item["chunk_id"] for item in expected]
    assert actual[0]["score"] == pytest.approx(expected[0]["score"])
    assert actual[0]["chunk"]["source_spans"][0]["element_id"]
    assert state["db"].jobs.find_one({"_id": records["job"]["_id"]})["state"] == "SUCCEEDED"


def test_idempotency_reuse_deduplicates_and_rebuild_preserves_immutable_history(state):
    first = request(state)
    assert request(state)["generation"]["_id"] == first["generation"]["_id"]
    assert request(state, token="another-key")["generation"]["_id"] == first["generation"]["_id"]
    with pytest.raises(DomainError) as error:
        request(state, rebuild=True)
    assert error.value.code == "IDEMPOTENCY_CONFLICT"
    build(state)
    prior = state["service"].get_snapshot(state["actor"], state["workspace"], first["generation"]["_id"])
    first_path = state["service"].artifacts / prior["generation"]["artifact_key"]
    original_bytes = first_path.read_bytes()
    second = request(state, token="second-rebuild", rebuild=True)
    assert second["generation"]["generation_no"] == 2
    build(state)
    assert state["db"].index_generations.find_one({"_id": first["generation"]["_id"]})["state"] == "SUPERSEDED"
    assert first_path.read_bytes() == original_bytes
    assert state["service"].get_snapshot(state["actor"], state["workspace"], first["generation"]["_id"])["chunks"] == prior["chunks"]
    with pytest.raises(DomainError) as error:
        state["service"].get_snapshot(state["actor"], state["workspace"], first["generation"]["_id"], allow_superseded=False)
    assert error.value.code == "INDEX_NOT_READY"


def test_out_of_order_rebuild_cannot_activate_old_requested_generation(state):
    first = request(state)
    second = request(state, token="newer-rebuild", rebuild=True)
    build(state)
    assert state["db"].index_generations.find_one({"_id": first["generation"]["_id"]})["state"] == "SUPERSEDED"
    assert state["db"].index_heads.find_one({})["active_generation_id"] is None
    build(state)
    assert state["db"].index_heads.find_one({})["active_generation_id"] == second["generation"]["_id"]


@pytest.mark.parametrize("change", ["approval", "membership", "tombstone", "retention", "chunk"])
def test_snapshot_and_search_recheck_current_gates(state, change):
    generation = request(state)["generation"]
    build(state)
    if change == "approval":
        state["db"].governance_records.update_one({"_id": state["right"]}, {"$set": {"status": "REVOKED"}})
    elif change == "membership":
        state["db"].memberships.update_one({"user_id": state["actor"]}, {"$set": {"status": "DISABLED"}})
    elif change == "tombstone":
        state["db"].tombstones.insert_one({"resource_type": "DOCUMENT_VERSION", "resource_id": state["created"]["version"]["_id"]})
    elif change == "retention":
        state["db"].file_objects.update_one({}, {"$set": {"retention_expires_at": datetime.now(UTC) - timedelta(seconds=1)}})
    else:
        state["db"].chunks.update_one({}, {"$set": {"normalized_text": "tampered"}})
    with pytest.raises(DomainError):
        state["service"].get_snapshot(state["actor"], state["workspace"], generation["_id"])
    with pytest.raises(DomainError):
        state["service"].search(state["actor"], state["workspace"], generation["_id"], "provenance")
    assert (state["service"].artifacts / (str(generation["_id"]) + ".json")).exists()


def test_pending_index_revocation_does_not_load_model_or_publish(state):
    records = request(state, config="research-v0")
    state["db"].governance_records.update_one({"_id": state["right"]}, {"$set": {"status": "REVOKED"}})
    def no_model(*args, **kwargs):
        pytest.fail("Revoked content must not reach an encoder")
    build(state, encoder=no_model)
    generation = state["db"].index_generations.find_one({"_id": records["generation"]["_id"]})
    assert generation["state"] == "REVOKED" and generation["artifact_key"] is None
    assert not list(state["service"].artifacts.iterdir())


def test_missing_dense_model_fails_explicitly_without_silent_bm25_fallback(state):
    records = request(state, config="research-v0")
    def unavailable(*args, **kwargs):
        raise EmbeddingRejected("DENSE_MODEL_UNAVAILABLE")
    build(state, encoder=unavailable)
    generation = state["db"].index_generations.find_one({"_id": records["generation"]["_id"]})
    job = state["db"].jobs.find_one({"_id": records["job"]["_id"]})
    assert generation["state"] == "FAILED" and generation["failure_code"] == "DENSE_MODEL_UNAVAILABLE"
    assert job["state"] == "FAILED_FINAL" and state["db"].index_heads.find_one({})["active_generation_id"] is None
    assert not list(state["service"].artifacts.iterdir())


def test_stale_cancelled_attempt_cannot_activate(state):
    records = request(state)
    worker = MongoIndexWorker(state["db"], state["root"], transactional=False)
    claimed = worker.queue.claim(owner=worker.owner, lease_seconds=300, job_type="INDEX")
    job = worker.queue.start(job_id=claimed["_id"], owner=worker.owner, revision=claimed["revision"])
    generation = worker._begin(job)
    state["db"].jobs.update_one({"_id": job["_id"]}, {"$set": {"state": "CANCELLED"}, "$inc": {"revision": 1}})
    snapshot_version = state["db"].document_versions.find_one({"_id": generation["document_version_id"]})
    chunks = state["service"]._chunks(snapshot_version)
    from services.backend.src.kltn_ai.domain.indexes import build_lexical
    from services.backend.src.kltn_ai.worker.mongo_worker import LeaseLost
    payload = {"schema_version": 1, "generation_id": str(generation["_id"]), "config_sha256": generation["config_sha256"],
        "chunks": chunks, "lexical": build_lexical(chunks), "vectors": None, "model": None}
    key, sha = state["service"].write_artifact(generation["_id"], payload)
    with pytest.raises(LeaseLost):
        worker._persist(job, payload, key, sha)
    assert state["db"].index_heads.find_one({})["active_generation_id"] is None
    assert state["db"].index_generations.find_one({"_id": records["generation"]["_id"]})["state"] == "BUILDING"


def test_artifact_tamper_and_frozen_config_tamper_are_rejected(state):
    records = request(state)
    build(state)
    generation = state["db"].index_generations.find_one({"_id": records["generation"]["_id"]})
    path = state["service"].artifacts / generation["artifact_key"]
    original = path.read_bytes()
    # Test fixture mutation only: the runtime never rewrites an artifact.
    path.write_bytes(b"{}")
    with pytest.raises(DomainError) as error:
        state["service"].get_snapshot(state["actor"], state["workspace"], generation["_id"])
    assert error.value.code == "INDEX_INTEGRITY_FAILED"
    path.write_bytes(original)
    state["db"].index_generations.update_one({"_id": generation["_id"]}, {"$set": {"config.seed": 1}})
    with pytest.raises(DomainError) as error:
        state["service"].get_snapshot(state["actor"], state["workspace"], generation["_id"])
    assert error.value.code == "INDEX_INTEGRITY_FAILED"


def test_student_and_wrong_workspace_cannot_request_index(state):
    with pytest.raises(DomainError) as error:
        state["service"].request(state["student"], state["workspace"], state["created"]["version"]["_id"],
            "bm25-smoke", idempotency_key="student-key", request_id="test-request")
    assert error.value.status == 403
    with pytest.raises(DomainError) as error:
        state["service"].get_active_snapshot(state["actor"], ObjectId(), state["created"]["version"]["_id"], "bm25-smoke")
    assert error.value.status == 404


@pytest.mark.parametrize("texts,options", [([], {}), ([""], {}), (["x"], {"mode": "invalid"}),
    (["x"], {"timeout_seconds": 121}), (["x"] * 5001, {})])
def test_bounded_encoder_rejects_inputs_before_loading_any_model(texts, options):
    config, _ = locked_config("research-v0")
    with pytest.raises(EmbeddingRejected) as error:
        encode_bounded(texts, config["models"]["dense"], **options)
    assert str(error.value) == "DENSE_INPUT_LIMIT"
