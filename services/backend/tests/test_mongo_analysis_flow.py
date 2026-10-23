"""Authenticated two-pipeline flow on synthetic bytes, not model-quality data."""

from __future__ import annotations

import os
import secrets

from bson import ObjectId
from fastapi.testclient import TestClient
import pytest

from services.backend.tests.test_authenticated_documents import (
    context as base_context,
    headers,
    upload,
    path,
    sign_in,
)
from services.backend.tests.test_authenticated_app import definition
from services.backend.tests.test_authenticated_documents import component
from services.backend.src.kltn_ai.api.app import create_app
from services.backend.src.kltn_ai.db.analysis_schema import apply_schema_v4
from services.backend.src.kltn_ai.domain.rubrics import RubricService
from services.backend.src.kltn_ai.worker.mongo_analysis_worker import (
    MongoAnalysisWorker,
)
from services.backend.src.kltn_ai.worker.mongo_index_worker import MongoIndexWorker
from services.backend.src.kltn_ai.worker.mongo_worker import MongoParseWorker
from services.backend.src.kltn_ai.worker.bounded_pipeline import (
    CachedDocumentEncoder,
    execute_snapshot,
)

PHRASE = "Measured benchmark evidence retains exact source spans and reproducible version identifiers. "
REPORT = ("# Implementation\n\n" + PHRASE * 8 + "\n\nReport conclusion.").encode()
SOURCE = (
    "# Comparison source\n\n" + PHRASE * 9 + "\n\nSource conclusion differs."
).encode()


@pytest.fixture
def context(tmp_path):
    yield from base_context.__wrapped__(tmp_path)


def prepare(ctx, *, transactional=False, worker_db=None, config_id="bm25-smoke"):
    db, actor, workspace = ctx["db"], ctx["identities"]["lecturer"], ctx["workspace"]
    worker_db = worker_db if worker_db is not None else db
    for collection, keys in (
        (
            "index_heads",
            [("workspace_id", 1), ("document_version_id", 1), ("config_id", 1)],
        ),
        (
            "index_generations",
            [
                ("workspace_id", 1),
                ("document_version_id", 1),
                ("config_id", 1),
                ("generation_no", 1),
            ],
        ),
        (
            "analysis_operations",
            [
                ("actor_id", 1),
                ("workspace_id", 1),
                ("operation", 1),
                ("idempotency_key", 1),
            ],
        ),
        ("analysis_results", [("analysis_run_id", 1)]),
        ("reviews", [("analysis_run_id", 1), ("based_on_revision", 1)]),
    ):
        if not transactional:
            db[collection].create_index(keys, unique=True)
    report, _ = upload(ctx, payload=REPORT, token="report-operation-0001")
    source, right = upload(
        ctx,
        payload=SOURCE,
        target="sources",
        document_key="comparison",
        token="source-operation-0001",
    )
    assert report.status_code == source.status_code == 202, (report.text, source.text)
    parser = MongoParseWorker(worker_db, ctx["private"], transactional=transactional)
    assert parser.process_one() and parser.process_one()
    rid, sid = report.json(), source.json()
    indexed = ctx["client"].post(
        path(
            ctx,
            "document-versions/" + sid["document_version_id"] + "/index-generations",
        ),
        json={"config_id": config_id},
        headers=headers(ctx, "index-operation-0001"),
    )
    assert indexed.status_code == 202, indexed.text
    component("IndexGeneration", indexed.json())
    assert MongoIndexWorker(
        worker_db, ctx["private"], transactional=transactional
    ).process_one()
    rubric = RubricService(db, transaction_mode=transactional).create(
        actor,
        workspace,
        {
            "rubric_key": "analysis-fixture",
            "title": "Synthetic rubric",
            "definition": definition(),
        },
        idempotency_key="rubric-create-0001",
        request_id="synthetic-request",
    )
    RubricService(db, transaction_mode=transactional).publish_version(
        actor,
        workspace,
        rubric["current_version_id"],
        expected_revision=1,
        idempotency_key="rubric-publish-0001",
        request_id="synthetic-request",
    )
    body = {
        "run_type": "BOTH",
        "report_version_id": rid["document_version_id"],
        "source_scope": {"source_version_ids": [sid["document_version_id"]]},
        "rubric_version_id": rubric["current_version_id"],
        "config_id": config_id,
    }
    return {
        "report": rid,
        "source": sid,
        "source_right": right,
        "body": body,
        "url": path(ctx, "reports/" + rid["document_id"] + "/analysis-runs"),
        "index": indexed.json(),
    }


def create(ctx, prepared, token="analysis-operation-0001", body=None):
    response = ctx["client"].post(
        prepared["url"], json=body or prepared["body"], headers=headers(ctx, token)
    )
    assert response.status_code == 202, response.text
    return response.json()


