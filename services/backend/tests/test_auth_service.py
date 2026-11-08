"""Authentication behavior including real scrypt, plus bounded mocked DB tests."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

import mongomock
import pytest
from bson import ObjectId

from services.backend.src.kltn_ai.auth.service import (
    AuthService,
    LOGIN_IDENTITY_LIMIT,
    LOGIN_PAIR_LIMIT,
    LOGIN_PEER_LIMIT,
    SESSION_LIFETIME,
    create_local_user,
    hash_password,
    verify_password,
)
from services.backend.src.kltn_ai.domain.access import ROLE_CAPABILITIES
from services.backend.src.kltn_ai.domain.errors import DomainError


NOW = datetime(2026, 10, 23, 3, 0, tzinfo=timezone.utc)
PASSWORD = "a-test-operator-password"
EMAIL = "owner@example.test"


def cheap_hash(password):
    return "test-sha256$" + hashlib.sha256(password.encode()).hexdigest()


@pytest.fixture
def database():
    database = mongomock.MongoClient(tz_aware=True).auth_test
    database.users.create_index("email_normalized", unique=True)
    database.auth_credentials.create_index("user_id", unique=True)
    database.auth_sessions.create_index("token_sha256", unique=True)
    # Do not ask mongomock's TTL implementation to delete our fixed-time rows.
    return database


@pytest.fixture
def account(database):
    return create_local_user(database, EMAIL, "Test owner", PASSWORD,
                             now=NOW, password_hasher=cheap_hash)


@pytest.fixture
def service(database):
    def verifier(password, encoded):
        return cheap_hash(password) == encoded
    return AuthService(database, password_verifier=verifier)


def login(service, *, now=NOW, **kwargs):
    return service.login(EMAIL, PASSWORD, "loopback-peer", now=now, **kwargs)


def add_membership(database, account, *, roles=None, status="ACTIVE", workspace_status="ACTIVE",
                   valid_from=None, valid_until=None):
    workspace_id = ObjectId()
    database.workspaces.insert_one({"_id": workspace_id, "workspace_key": str(workspace_id),
                                   "name": "Test workspace", "status": workspace_status})
    identifier = database.memberships.insert_one({
        "workspace_id": workspace_id, "user_id": ObjectId(account["id"]),
        "roles": roles or ["STUDENT"], "status": status,
        "valid_from": valid_from, "valid_until": valid_until,
    }).inserted_id
    return identifier, workspace_id


def test_real_scrypt_password_hash_random_salt_and_reject_wrong_password():
    first = hash_password(PASSWORD)
    second = hash_password(PASSWORD)
    assert first != second
    assert first.startswith("scrypt$n=131072,r=8,p=1$")
    assert PASSWORD not in first
    assert verify_password(PASSWORD, first)
    assert not verify_password("incorrect-operator-password", first)
    assert not verify_password(PASSWORD, first.replace("n=131072", "n=99999999999"))
    assert not verify_password(PASSWORD, "malformed")
    assert not verify_password(PASSWORD, "scrypt$n=131072,r=8,p=1$!$!")


@pytest.mark.parametrize("password", ["short", "", "x" * 1025, "\x00" * 15, "\ud800" * 15])
def test_bootstrap_rejects_invalid_password_before_db_insert(database, password):
    with pytest.raises(ValueError):
        create_local_user(database, EMAIL, "Test owner", password, password_hasher=cheap_hash)
    assert database.users.count_documents({}) == 0
    assert database.auth_credentials.count_documents({}) == 0


def test_bootstrap_normalizes_identity_and_credential_is_separate(database):
    actor = create_local_user(database, " Owner@Example.Test ", " Test owner ", PASSWORD,
                              now=NOW, password_hasher=cheap_hash)
    user = database.users.find_one({"_id": ObjectId(actor["id"])})
    assert user["email_normalized"] == EMAIL
    assert user["display_name"] == "Test owner"
    assert not any("password" in key for key in user)
    credential = database.auth_credentials.find_one({"user_id": user["_id"]})
    assert credential["password_hash"] == cheap_hash(PASSWORD)
    assert credential["revision"] == 1
    assert PASSWORD not in repr(list(database.auth_credentials.find()))
    with pytest.raises(DomainError) as failure:
        create_local_user(database, EMAIL, "Duplicate", PASSWORD, password_hasher=cheap_hash)
    assert failure.value.code == "IDENTITY_ALREADY_EXISTS"


def test_email_size_is_bounded_to_current_mongodb_identity_schema(database):
    with pytest.raises(ValueError):
        create_local_user(database, "a" * 257 + "@example.test", "Synthetic", PASSWORD,
                          password_hasher=cheap_hash)
    assert database.users.count_documents({}) == 0


def test_login_authenticate_csrf_session_fixation_and_no_plaintext(database, account, service):
    response = login(service, request_id="req-test-login-0001")
    assert response["actor"] == account
    assert response["expires_at"] == NOW + SESSION_LIFETIME
    session = service.authenticate(response["token"], now=NOW)
    assert session["user_id"] == ObjectId(account["id"])
    service.check_csrf(session, response["csrf_token"])
    stored = repr({name: list(database[name].find()) for name in database.list_collection_names()})
    for secret in (response["token"], response["csrf_token"], PASSWORD, "loopback-peer"):
        assert secret not in stored
    assert response["token"] not in session and response["csrf_token"] not in session
    next_response = login(service, old_token=response["token"])
    assert response["token"] != next_response["token"]
    with pytest.raises(DomainError) as failure:
        service.authenticate(response["token"], now=NOW)
    assert failure.value.status == 401
    service.authenticate(next_response["token"], now=NOW)


@pytest.mark.parametrize("csrf", [None, "", "x" * 43, "x" * 10000])
def test_csrf_missing_wrong_or_oversize_is_denied(database, account, service, csrf):
    response = login(service)
    session = service.authenticate(response["token"], now=NOW)
    with pytest.raises(DomainError) as failure:
        service.check_csrf(session, csrf)
    assert failure.value.status == 403
    assert failure.value.code == "CSRF_INVALID"


def test_unknown_user_and_disabled_account_are_generic_and_always_verify(database, account):
    calls = []

    def verifier(password, encoded):
        calls.append((password, encoded))
        return cheap_hash(password) == encoded

    service = AuthService(database, password_verifier=verifier)
    database.users.update_one({"_id": ObjectId(account["id"])}, {"$set": {"status": "DISABLED"}})
    for email, password in ((EMAIL, PASSWORD), ("missing@example.test", PASSWORD),
                            ("invalid", PASSWORD), (EMAIL, "x" * 1025), (EMAIL, "\ud800")):
        with pytest.raises(DomainError) as failure:
            service.login(email, password, "peer", now=NOW)
        assert (failure.value.status, failure.value.code, failure.value.message) == (
            401, "INVALID_CREDENTIALS", "Invalid credentials")
    assert len(calls) == 5
    assert calls[1][1].startswith("scrypt$")  # Unknown identity still gets dummy KDF.
    assert database.auth_sessions.count_documents({}) == 0


def test_pair_limit_runs_before_password_hash_and_resets_after_window(database, account):
    calls = []
    service = AuthService(database, password_verifier=lambda password, encoded: calls.append(1) or False)
    for _ in range(LOGIN_PAIR_LIMIT):
        with pytest.raises(DomainError) as failure:
            service.login(EMAIL, "incorrect", "one-peer", now=NOW)
        assert failure.value.status == 401
    with pytest.raises(DomainError) as failure:
        service.login(EMAIL, "incorrect", "one-peer", now=NOW)
    assert failure.value.status == 429
    assert len(calls) == LOGIN_PAIR_LIMIT
    assert max(row["attempts"] for row in database.auth_throttles.find()) <= LOGIN_PEER_LIMIT
    with pytest.raises(DomainError) as failure:
        service.login(EMAIL, "incorrect", "one-peer", now=NOW + timedelta(minutes=5))
    assert failure.value.status == 401
    assert len(calls) == LOGIN_PAIR_LIMIT + 1


def test_rotating_peers_cannot_bypass_identity_limit(database, account, service):
    for index in range(LOGIN_IDENTITY_LIMIT):
        with pytest.raises(DomainError) as failure:
            service.login(EMAIL, "incorrect", f"peer-{index}", now=NOW)
        assert failure.value.status == 401
    with pytest.raises(DomainError) as failure:
        service.login(EMAIL.upper(), PASSWORD, "another-peer", now=NOW)
    assert failure.value.status == 429


def test_rotating_identities_cannot_bypass_peer_limit(database, service):
    for index in range(LOGIN_PEER_LIMIT):
        with pytest.raises(DomainError) as failure:
            service.login(f"missing-{index}@example.test", PASSWORD, "one-peer", now=NOW)
        assert failure.value.status == 401
    with pytest.raises(DomainError) as failure:
        service.login("last@example.test", PASSWORD, "one-peer", now=NOW)
    assert failure.value.status == 429


@pytest.mark.parametrize("change", ["disable_user", "disable_credential", "rotate_password", "remove_credential"])
def test_current_account_or_credential_change_invalidates_existing_session(database, account, service, change):
    token = login(service)["token"]
    identifier = ObjectId(account["id"])
    if change == "disable_user":
        database.users.update_one({"_id": identifier}, {"$set": {"status": "DISABLED"}})
    elif change == "disable_credential":
        database.auth_credentials.update_one({"user_id": identifier}, {"$set": {"status": "DISABLED"}})
    elif change == "rotate_password":
        database.auth_credentials.update_one({"user_id": identifier}, {"$inc": {"revision": 1}})
    else:
        database.auth_credentials.delete_one({"user_id": identifier})
    with pytest.raises(DomainError) as failure:
        service.authenticate(token, now=NOW)
    assert failure.value.status == 401


def test_absolute_expiry_without_ttl_and_idle_expiry_and_refresh(database, account, service):
    token = login(service)["token"]
    for hours in range(8):
        for minutes in (0, 20, 40):
            instant = NOW + timedelta(hours=hours, minutes=minutes)
            service.authenticate(token, now=instant)
    with pytest.raises(DomainError) as failure:
        service.authenticate(token, now=NOW + SESSION_LIFETIME)
    assert failure.value.status == 401
    assert database.auth_sessions.count_documents({}) == 1  # TTL was not necessary.
    idle_token = login(service)["token"]
    with pytest.raises(DomainError) as failure:
        service.authenticate(idle_token, now=NOW + timedelta(minutes=30))
    assert failure.value.status == 401


def test_logout_idempotent_and_safe_audit(database, account, service):
    response = login(service, request_id="req-test-audit-0001")
    service.revoke(response["token"], now=NOW, request_id="req-test-audit-0002")
    service.revoke(response["token"], now=NOW)
    with pytest.raises(DomainError):
        service.authenticate(response["token"], now=NOW)
    events = list(database.audit_events.find())
    assert [event["action"] for event in events] == ["AUTH_LOGIN_SUCCEEDED", "AUTH_LOGOUT"]
    assert events[0]["correlation_id"] == "req-test-audit-0001"
    serialized = repr(events)
    for secret in (EMAIL, PASSWORD, "loopback-peer", response["token"], response["csrf_token"]):
        assert secret not in serialized
    assert all(event["metadata_allowlist"] == {} for event in events)


def test_current_membership_capabilities_not_session_claims(database, account, service):
    member_id, workspace_id = add_membership(database, account, roles=["STUDENT"])
    token = login(service)["token"]
    database.memberships.update_one({"_id": member_id}, {"$set": {"roles": ["LECTURER", "OPERATOR"]}})
    actor = service.actor(service.authenticate(token, now=NOW)["user_id"], now=NOW)
    assert actor["memberships"] == [
        {"workspace_id": str(workspace_id), "role": role, "capabilities": sorted(ROLE_CAPABILITIES[role])}
        for role in ("LECTURER", "OPERATOR")
    ]
    database.memberships.update_one({"_id": member_id}, {"$set": {"status": "REVOKED"}})
    assert service.actor(ObjectId(account["id"]), now=NOW)["memberships"] == []


def test_system_admin_does_not_inherit_academic_memberships(database, account, service):
    database.users.update_one({"_id": ObjectId(account["id"])}, {"$set": {"system_roles": ["ADMIN"]}})
    assert login(service)["actor"]["memberships"] == []
    assert service.list_workspaces(ObjectId(account["id"]), now=NOW) == []


def test_workspaces_are_filtered_current_status_time_and_membership(database, account, service):
    _, valid_workspace = add_membership(database, account)
    add_membership(database, account, status="REVOKED")
    add_membership(database, account, workspace_status="ARCHIVED")
    add_membership(database, account, valid_from=NOW + timedelta(seconds=1))
    add_membership(database, account, valid_until=NOW)
    unrelated_account = {"id": str(ObjectId())}
    add_membership(database, unrelated_account)
    workspaces = service.list_workspaces(ObjectId(account["id"]), now=NOW)
    assert len(workspaces) == 1
    assert workspaces[0]["id"] == str(valid_workspace)
    assert set(workspaces[0]) == {"id", "key", "name", "status"}


@pytest.mark.parametrize("token", [None, "", "x" * 42, "x" * 44, "x" * 10000, ";" * 43])
def test_malformed_session_is_generic(service, token):
    with pytest.raises(DomainError) as failure:
        service.authenticate(token, now=NOW)
    assert failure.value.status == 401


def test_default_bootstrap_hasher_is_actually_scrypt(database):
    actor = create_local_user(database, EMAIL, "Test owner", PASSWORD, now=NOW)
    credential = database.auth_credentials.find_one({"user_id": ObjectId(actor["id"])})
    assert credential["password_hash"].startswith("scrypt$n=131072,r=8,p=1$")
    response = AuthService(database).login(EMAIL, PASSWORD, "peer", now=NOW)
    assert response["actor"]["id"] == actor["id"]


def test_oversized_membership_set_is_rejected_not_silently_truncated(database, account, service):
    for _ in range(201):
        add_membership(database, account)
    with pytest.raises(DomainError) as failure:
        login(service)
    assert failure.value.code == "MEMBERSHIP_LIMIT_EXCEEDED"
    assert database.auth_sessions.count_documents({}) == 0


def test_untrusted_request_id_is_replaced_by_safe_identifier(database, account, service):
    login(service, request_id="secret\nunsafe-user-text")
    event = database.audit_events.find_one()
    assert event["correlation_id"].startswith("req-")
    assert "secret" not in repr(event)
