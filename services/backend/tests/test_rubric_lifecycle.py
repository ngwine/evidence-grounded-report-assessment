"""Executable rubric lifecycle and authority checks; all text is synthetic."""

import os
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import mongomock
import pytest
import yaml
from bson import ObjectId
from jsonschema import Draft202012Validator
from pymongo import MongoClient

from research.core_mvp.rubric_api import compile_api_rubric_definition
from services.backend.src.kltn_ai.db.application_schema import apply_schema_v2
from services.backend.src.kltn_ai.db.migrations import apply_schema_v1
from services.backend.src.kltn_ai.domain.errors import DomainError
from services.backend.src.kltn_ai.domain.rubrics import RubricService


def definition():
    return {"max_score": 10, "criteria": [{
        "criterion_key": "C1", "title": "Implementation", "weight": 10,
        "scoring_mode": "PROPORTIONAL_CHECKLIST_V0", "checklists": [{
            "checklist_key": "C1.1", "statement": "Has a measured implementation",
            "evidence_mode": "LOCAL", "importance": "REQUIRED", "query": "benchmark",
            "requirements": [{"requirement_id": "R1", "any_of": ["benchmark", "latency"]}],
            "contradiction_patterns": ["not implemented"],
        }],
    }]}


def body():
    return {"rubric_key": "synthetic-rubric", "title": "Synthetic rubric", "definition": definition()}


def seed(database):
    now = datetime.now(UTC)
    workspace, other_workspace = ObjectId(), ObjectId()
    identities = {role: ObjectId() for role in ["lecturer", "student", "admin", "other", "disabled"]}
    def common(identifier):
        return {"_id": identifier, "schema_version": 1, "created_at": now, "created_by": None,
                "updated_at": now, "updated_by": None, "revision": 1}
    for role, actor in identities.items():
        database.users.insert_one({**common(actor), "email_normalized": role + "@example.invalid",
                                   "display_name": "Synthetic", "system_roles": ["ADMIN"] if role == "admin" else [],
                                   "status": "DISABLED" if role == "disabled" else "ACTIVE"})
    for identifier, key in [(workspace, "synthetic"), (other_workspace, "other")]:
        database.workspaces.insert_one({**common(identifier), "workspace_key": key,
                                        "kind": "RESEARCH", "name": "Synthetic", "status": "ACTIVE",
                                        "default_purpose": "RESEARCH"})
    for role, actor in identities.items():
        database.memberships.insert_one({
            **common(ObjectId()), "workspace_id": other_workspace if role == "other" else workspace,
            "user_id": actor, "roles": ["LECTURER"] if role in {"lecturer", "other", "disabled"} else ["STUDENT"],
            "status": "ACTIVE", "valid_from": None, "valid_until": None,
        })
    return workspace, other_workspace, identities


def indexes(database):
    database.rubrics.create_index([("workspace_id", 1), ("rubric_key", 1)], unique=True)
    database.rubric_versions.create_index([("rubric_id", 1), ("version_no", 1)], unique=True)
    database.rubric_operations.create_index([
        ("workspace_id", 1), ("actor_id", 1), ("operation_key", 1), ("idempotency_key", 1),
    ], unique=True)


@pytest.fixture
def context():
    database = mongomock.MongoClient(tz_aware=True).kltn_rubric
    indexes(database)
    workspace, other, actors = seed(database)
    return database, RubricService(database, transaction_mode=False), workspace, other, actors


def create(context, *, key="create-one", value=None):
    _, service, workspace, _, actors = context
    return service.create(actors["lecturer"], workspace, value or body(),
                          idempotency_key=key, request_id="req-synthetic")


