"""HTTP auth and authoring boundary tests; synthetic data and no network DB."""

from __future__ import annotations

import hashlib
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import mongomock
import pytest
import yaml
from bson import ObjectId
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
from pymongo.errors import OperationFailure

from services.backend.src.kltn_ai.api.app import COOKIE, MAX_BODY, PREFIX, create_app
from services.backend.src.kltn_ai.auth.service import AuthService, create_local_user
from services.backend.src.kltn_ai.domain.errors import DomainError


ORIGIN = "http://127.0.0.1:5173"
PASSWORD = "synthetic-owner-password"
EMAIL = "lecturer@example.test"
OPENAPI = Path(__file__).resolve().parents[3] / "docs" / "api" / "openapi-v1.yaml"


def definition():
    return {"max_score": 10, "criteria": [{
        "criterion_key": "C1", "title": "Implementation", "weight": 10,
        "scoring_mode": "PROPORTIONAL_CHECKLIST_V0", "checklists": [{
            "checklist_key": "C1.1", "statement": "Has a measured implementation",
            "evidence_mode": "LOCAL", "importance": "REQUIRED",
            "requirements": [{"requirement_id": "R1", "any_of": ["benchmark", "latency"]}],
            "contradiction_patterns": ["not implemented"],
        }],
    }]}


def create_body():
    return {"rubric_key": "http-synthetic", "title": "Synthetic HTTP rubric", "definition": definition()}


def validate_component(component, value):
    document = yaml.safe_load(OPENAPI.read_text())
    Draft202012Validator({"components": document["components"],
                           "$ref": f"#/components/schemas/{component}"}).validate(value)


@pytest.fixture
def context():
    database = mongomock.MongoClient(tz_aware=True).http_boundary
    database.users.create_index("email_normalized", unique=True)
    database.auth_credentials.create_index("user_id", unique=True)
    database.auth_sessions.create_index("token_sha256", unique=True)
    database.rubrics.create_index([("workspace_id", 1), ("rubric_key", 1)], unique=True)
    database.rubric_versions.create_index([("rubric_id", 1), ("version_no", 1)], unique=True)
    database.rubric_operations.create_index([
        ("workspace_id", 1), ("actor_id", 1), ("operation_key", 1), ("idempotency_key", 1),
    ], unique=True)

    def cheap_hash(password):
        return "test-only$" + hashlib.sha256(password.encode()).hexdigest()

    actor = create_local_user(database, EMAIL, "Synthetic lecturer", PASSWORD, password_hasher=cheap_hash)
    actor_id = ObjectId(actor["id"])
    now = datetime.now(timezone.utc)
    workspace_id = database.workspaces.insert_one({
        "workspace_key": "synthetic-workspace", "name": "Synthetic", "status": "ACTIVE",
        "kind": "RESEARCH", "default_purpose": "RESEARCH", "schema_version": 1,
        "created_at": now, "created_by": actor_id, "updated_at": now,
        "updated_by": actor_id, "revision": 1,
    }).inserted_id
    membership_id = database.memberships.insert_one({
        "workspace_id": workspace_id, "user_id": actor_id, "roles": ["LECTURER"],
        "status": "ACTIVE", "valid_from": None, "valid_until": None,
    }).inserted_id
    auth = AuthService(database, password_verifier=lambda password, encoded: cheap_hash(password) == encoded)
    app = create_app(database, allow_test_client=True, auth_service=auth, transaction_mode=False)
    with TestClient(app) as client:
        yield {"db": database, "client": client, "auth": auth, "app": app,
               "actor_id": actor_id, "workspace_id": str(workspace_id), "membership_id": membership_id}


def sign_in(context):
    response = context["client"].post(f"{PREFIX}/auth/sessions", json={"email": EMAIL, "password": PASSWORD},
                                      headers={"Origin": ORIGIN})
    assert response.status_code == 200, response.text
    return response


def headers(context, *, key="synthetic-operation-0001", revision=None):
    result = {"Origin": ORIGIN, "X-CSRF-Token": context["csrf"], "Idempotency-Key": key}
    if revision is not None:
        result["If-Match"] = revision
    return result


def rubric_path(context):
    return f"{PREFIX}/workspaces/{context['workspace_id']}/rubrics"


def create_rubric(context):
    response = context["client"].post(rubric_path(context), json=create_body(), headers=headers(context))
    assert response.status_code == 201, response.text
    assert response.headers["etag"] == '"rev-1"'
    return response.json()


def assert_error(response, status, code=None):
    assert response.status_code == status, response.text
    error = response.json()["error"]
    assert set(error) == {"code", "message", "request_id"}
    if code:
        assert error["code"] == code
    assert error["request_id"] == response.headers["x-request-id"]
    assert response.headers["cache-control"] == "no-store"
    assert PASSWORD not in response.text
    assert "Traceback" not in response.text
    return error


