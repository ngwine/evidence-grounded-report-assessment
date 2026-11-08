"""Opt-in real Mongo item review: scoped roles, CAS, rollback and private readback.

Only self-authored test bytes and locally generated test identities are used.
No model-quality or independent-gold result is inferred from these tests.
"""

from __future__ import annotations

from copy import deepcopy
import os
import secrets
from uuid import uuid4

from bson import ObjectId
from fastapi.testclient import TestClient
from pymongo import MongoClient
from pymongo.errors import OperationFailure, WriteError
import pytest

from services.backend.src.kltn_ai.api.app import create_app
from services.backend.src.kltn_ai.db.migrations import apply_schema_v1
from services.backend.src.kltn_ai.db.application_schema import apply_schema_v2
from services.backend.src.kltn_ai.db.document_schema import apply_schema_v3
from services.backend.src.kltn_ai.db.analysis_schema import apply_schema_v4
from services.backend.src.kltn_ai.db.annotation_schema import apply_schema_v5
from services.backend.src.kltn_ai.db.roles import provision_roles
from services.backend.src.kltn_ai.domain.item_annotations import ItemAnnotationService
from services.backend.src.kltn_ai.worker.mongo_analysis_worker import MongoAnalysisWorker
from services.backend.tests.test_authenticated_mongo_integration import seed_identity
from services.backend.tests.test_authenticated_documents import component, headers, path
from services.backend.tests.test_mongo_analysis_flow import prepare, create


@pytest.fixture
def live_review(tmp_path):
    uri = os.environ.get("KLTN_MONGO_TEST_URI")
    if not uri:
        pytest.skip("Set KLTN_MONGO_TEST_URI for real-Mongo item review tests")
    name = "kltn_item_review_test_" + uuid4().hex
    with MongoClient(uri, serverSelectionTimeoutMS=3000, timeoutMS=30000, tz_aware=True) as admin:
        db = admin[name]
        clients = []
        try:
            for migrate in (apply_schema_v1, apply_schema_v2, apply_schema_v3, apply_schema_v4, apply_schema_v5):
                first = migrate(db, code_commit="0" * 40, applied_by="synthetic-item-review")
                assert migrate(db, code_commit="0" * 40, applied_by="synthetic-item-review") == first
            actor, workspace, membership, password = seed_identity(db)
            db.workspaces.update_one({"_id": workspace}, {"$set": {"default_purpose": "INTERNAL_TEST"}})
            provision_roles(db)
            host, port = admin.address
            for role in ("api", "worker"):
                secret = secrets.token_urlsafe(24)
                db.command("createUser", "synthetic_" + role, pwd=secret,
                           roles=[{"role": "kltn_" + role, "db": name}])
                clients.append(MongoClient(host=host, port=port, username="synthetic_" + role,
                    password=secret, authSource=name, directConnection=True, tz_aware=True,
                    serverSelectionTimeoutMS=3000, timeoutMS=30000))
            private = tmp_path / "live-item-review-private"
            with TestClient(create_app(clients[0][name], allow_test_client=True, private_root=private)) as client:
                login = client.post("/api/v1/auth/sessions", json={"email": "real-fixture@example.invalid", "password": password},
                                    headers={"Origin": "http://127.0.0.1:5173"})
                assert login.status_code == 200
                ctx = {"db": db, "api_db": clients[0][name], "worker_db": clients[1][name],
                    "client": client, "workspace": workspace, "membership": membership,
                    "identities": {"lecturer": actor}, "private": private, "csrf": login.json()["csrf_token"]}
                prepared = prepare(ctx, transactional=True, worker_db=ctx["worker_db"])
                operation = create(ctx, prepared)
                assert MongoAnalysisWorker(ctx["worker_db"], private).process_one()
                ctx.update(prepared=prepared, run_id=operation["run_id"],
                    base=path(ctx, "analysis-runs/" + operation["run_id"]))
                yield ctx
        finally:
            for client in clients:
                client.close()
            for user in db.command("usersInfo")["users"]:
                db.command("dropUser", user["user"])
            for role in db.command("rolesInfo")["roles"]:
                db.command("dropRole", role["role"])
            admin.drop_database(name)


def _body(item):
    return {"item_id": item["item_id"], "label": "VERBATIM", "quote_or_citation": "NO",
            "evidence_span_ids": [span["span_id"] for span in item["span_options"]],
            "rationale": "Synthetic reviewer checked both exact parser spans."}