def test_http_both_pipelines_are_persisted_versioned_exported_and_reviewed(context):
    prepared = prepare(context)
    operation = create(context, prepared)
    assert create(context, prepared) == operation
    base = path(context, "analysis-runs/" + operation["run_id"])
    assert context["client"].get(base + "/results").status_code == 409
    assert MongoAnalysisWorker(
        context["db"], context["private"], transactional=False
    ).process_one()
    current = context["client"].get(base)
    assert current.status_code == 200 and current.json()["state"] == "SUCCEEDED", (
        current.text
    )
    component("AnalysisRun", current.json())
    output = context["client"].get(base + "/results")
    assert output.status_code == 200, output.text
    component("RuntimeResults", output.json())
    assert output.json()["similarity"]["exact_match_coverage_percentage"] > 0
    assert (
        output.json()["assessment"]["checklist_results"][0]["checklist_outcome"]
        == "MET"
    )
    assert output.json()["manifest"]["index_generation_ids"] == [
        prepared["index"]["id"]
    ]
    assert output.json()["manifest"]["proposal_only"] is True
    assert output.json()["manifest"]["gold_metrics_available"] is False
    evidence = context["client"].get(base + "/evidence?limit=1")
    assert evidence.status_code == 200 and evidence.json()["items"]
    component("RuntimeEvidencePage", evidence.json())
    assert "has_more" in evidence.json()["page"]
    exported = context["client"].get(base + "/export")
    assert (
        exported.status_code == 200
        and "attachment" in exported.headers["content-disposition"]
    )
    assert exported.json()["results"] == output.json()
    assert "storage_key" not in exported.text and "password" not in exported.text
    review_body = {
        "decision": "ACCEPT",
        "reason_code": "MANUALLY_CHECKED",
        "reason_text": "Synthetic review",
    }
    reviewed = context["client"].post(
        base + "/reviews",
        json=review_body,
        headers=headers(context, revision=current.headers["etag"]),
    )
    assert reviewed.status_code == 201, reviewed.text
    component("RunReview", reviewed.json())
    assert (
        context["client"]
        .post(
            base + "/reviews",
            json=review_body,
            headers=headers(context, revision=current.headers["etag"]),
        )
        .json()
        == reviewed.json()
    )
    assert context["db"].reviews.count_documents({}) == 1
    different = context["client"].post(
        base + "/reviews",
        json={**review_body, "decision": "REJECT"},
        headers=headers(context, revision=current.headers["etag"]),
    )
    assert different.status_code == 409
    assert context["client"].get(base + "/reviews").json()["items"][0][
        "reviewer_id"
    ] == str(context["identities"]["lecturer"])
    assert (
        context["client"].get(prepared["url"]).json()["items"][0]["id"]
        == operation["run_id"]
    )
    assert not MongoAnalysisWorker(
        context["db"], context["private"], transactional=False
    ).process_one()


@pytest.mark.parametrize(
    "change",
    [
        "source_approval",
        "report_tombstone",
        "membership",
        "rubric",
        "element",
        "chunk_span",
    ],
)
def test_authority_and_provenance_changes_block_run_before_execution(context, change):
    prepared = prepare(context)
    operation = create(context, prepared)
    db = context["db"]
    if change == "source_approval":
        db.governance_records.update_one(
            {"_id": prepared["source_right"]["_id"]}, {"$set": {"status": "REVOKED"}}
        )
    elif change == "report_tombstone":
        db.tombstones.insert_one(
            {
                "resource_type": "DOCUMENT_VERSION",
                "resource_id": ObjectId(prepared["report"]["document_version_id"]),
            }
        )
    elif change == "membership":
        db.memberships.update_one(
            {"user_id": context["identities"]["lecturer"]},
            {"$set": {"status": "REVOKED"}},
        )
    elif change == "rubric":
        db.rubric_versions.update_one({}, {"$set": {"definition.max_score": 99}})
    elif change == "element":
        db.document_elements.update_one({}, {"$set": {"raw_text": "tampered"}})
    else:
        db.chunks.update_one(
            {}, {"$set": {"source_spans.0.element_raw_char_end": 999999}}
        )

    def forbidden(*args, **kwargs):
        pytest.fail("Invalid/revoked inputs must not reach inference")

    assert MongoAnalysisWorker(
        db, context["private"], transactional=False, executor=forbidden
    ).process_one()
    assert (
        db.analysis_results.count_documents({})
        == db.evidence_items.count_documents({})
        == 0
    )
    assert (
        db.jobs.find_one({"_id": ObjectId(operation["job_id"])})["state"]
        == "FAILED_FINAL"
    )