def test_create_replay_body_conflict_scoped_audit_and_no_unknown_output(context):
    database, service, workspace, _, actors = context
    first = create(context)
    assert create(context) == first
    assert set(first) == {"id", "workspace_id", "rubric_key", "title", "current_version_id", "lifecycle_state", "revision"}
    assert database.rubrics.count_documents({}) == database.rubric_versions.count_documents({}) == 1
    changed = body()
    changed["title"] = "Changed title"
    with pytest.raises(DomainError) as error:
        create(context, value=changed)
    assert (error.value.status, error.value.code) == (409, "IDEMPOTENCY_CONFLICT")
    with pytest.raises(DomainError) as error:
        create(context, key="another-key")
    assert error.value.code == "RUBRIC_CONFLICT"
    assert service.get(actors["lecturer"], workspace, first["id"]) == first
    event = database.audit_events.find_one({})
    assert event["action"] == "RUBRIC_CREATED" and event["metadata_allowlist"] == {}
    assert "definition" not in event and "statement" not in str(event)


@pytest.mark.parametrize("role,status", [("student", 403), ("admin", 403), ("other", 404), ("disabled", 401)])
def test_all_operations_recheck_role_workspace_and_active_user(context, role, status):
    _, service, workspace, _, actors = context
    rubric = create(context)
    calls = [
        lambda: service.create(actors[role], workspace, body(), idempotency_key="new", request_id="req-test"),
        lambda: service.list(actors[role], workspace),
        lambda: service.get(actors[role], workspace, rubric["id"]),
        lambda: service.get_version(actors[role], workspace, rubric["current_version_id"]),
        lambda: service.list_versions(actors[role], workspace, rubric["id"]),
        lambda: service.clone_version(actors[role], workspace, rubric["id"], {"definition": definition()},
                                     expected_revision=1, idempotency_key="clone", request_id="req-test"),
        lambda: service.update_draft(actors[role], workspace, rubric["current_version_id"], definition(),
                                     expected_revision=1, request_id="req-test"),
        lambda: service.publish_version(actors[role], workspace, rubric["current_version_id"],
                                        expected_revision=1, idempotency_key="publish", request_id="req-test"),
        lambda: service.get_compiled_published(actors[role], workspace, rubric["current_version_id"]),
    ]
    for call in calls:
        with pytest.raises(DomainError) as error:
            call()
        assert error.value.status == status


def test_revoked_membership_blocks_even_idempotent_replay_and_compiled_read(context):
    database, service, workspace, _, actors = context
    rubric = create(context)
    service.publish_version(actors["lecturer"], workspace, rubric["current_version_id"],
                            expected_revision=1, idempotency_key="publish", request_id="req-test")
    database.memberships.update_one({"user_id": actors["lecturer"]}, {"$set": {"status": "REVOKED"}})
    for call in [lambda: create(context), lambda: service.get_compiled_published(
        actors["lecturer"], workspace, rubric["current_version_id"],
    )]:
        with pytest.raises(DomainError) as error:
            call()
        assert error.value.status == 404