def test_real_annotations_are_append_only_versioned_and_not_gold(live_review):
    ctx, db = live_review, live_review["db"]
    client, base = ctx["client"], ctx["base"]
    before = deepcopy(db.analysis_results.find_one({"analysis_run_id": ObjectId(ctx["run_id"])}))
    items = client.get(base + "/annotation-items")
    assert items.status_code == 200, items.text
    component("AnnotationItemPage", items.json())
    pair = next(item for item in items.json()["items"] if item["pipeline"] == "SIMILARITY")
    body = _body(pair)
    request_headers = headers(ctx, "item-review-00000001", f'"rev-{items.json()["run_revision"]}"')
    annotated = client.post(base + "/item-annotations", json=body, headers=request_headers)
    assert annotated.status_code == 201, annotated.text
    component("ItemAnnotation", annotated.json())
    assert client.post(base + "/item-annotations", json=body, headers=request_headers).json() == annotated.json()
    assert db.item_annotations.count_documents({}) == 1
    # A stale distinct write is rejected, while a correction appends a new row.
    corrected_body = {**body, "label": "NONE", "evidence_span_ids": [], "rationale": "Synthetic correction after reviewing context."}
    assert client.post(base + "/item-annotations", json=corrected_body,
                       headers=headers(ctx, "item-review-00000002", request_headers["If-Match"])).status_code == 409
    corrected = client.post(base + "/item-annotations", json=corrected_body,
        headers=headers(ctx, "item-review-00000002", f'"rev-{annotated.json()["run_revision"]}"'))
    assert corrected.status_code == 201, corrected.text
    assert corrected.json()["annotation_revision"] == 2
    history = client.get(base + "/item-annotations")
    component("ItemAnnotationPage", history.json())
    assert len(history.json()["items"]) == 2
    exported = client.get(base + "/item-annotations/export")
    assert exported.status_code == 200 and exported.json()["predictions_visible"] is True
    assert exported.json()["independent_gold"] is exported.json()["official_grade"] is False
    assert db.analysis_results.find_one({"_id": before["_id"]}) == before
    row = db.item_annotations.find_one({})
    with pytest.raises(OperationFailure) as error:
        ctx["api_db"].item_annotations.update_one({"_id": row["_id"]}, {"$set": {"rationale": "forbidden mutation"}})
    assert error.value.code == 13
    for action in (lambda: ctx["worker_db"].item_annotations.find_one({}),
                   lambda: ctx["worker_db"].item_annotations.insert_one(row)):
        with pytest.raises(OperationFailure) as error:
            action()
        assert error.value.code == 13
    # The strict new validator separates the two label vocabularies.
    invalid = {**row, "_id": ObjectId(), "pipeline": "ASSESSMENT", "label": "VERBATIM"}
    with pytest.raises(WriteError) as error:
        db.item_annotations.insert_one(invalid)
    assert error.value.code == 121
    # Already completed review cannot bypass a current rights revocation.
    db.governance_records.update_one({"_id": ctx["prepared"]["source_right"]["_id"]}, {"$set": {"status": "REVOKED"}})
    for suffix in ("/annotation-items", "/item-annotations", "/item-annotations/export"):
        assert client.get(base + suffix).status_code == 409


def test_real_annotation_audit_failure_rolls_back_run_and_append(live_review, monkeypatch):
    from services.backend.src.kltn_ai.domain import item_annotations

    ctx = live_review
    service = ItemAnnotationService(ctx["api_db"], ctx["private"])
    actor, ws = ctx["identities"]["lecturer"], ctx["workspace"]
    page = service.list_items(actor, ws, ctx["run_id"])
    pair = next(item for item in page["items"] if item["pipeline"] == "SIMILARITY")
    before = ctx["db"].analysis_runs.find_one({"_id": ObjectId(ctx["run_id"])})

    def fail_audit(*args, **kwargs):
        raise RuntimeError("Synthetic audit persistence failure")

    with monkeypatch.context() as fault:
        fault.setattr(item_annotations, "append_event", fail_audit)
        with pytest.raises(RuntimeError, match="Synthetic audit"):
            service.create(actor, ws, ctx["run_id"], _body(pair), expected_revision=page["run_revision"],
                           idempotency_key="item-review-00000003", request_id="synthetic-item-review")
    assert ctx["db"].analysis_runs.find_one({"_id": before["_id"]}) == before
    assert ctx["db"].item_annotations.count_documents({}) == 0
    result = service.create(actor, ws, ctx["run_id"], _body(pair), expected_revision=page["run_revision"],
                            idempotency_key="item-review-00000003", request_id="synthetic-item-review")
    assert result["annotation_revision"] == 1
    assert ctx["db"].audit_events.count_documents({"action": "ITEM_ANNOTATION_CREATED"}) == 1