def test_login_cookie_boundary_actor_me_and_no_raw_secret_in_payload(context):
    response = sign_in(context)
    data = response.json()
    validate_component("SessionInfo", data)
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie
    assert "Path=/api/v1" in cookie and "Max-Age=28800" in cookie
    assert PASSWORD not in response.text
    assert set(data) == {"actor", "csrf_token", "expires_at"}
    assert COOKIE in context["client"].cookies
    me = context["client"].get(f"{PREFIX}/auth/me")
    assert me.status_code == 200
    validate_component("Actor", me.json())
    assert me.json() == data["actor"]
    assert me.headers["x-content-type-options"] == "nosniff"
    assert context["client"].cookies[COOKIE] not in me.text


@pytest.mark.parametrize("path", ["/auth/me", "/workspaces", "/workspaces/ffffffffffffffffffffffff/rubrics"])
def test_unauthenticated_reads_are_401_and_never_inherit_local_demo_role(context, path):
    assert_error(context["client"].get(PREFIX + path), 401, "AUTHENTICATION_REQUIRED")


@pytest.mark.parametrize("origin,code", [(None, "ORIGIN_REQUIRED"),
                                       ("https://attacker.example", "ORIGIN_DENIED"),
                                       ("null", "ORIGIN_DENIED")])
def test_login_requires_allowed_origin(context, origin, code):
    response = context["client"].post(f"{PREFIX}/auth/sessions", json={"email": EMAIL, "password": PASSWORD},
                                      headers={"Origin": origin} if origin else {})
    assert_error(response, 403, code)
    assert context["db"].auth_sessions.count_documents({}) == 0


def test_wrong_login_and_unknown_identity_have_identical_public_errors(context):
    failures = []
    for email in (EMAIL, "missing@example.test"):
        response = context["client"].post(f"{PREFIX}/auth/sessions",
                                          json={"email": email, "password": "wrong-password"},
                                          headers={"Origin": ORIGIN})
        error = assert_error(response, 401, "INVALID_CREDENTIALS")
        assert email not in response.text
        failures.append({key: value for key, value in error.items() if key != "request_id"})
    assert failures[0] == failures[1]


def test_unsafe_authoring_rejects_missing_wrong_csrf_and_missing_origin(context):
    sign_in(context)
    for supplied in ({"Origin": ORIGIN}, {"Origin": ORIGIN, "X-CSRF-Token": "wrong-token"},
                     {"X-CSRF-Token": "whatever"}):
        response = context["client"].post(rubric_path(context), json=create_body(), headers=supplied)
        assert_error(response, 403)
    assert context["db"].rubrics.count_documents({}) == 0


def test_session_rotation_and_logout_revoke_old_cookie_and_require_csrf(context):
    first = sign_in(context)
    old_cookie = context["client"].cookies[COOKIE]
    second = sign_in(context)
    new_cookie = context["client"].cookies[COOKIE]
    assert old_cookie != new_cookie
    with pytest.raises(DomainError) as failure:
        context["auth"].authenticate(old_cookie)
    assert getattr(failure.value, "status", None) == 401
    denied = context["client"].delete(f"{PREFIX}/auth/session", headers={"Origin": ORIGIN})
    assert_error(denied, 403, "CSRF_INVALID")
    response = context["client"].delete(f"{PREFIX}/auth/session", headers={
        "Origin": ORIGIN, "X-CSRF-Token": second.json()["csrf_token"],
    })
    assert response.status_code == 204 and not response.content
    assert "Max-Age=0" in response.headers["set-cookie"]
    assert COOKIE not in context["client"].cookies
    assert_error(context["client"].get(f"{PREFIX}/auth/me"), 401)
    assert first.json()["csrf_token"] != second.json()["csrf_token"]


@pytest.mark.parametrize("change,status", [("disabled", 401), ("revoked", 404), ("student", 403)])
def test_account_and_membership_changes_take_effect_without_relogin(context, change, status):
    context["csrf"] = sign_in(context).json()["csrf_token"]
    if change == "disabled":
        context["db"].users.update_one({"_id": context["actor_id"]}, {"$set": {"status": "DISABLED"}})
    else:
        update = {"status": "REVOKED"} if change == "revoked" else {"roles": ["STUDENT"]}
        context["db"].memberships.update_one({"_id": context["membership_id"]}, {"$set": update})
    assert_error(context["client"].post(rubric_path(context), json=create_body(), headers=headers(context)), status)
    assert context["db"].rubrics.count_documents({}) == 0