def test_post_completion_revocation_blocks_result_export_evidence_and_review(context):
    prepared = prepare(context)
    op = create(context, prepared)
    assert MongoAnalysisWorker(
        context["db"], context["private"], transactional=False
    ).process_one()
    base = path(context, "analysis-runs/" + op["run_id"])
    assert context["client"].get(base + "/results").status_code == 200
    context["db"].governance_records.update_one(
        {"_id": prepared["source_right"]["_id"]}, {"$set": {"status": "REVOKED"}}
    )
    for suffix in ("", "/results", "/evidence", "/export", "/reviews"):
        assert context["client"].get(base + suffix).status_code == 409
    assert (
        context["client"]
        .post(
            base + "/reviews",
            json={"decision": "ACCEPT", "reason_code": "CHECKED"},
            headers=headers(context, revision='"rev-3"'),
        )
        .status_code
        == 409
    )


@pytest.mark.parametrize(
    "collection,mutation",
    [
        ("analysis_results", {"manifest.seed": 0}),
        (
            "evidence_items",
            {"evidence.quote_text": "Modified outside the immutable result"},
        ),
    ],
)
def test_result_and_evidence_integrity_are_checked_before_read_export_or_review(
    context, collection, mutation
):
    prepared = prepare(context)
    op = create(context, prepared)
    assert MongoAnalysisWorker(
        context["db"], context["private"], transactional=False
    ).process_one()
    base = path(context, "analysis-runs/" + op["run_id"])
    context["db"][collection].update_one({}, {"$set": mutation})
    for suffix in ("/results", "/export", "/evidence"):
        response = context["client"].get(base + suffix)
        assert (
            response.status_code == 409
            and response.json()["error"]["code"] == "RESULT_INTEGRITY_FAILED"
        )


def test_stale_worker_and_governance_change_during_inference_never_publish(context):
    prepared = prepare(context)
    create(context, prepared)

    def revoked(snapshot, *, heartbeat):
        output = execute_snapshot(snapshot)
        context["db"].governance_records.update_one(
            {"_id": prepared["source_right"]["_id"]}, {"$set": {"status": "REVOKED"}}
        )
        return output

    assert MongoAnalysisWorker(
        context["db"], context["private"], transactional=False, executor=revoked
    ).process_one()
    assert context["db"].analysis_results.count_documents({}) == 0
    context["db"].governance_records.update_one(
        {"_id": prepared["source_right"]["_id"]}, {"$set": {"status": "APPROVED"}}
    )
    op2 = create(context, prepared, token="analysis-operation-0002")

    def stale(snapshot, *, heartbeat):
        output = execute_snapshot(snapshot)
        context["db"].jobs.update_one(
            {"_id": ObjectId(op2["job_id"])},
            {"$set": {"state": "CANCELLED"}, "$inc": {"revision": 1}},
        )
        return output

    assert MongoAnalysisWorker(
        context["db"], context["private"], transactional=False, executor=stale
    ).process_one()
    assert context["db"].analysis_results.count_documents({}) == 0


def test_pipeline_selection_idempotency_and_student_denial(context):
    prepared = prepare(context)
    op = create(context, prepared)
    changed = {
        **prepared["body"],
        "run_type": "ASSESSMENT",
        "source_scope": {"source_version_ids": []},
    }
    assert (
        context["client"]
        .post(
            prepared["url"],
            json=changed,
            headers=headers(context, "analysis-operation-0001"),
        )
        .status_code
        == 409
    )
    sign_in(context, "student")
    base = path(context, "analysis-runs/" + op["run_id"])
    assert context["client"].get(base).status_code == 403
    assert (
        context["client"]
        .post(prepared["url"], json=prepared["body"], headers=headers(context))
        .status_code
        == 403
    )
    sign_in(context, "lecturer")
    assessment = create(
        context, prepared, token="assessment-00000002", body=changed
    )
    assert MongoAnalysisWorker(
        context["db"], context["private"], transactional=False
    ).process_one()
    assert MongoAnalysisWorker(
        context["db"], context["private"], transactional=False
    ).process_one()
    output = (
        context["client"]
        .get(path(context, "analysis-runs/" + assessment["run_id"] + "/results"))
        .json()
    )
    assert output["similarity"] is None and output["assessment"]


def test_document_prefix_cache_is_used_without_reusing_query_vectors():
    class Encoder:
        metadata = {"model": "TEST_DOUBLE_ONLY"}

        def set_mode(self, mode):
            self.mode = mode

        def encode(self, texts):
            return [[len(text), 1] for text in texts]

    encoder = CachedDocumentEncoder(Encoder(), {"same": [0.5, 0.5]})
    encoder.set_mode("document")
    assert encoder.encode(["same", "new"]) == [[0.5, 0.5], [3, 1]]
    assert encoder.reused == 1
    encoder.set_mode("query")
    assert encoder.encode(["same"]) == [[4, 1]]