def test_draft_cas_then_deterministic_publish_immutable_replay_and_clone(context):
    database, service, workspace, _, actors = context
    actor = actors["lecturer"]
    rubric = create(context)
    version = rubric["current_version_id"]
    with pytest.raises(DomainError) as error:
        service.get_compiled_published(actor, workspace, version)
    assert error.value.code == "RUBRIC_NOT_PUBLISHED"
    edited = definition()
    edited["criteria"][0]["title"] = "Updated criterion"
    draft = service.update_draft(actor, workspace, version, edited, expected_revision=1, request_id="req-update")
    assert draft["revision"] == 2 and draft["definition"] == edited
    with pytest.raises(DomainError) as error:
        service.update_draft(actor, workspace, version, definition(), expected_revision=1, request_id="req-stale")
    assert error.value.code == "REVISION_CONFLICT"
    published = service.publish_version(actor, workspace, version, expected_revision=2,
                                        idempotency_key="publish", request_id="req-publish")
    assert published["status"] == "PUBLISHED" and published["revision"] == 3
    assert service.publish_version(actor, workspace, version, expected_revision=2,
                                   idempotency_key="publish", request_id="req-replay") == published
    compiled = service.get_compiled_published(actor, workspace, version)
    assert compiled["rubric_version"] == "1"
    assert compiled["compiler"]["automatic_decomposition"] is False
    assert service.get_compiled_published(actor, workspace, version) == compiled
    stored = database.rubric_versions.find_one({"_id": ObjectId(version)})
    assert stored["compiled_sha256"] == compiled["compiled_sha256"]
    assert stored["compiler_version"] == compiled["compiler"]["version"]
    before = deepcopy(stored)
    for call in [
        lambda: service.update_draft(actor, workspace, version, definition(), expected_revision=3, request_id="req-no"),
        lambda: service.publish_version(actor, workspace, version, expected_revision=3,
                                        idempotency_key="new-publish", request_id="req-no"),
    ]:
        with pytest.raises(DomainError) as error:
            call()
        assert error.value.code == "RUBRIC_IMMUTABLE"
    assert database.rubric_versions.find_one({"_id": ObjectId(version)}) == before
    clone = service.clone_version(actor, workspace, rubric["id"], {"clone_from_version_id": version},
                                  expected_revision=2, idempotency_key="clone", request_id="req-clone")
    assert clone["version_no"] == 2 and clone["status"] == "DRAFT" and clone["revision"] == 1
    assert clone["definition"] == published["definition"]
    assert service.get(actor, workspace, rubric["id"])["current_version_id"] == version
    assert service.clone_version(actor, workspace, rubric["id"], {"clone_from_version_id": version},
                                 expected_revision=2, idempotency_key="clone", request_id="req-again") == clone
    next_published = service.publish_version(actor, workspace, clone["id"], expected_revision=1,
                                             idempotency_key="publish-v2", request_id="req-publish")
    assert next_published["status"] == "PUBLISHED"
    assert service.get(actor, workspace, rubric["id"])["current_version_id"] == clone["id"]
    assert service.get_version(actor, workspace, version) == published
    assert service.get_compiled_published(actor, workspace, clone["id"])["compiled_sha256"] != compiled["compiled_sha256"]


@pytest.mark.parametrize("mutation,field", [
    (lambda value: value["criteria"][0].update(levels=[{"level_key": "top", "score": 10, "rule": "private text"}]), ".levels"),
    (lambda value: value["criteria"][0]["checklists"][0].update(requirement="private legacy text"), ".requirement"),
    (lambda value: value["criteria"][0]["checklists"][0].update(evidence_mode="GRAPH"), "definition"),
    (lambda value: value.update(max_score=11), "definition"),
])
def test_publish_fails_closed_unsupported_or_invalid_scoring_and_no_raw_errors(context, mutation, field):
    database, service, workspace, _, actors = context
    value = body()
    mutation(value["definition"])
    rubric = create(context, value=value)
    with pytest.raises(DomainError) as error:
        service.publish_version(actors["lecturer"], workspace, rubric["current_version_id"],
                                expected_revision=1, idempotency_key="publish", request_id="req-publish")
    assert error.value.code == "RUBRIC_COMPILATION_FAILED"
    assert field in error.value.message and "private" not in error.value.message
    assert database.rubric_versions.find_one({})["status"] == "DRAFT"
    assert database.rubric_operations.count_documents({}) == 1


def test_graph_two_authored_requirements_preserved(context):
    _, service, workspace, _, actors = context
    value = body()
    checklist = value["definition"]["criteria"][0]["checklists"][0]
    checklist["evidence_mode"] = "GRAPH"
    checklist["requirements"].append({"requirement_id": "R2", "description": "Other section", "any_of": ["method"]})
    rubric = create(context, value=value)
    service.publish_version(actors["lecturer"], workspace, rubric["current_version_id"], expected_revision=1,
                            idempotency_key="publish", request_id="req-publish")
    compiled = service.get_compiled_published(actors["lecturer"], workspace, rubric["current_version_id"])
    item = compiled["criteria"][0]["checklists"][0]
    assert item["mode"] == "GRAPH" and len(item["requirements"]) == 2
    assert item["query"] == checklist["query"] and item["contradiction_patterns"] == checklist["contradiction_patterns"]


def test_validation_safe_unknown_fields_size_numeric_and_finite(context):
    _, _, _, _, _ = context
    cases = [
        {**body(), "untrusted author text": "private"},
        {**body(), "title": "x" * 501},
        {**body(), "definition": {**definition(), "max_score": float("nan")}},
        {**body(), "definition": {**definition(), "max_score": True}},
    ]
    for value in cases:
        with pytest.raises(DomainError) as error:
            create(context, value=value)
        assert error.value.status == 422 and "private" not in error.value.message