def test_cross_workspace_and_non_academic_admin_do_not_gain_rubric_access(context):
    context["csrf"] = sign_in(context).json()["csrf_token"]
    hidden = context["client"].get(f"{PREFIX}/workspaces/{ObjectId()}/rubrics")
    assert_error(hidden, 404, "RESOURCE_NOT_FOUND")
    context["db"].users.update_one({"_id": context["actor_id"]}, {"$set": {"system_roles": ["ADMIN"]}})
    context["db"].memberships.update_one({"_id": context["membership_id"]}, {"$set": {"roles": ["OPERATOR"]}})
    denied = context["client"].post(rubric_path(context), json=create_body(), headers=headers(context))
    assert_error(denied, 403)


def test_request_identifier_reflection_is_bounded_and_malicious_header_is_replaced(context):
    for request_id in ("unsafe/raw-token", "x" * 129):
        response = context["client"].get(f"{PREFIX}/auth/me", headers={"X-Request-ID": request_id})
        error = assert_error(response, 401)
        assert error["request_id"].startswith("req-")
        assert request_id not in response.text
    response = context["client"].get(f"{PREFIX}/auth/me", headers={"X-Request-ID": "req-safe-trace-0001"})
    assert assert_error(response, 401)["request_id"] == "req-safe-trace-0001"


@pytest.mark.parametrize("content,content_type", [(b"{malformed", "application/json"),
                                                  (b'[{"email":"secret@example.test"}]', "application/json"),
                                                  (b"a=b", "text/plain")])
def test_bad_login_bodies_are_safe_bounded_validation_failures(context, content, content_type):
    response = context["client"].post(f"{PREFIX}/auth/sessions", content=content,
                                      headers={"Origin": ORIGIN, "Content-Type": content_type})
    assert_error(response, 415 if content_type == "text/plain" else 422)
    assert "secret@example.test" not in response.text


def test_body_budget_blocks_before_credentials_or_rubric_mutation(context):
    response = context["client"].post(f"{PREFIX}/auth/sessions", content=b"x" * (MAX_BODY + 1),
                                      headers={"Origin": ORIGIN, "Content-Type": "application/json"})
    assert_error(response, 413, "PAYLOAD_TOO_LARGE")
    assert context["db"].auth_sessions.count_documents({}) == 0


def test_actual_stream_budget_applies_even_when_declared_length_is_small(context):
    def chunks():
        yield b"x" * MAX_BODY
        yield b"y" * 20

    response = context["client"].post(f"{PREFIX}/auth/sessions", content=chunks(), headers={
        "Origin": ORIGIN, "Content-Type": "application/json", "Content-Length": "0",
    })
    assert_error(response, 413, "PAYLOAD_TOO_LARGE")
    assert context["db"].auth_throttles.count_documents({}) == 0


def test_login_bruteforce_returns_retry_after_before_password_verification(context):
    for _ in range(10):
        response = context["client"].post(f"{PREFIX}/auth/sessions",
                                          json={"email": EMAIL, "password": "wrong-password"},
                                          headers={"Origin": ORIGIN})
        assert_error(response, 401, "INVALID_CREDENTIALS")
    limited = context["client"].post(f"{PREFIX}/auth/sessions", json={"email": EMAIL, "password": PASSWORD},
                                     headers={"Origin": ORIGIN})
    assert_error(limited, 429, "RATE_LIMITED")
    assert 1 <= int(limited.headers["retry-after"]) <= 300
    assert context["db"].auth_sessions.count_documents({}) == 0


def test_deployment_denies_untrusted_host_and_forwarded_origin_cannot_override(context):
    response = context["client"].get(f"{PREFIX}/auth/me", headers={
        "Host": "attacker.example", "X-Forwarded-For": "127.0.0.1", "X-Forwarded-Host": "localhost",
    })
    assert_error(response, 403, "DEPLOYMENT_SCOPE_DENIED")