@pytest.mark.parametrize("config_id", ["bm25-smoke", "research-v0"])
def test_real_mongo_two_pipeline_runtime_roles_and_transaction_rollback(
    tmp_path, monkeypatch, config_id
):
    from uuid import uuid4
    from pymongo import MongoClient
    from pymongo.collection import Collection
    from services.backend.src.kltn_ai.db.migrations import apply_schema_v1
    from services.backend.src.kltn_ai.db.application_schema import apply_schema_v2
    from services.backend.src.kltn_ai.db.document_schema import apply_schema_v3
    from services.backend.src.kltn_ai.db.roles import provision_roles
    from services.backend.tests.test_authenticated_mongo_integration import (
        seed_identity,
    )

    uri = os.environ.get("KLTN_MONGO_TEST_URI")
    if not uri:
        pytest.skip("Dedicated replica-set URI required")
    if config_id == "research-v0" and os.environ.get("KLTN_TEST_LOCAL_MODELS") != "1":
        pytest.skip("Opt-in cached real-model smoke; never download models in CI")
    admin = MongoClient(
        uri, serverSelectionTimeoutMS=3000, timeoutMS=30000, tz_aware=True
    )
    name = "kltn_analysis_flow_test_" + uuid4().hex
    db = admin[name]
    clients = []
    try:
        for migrate in (
            apply_schema_v1,
            apply_schema_v2,
            apply_schema_v3,
            apply_schema_v4,
        ):
            migrate(db, code_commit="a" * 40, applied_by="synthetic-flow-test")
        actor, workspace, _, password = seed_identity(db)
        provision_roles(db)
        for role in ("api", "worker"):
            user, secret = "synthetic_" + role, secrets.token_urlsafe(24)
            db.command(
                "createUser",
                user,
                pwd=secret,
                roles=[{"role": "kltn_" + role, "db": name}],
            )
            host, port = admin.address
            clients.append(
                MongoClient(
                    host=host,
                    port=port,
                    username=user,
                    password=secret,
                    authSource=name,
                    directConnection=True,
                    tz_aware=True,
                    serverSelectionTimeoutMS=3000,
                    timeoutMS=30000,
                )
            )
        app = create_app(
            clients[0][name],
            allow_test_client=True,
            private_root=tmp_path / "live-private",
        )
        with TestClient(app) as client:
            login = client.post(
                "/api/v1/auth/sessions",
                json={"email": "real-fixture@example.invalid", "password": password},
                headers={"Origin": "http://127.0.0.1:5173"},
            )
            assert login.status_code == 200
            ctx = {
                "db": db,
                "client": client,
                "identities": {"lecturer": actor},
                "workspace": workspace,
                "private": tmp_path / "live-private",
                "csrf": login.json()["csrf_token"],
            }
            # The generated governance fixtures name the exact purpose in this workspace.
            db.workspaces.update_one(
                {"_id": workspace}, {"$set": {"default_purpose": "INTERNAL_TEST"}}
            )
            prepared = prepare(
                ctx, transactional=True, worker_db=clients[1][name], config_id=config_id
            )
            operation = create(ctx, prepared)
            original = Collection.insert_many

            def fail_evidence(collection, *args, **kwargs):
                if (
                    collection.database.name == name
                    and collection.name == "evidence_items"
                ):
                    raise RuntimeError(
                        "Synthetic fault injection after result, before evidence"
                    )
                return original(collection, *args, **kwargs)

            with monkeypatch.context() as fault:
                fault.setattr(Collection, "insert_many", fail_evidence)
                assert MongoAnalysisWorker(
                    clients[1][name], ctx["private"]
                ).process_one()
            assert (
                db.analysis_results.count_documents({})
                == db.evidence_items.count_documents({})
                == 0
            )
            assert (
                db.jobs.find_one({"_id": ObjectId(operation["job_id"])})["state"]
                == "QUEUED"
            )
            assert MongoAnalysisWorker(clients[1][name], ctx["private"]).process_one()
            result = client.get(
                path(ctx, "analysis-runs/" + operation["run_id"] + "/results")
            )
            assert (
                result.status_code == 200
                and result.json()["similarity"]
                and result.json()["assessment"]
            ), result.text
            assert db.analysis_results.count_documents({}) == 1
            assert (
                db.audit_events.count_documents({"action": "ANALYSIS_COMPLETED"}) == 1
            )
            if config_id == "research-v0":
                assert result.json()["manifest"]["index_vectors_reused"] is True
                assert result.json()["manifest"]["cached_document_vectors_used"] > 0
    finally:
        for child in clients:
            child.close()
        for user in db.command("usersInfo")["users"]:
            db.command("dropUser", user["user"])
        for role in db.command("rolesInfo")["roles"]:
            db.command("dropRole", role["role"])
        admin.drop_database(name)
        admin.close()