def test_two_concurrent_clone_requests_same_revision_one_wins_no_ordinal_collision(context):
    database, service, workspace, _, actors = context
    rubric = create(context)
    def clone(number):
        try:
            return service.clone_version(actors["lecturer"], workspace, rubric["id"], {"definition": definition()},
                                         expected_revision=1, idempotency_key=f"clone-{number}", request_id="req-clone")
        except DomainError as exc:
            return exc.code
    with ThreadPoolExecutor(max_workers=2) as executor:
        values = list(executor.map(clone, range(2)))
    assert sum(isinstance(item, dict) for item in values) == 1
    assert "REVISION_CONFLICT" in values
    assert sorted(item["version_no"] for item in database.rubric_versions.find({})) == [1, 2]
    current = service.get(actors["lecturer"], workspace, rubric["id"])
    third = service.clone_version(actors["lecturer"], workspace, rubric["id"], {"definition": definition()},
                                  expected_revision=current["revision"], idempotency_key="clone-third", request_id="req-clone")
    assert third["version_no"] == 3


def test_workspace_isolation_clone_source_and_pagination(context):
    _, service, workspace, other, actors = context
    first = create(context)
    second_body = {**body(), "rubric_key": "second"}
    second = create(context, key="second", value=second_body)
    page = service.list(actors["lecturer"], workspace, limit=1)
    assert page["page"]["has_more"] is True and len(page["items"]) == 1
    remaining = service.list(actors["lecturer"], workspace, limit=1, cursor=page["page"]["next_cursor"])
    assert remaining["page"]["has_more"] is False
    assert {page["items"][0]["id"], remaining["items"][0]["id"]} == {first["id"], second["id"]}
    with pytest.raises(DomainError) as error:
        service.get(actors["other"], other, first["id"])
    assert error.value.status == 404
    with pytest.raises(DomainError) as error:
        service.clone_version(actors["lecturer"], workspace, second["id"],
                              {"clone_from_version_id": first["current_version_id"]}, expected_revision=1,
                              idempotency_key="wrong-parent", request_id="req-clone")
    assert error.value.status == 404


def test_version_listing_recovers_drafts_without_changing_current_publication(context):
    _, service, workspace, other, actors = context
    rubric = create(context)
    draft = service.clone_version(actors["lecturer"], workspace, rubric["id"], {"definition": definition()},
                                  expected_revision=1, idempotency_key="clone-draft", request_id="req-clone")
    page = service.list_versions(actors["lecturer"], workspace, rubric["id"], limit=1)
    assert page["items"][0]["id"] == rubric["current_version_id"]
    assert page["page"]["has_more"] is True
    following = service.list_versions(actors["lecturer"], workspace, rubric["id"],
                                      limit=1, cursor=page["page"]["next_cursor"])
    assert following["items"] == [draft] and following["page"]["has_more"] is False
    with pytest.raises(DomainError) as error:
        service.list_versions(actors["other"], other, rubric["id"])
    assert error.value.status == 404
def test_published_integrity_fail_closed(context):
    database, service, workspace, _, actors = context
    rubric = create(context)
    version = ObjectId(rubric["current_version_id"])
    service.publish_version(actors["lecturer"], workspace, version, expected_revision=1,
                            idempotency_key="publish", request_id="req-publish")
    database.rubric_versions.update_one({"_id": version}, {"$set": {"compiled.max_score": 999}})
    with pytest.raises(DomainError) as error:
        service.get_compiled_published(actors["lecturer"], workspace, version)
    assert error.value.code == "RUBRIC_INTEGRITY_FAILED"