def test_create_publish_immutable_revision_idempotency_and_current_scope(context):
    context["csrf"] = sign_in(context).json()["csrf_token"]
    validate_component("CreateRubricRequest", create_body())
    rubric = create_rubric(context)
    replay = context["client"].post(rubric_path(context), json=create_body(), headers=headers(context))
    assert replay.status_code == 201 and replay.json() == rubric
    changed = create_body()
    changed["title"] = "Changed synthetic title"
    conflict = context["client"].post(rubric_path(context), json=changed, headers=headers(context))
    assert_error(conflict, 409, "IDEMPOTENCY_CONFLICT")
    version_path = f"{PREFIX}/workspaces/{context['workspace_id']}/rubric-versions/{rubric['current_version_id']}"
    version = context["client"].get(version_path)
    assert version.status_code == 200 and version.json()["status"] == "DRAFT"
    assert version.headers["etag"] == '"rev-1"'
    no_revision = context["client"].put(version_path, json=definition(), headers=headers(context))
    assert_error(no_revision, 428, "PRECONDITION_REQUIRED")
    updated_definition = deepcopy(definition())
    updated_definition["criteria"][0]["title"] = "Updated implementation"
    updated = context["client"].put(version_path, json=updated_definition,
                                    headers=headers(context, revision='"rev-1"'))
    assert updated.status_code == 200 and updated.headers["etag"] == '"rev-2"'
    stale = context["client"].put(version_path, json=updated_definition,
                                  headers=headers(context, revision='"rev-1"'))
    assert_error(stale, 409, "REVISION_CONFLICT")
    published = context["client"].post(version_path + ":publish",
                                      headers=headers(context, key="publish-operation-0001", revision='"rev-2"'))
    assert published.status_code == 200 and published.json()["status"] == "PUBLISHED"
    assert published.headers["etag"] == '"rev-3"'
    assert "compiled" not in published.json()
    immutable = context["client"].put(version_path, json=definition(),
                                      headers=headers(context, revision='"rev-3"'))
    assert_error(immutable, 409, "RUBRIC_IMMUTABLE")
    record = context["db"].rubric_versions.find_one({"_id": ObjectId(rubric["current_version_id"])})
    assert record["compiled_id"] and record["compiled_sha256"]
    context["db"].memberships.update_one({"_id": context["membership_id"]}, {"$set": {"status": "REVOKED"}})
    denied_replay = context["client"].post(rubric_path(context), json=create_body(), headers=headers(context))
    assert_error(denied_replay, 404)


def test_database_failure_is_safe_503_not_raw_driver_message(context, monkeypatch):
    sign_in(context)

    def unavailable(*args, **kwargs):
        raise OperationFailure("internal password=secret database URI unpublished report text")

    monkeypatch.setattr(context["db"].auth_sessions, "find_one", unavailable)
    response = context["client"].get(f"{PREFIX}/auth/me")
    assert_error(response, 503)
    for secret in ("password=", "URI", "report text", "OperationFailure"):
        assert secret not in response.text


def test_unexpected_failure_is_safe_json_500_not_stack_or_secret(context, monkeypatch):
    def unavailable(*args, **kwargs):
        raise RuntimeError("secret-token raw report content database-password")

    monkeypatch.setattr(context["auth"], "authenticate", unavailable)
    response = context["client"].get(f"{PREFIX}/auth/me")
    assert_error(response, 500, "INTERNAL_ERROR")
    for secret in ("secret-token", "report content", "database-password", "RuntimeError"):
        assert secret not in response.text


def test_deep_json_is_bounded_safe_validation_error_not_unhandled_recursion(context):
    response = context["client"].post(f"{PREFIX}/auth/sessions", content=b"[" * 2000 + b"0" + b"]" * 2000,
                                      headers={"Origin": ORIGIN, "Content-Type": "application/json"})
    assert_error(response, 422, "VALIDATION_FAILED")


def test_authenticated_csrf_refresh_recovers_browser_reload_without_storing_raw_token(context):
    original_csrf = sign_in(context).json()["csrf_token"]
    response = context["client"].get(f"{PREFIX}/auth/csrf", headers={"Origin": ORIGIN, "X-CSRF-Refresh": "1"})
    assert response.status_code == 200
    assert set(response.json()) == {"csrf_token"}
    csrf = response.json()["csrf_token"]
    assert csrf != original_csrf
    assert response.headers["cache-control"] == "no-store"
    persisted = repr(list(context["db"].auth_sessions.find()))
    assert csrf not in persisted and original_csrf not in persisted
    context["csrf"] = original_csrf
    old = context["client"].post(rubric_path(context), json=create_body(), headers=headers(context))
    assert_error(old, 403, "CSRF_INVALID")
    context["csrf"] = csrf
    create_rubric(context)


def test_csrf_refresh_requires_valid_session_and_never_trusts_cross_origin(context):
    assert_error(context["client"].get(f"{PREFIX}/auth/csrf"), 401)
    sign_in(context)
    denied = context["client"].get(f"{PREFIX}/auth/csrf", headers={"Origin": "https://attacker.example"})
    assert_error(denied, 403, "ORIGIN_DENIED")
    simple_get = context["client"].get(f"{PREFIX}/auth/csrf", headers={"Origin": ORIGIN})
    assert_error(simple_get, 403)


def test_csrf_refresh_fails_closed_when_session_changes_concurrently(context, monkeypatch):
    sign_in(context)
    monkeypatch.setattr(context["db"].auth_sessions, "update_one",
                        lambda *args, **kwargs: SimpleNamespace(matched_count=0))
    response = context["client"].get(f"{PREFIX}/auth/csrf", headers={"Origin": ORIGIN, "X-CSRF-Refresh": "1"})
    assert_error(response, 409, "SESSION_CHANGED")