def test_self_consistent_swapped_compiled_snapshot_is_not_bound_to_authoring(context):
    database, service, workspace, _, actors = context
    rubric = create(context)
    version = ObjectId(rubric["current_version_id"])
    service.publish_version(actors["lecturer"], workspace, version, expected_revision=1,
                            idempotency_key="publish", request_id="req-publish")
    different = definition()
    different["criteria"][0]["title"] = "Swapped criterion"
    compiled = compile_api_rubric_definition(rubric_key=body()["rubric_key"], title=body()["title"],
                                             rubric_version="1", definition=different)
    database.rubric_versions.update_one({"_id": version}, {"$set": {
        "compiled": compiled, "compiled_sha256": compiled["compiled_sha256"],
        "compiled_id": compiled["compiled_id"],
    }})
    with pytest.raises(DomainError) as error:
        service.get_compiled_published(actors["lecturer"], workspace, version)
    assert error.value.code == "RUBRIC_INTEGRITY_FAILED"


def test_service_response_shapes_follow_real_openapi_components(context):
    _, service, workspace, _, actors = context
    document = yaml.safe_load((Path(__file__).parents[3] / "docs/api/openapi-v1.yaml").read_text())
    def validate(component, value):
        schema = {"$schema": "https://json-schema.org/draft/2020-12/schema",
                  "components": document["components"], "$ref": "#/components/schemas/" + component}
        Draft202012Validator(schema).validate(value)
    validate("CreateRubricRequest", body())
    rubric = create(context)
    validate("Rubric", rubric)
    validate("RubricPage", service.list(actors["lecturer"], workspace))
    validate("RubricVersion", service.get_version(actors["lecturer"], workspace, rubric["current_version_id"]))
    published = service.publish_version(actors["lecturer"], workspace, rubric["current_version_id"],
                                        expected_revision=1, idempotency_key="publish", request_id="req-publish")
    validate("RubricVersion", published)


def test_production_mode_does_not_silently_fallback_to_nontransaction_mongo(context):
    database, _, workspace, _, actors = context
    service = RubricService(database)
    with pytest.raises(NotImplementedError):
        service.create(actors["lecturer"], workspace, body(), idempotency_key="prod", request_id="req-prod")
    assert database.rubrics.count_documents({}) == 0


def test_live_rubric_transactions_rollback_duplicate_and_concurrent_clone():
    uri = os.environ.get("KLTN_MONGO_TEST_URI")
    if not uri:
        pytest.skip("Set KLTN_MONGO_TEST_URI for real rubric transaction tests")
    with MongoClient(uri, tz_aware=True, serverSelectionTimeoutMS=5000) as client:
        database = client["kltn_rubric_test_" + uuid4().hex]
        try:
            apply_schema_v1(database, code_commit="0" * 40, applied_by="synthetic-test")
            apply_schema_v2(database, code_commit="0" * 40, applied_by="synthetic-test")
            workspace, other, actors = seed(database)
            service = RubricService(database)
            context = database, service, workspace, other, actors
            rubric = create(context)
            with pytest.raises(DomainError):
                create(context, key="duplicate")
            assert database.rubric_versions.count_documents({}) == 1
            def clone(number):
                try:
                    return service.clone_version(actors["lecturer"], workspace, rubric["id"],
                                                 {"definition": definition()}, expected_revision=1,
                                                 idempotency_key=f"clone-{number}", request_id="req-clone")
                except DomainError as exc:
                    return exc.code
            with ThreadPoolExecutor(max_workers=2) as executor:
                outcomes = list(executor.map(clone, range(2)))
            assert sum(isinstance(item, dict) for item in outcomes) == 1
            assert "REVISION_CONFLICT" in outcomes
            service.publish_version(actors["lecturer"], workspace, rubric["current_version_id"],
                                    expected_revision=1, idempotency_key="publish", request_id="req-publish")
            assert service.get_compiled_published(actors["lecturer"], workspace, rubric["current_version_id"])
            # An audit failure happens after the writes; a real transaction
            # must roll both the new parent and its first draft back.
            bad = {**body(), "rubric_key": "rollback"}
            with pytest.raises(DomainError):
                service.create(actors["lecturer"], workspace, bad,
                               idempotency_key="rollback", request_id="invalid request id")
            assert database.rubrics.count_documents({"rubric_key": "rollback"}) == 0
            assert database.rubric_versions.count_documents({}) == 2
        finally:
            client.drop_database(database.name)
