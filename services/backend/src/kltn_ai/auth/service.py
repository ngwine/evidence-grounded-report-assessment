"""Mongo-backed local authentication, independent of HTTP cookie transport.

Use only through the loopback deployment's origin/CSRF protected HTTP adapter.
Database validators, unique indexes and TTL indexes are migration concerns.
Expiry is checked here even when MongoDB's asynchronous TTL sweep has not run.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from ..domain.access import ROLE_CAPABILITIES
from ..domain.audit import append_event
from ..domain.errors import DomainError


_HASH_PREFIX = "scrypt$n=131072,r=8,p=1"
_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43}$")
_DUMMY_HASH = _HASH_PREFIX + "$" + base64.b64encode(bytes(16)).decode() + "$" + base64.b64encode(bytes(32)).decode()
SESSION_LIFETIME = timedelta(hours=8)
SESSION_IDLE = timedelta(minutes=30)
THROTTLE_WINDOW_SECONDS = 300
LOGIN_PAIR_LIMIT = 10
LOGIN_PEER_LIMIT = 100
LOGIN_IDENTITY_LIMIT = 20


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _instant(now: datetime | None) -> datetime:
    return _utc(now) if now is not None else datetime.now(timezone.utc)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _common(now: datetime, actor: ObjectId | None = None) -> dict[str, Any]:
    return {"schema_version": 1, "created_at": now, "created_by": actor,
            "updated_at": now, "updated_by": actor, "revision": 1}


def _password_valid(value: Any) -> bool:
    if not isinstance(value, str) or not 1 <= len(value) <= 1024 or "\x00" in value:
        return False
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def hash_password(password: str) -> str:
    """One fixed scrypt cost; database text cannot request arbitrary parameters."""
    if not _password_valid(password):
        raise ValueError("Password must contain 1 to 1024 non-NUL characters")
    salt = secrets.token_bytes(16)
    derived = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**17, r=8,
                             p=1, dklen=32, maxmem=256 * 1024 * 1024)
    return "$".join((_HASH_PREFIX, base64.b64encode(salt).decode("ascii"),
                     base64.b64encode(derived).decode("ascii")))


def verify_password(password: str, encoded: str) -> bool:
    if not _password_valid(password) or not isinstance(encoded, str):
        return False
    try:
        algorithm, parameters, salt_text, expected_text = encoded.split("$")
        if algorithm + "$" + parameters != _HASH_PREFIX:
            return False
        salt = base64.b64decode(salt_text, validate=True)
        expected = base64.b64decode(expected_text, validate=True)
        if len(salt) != 16 or len(expected) != 32:
            return False
    except (ValueError, TypeError):
        return False
    actual = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**17, r=8,
                            p=1, dklen=32, maxmem=256 * 1024 * 1024)
    return hmac.compare_digest(actual, expected)


def _email(value: Any) -> str | None:
    if not isinstance(value, str) or not 3 <= len(value) <= 256:
        return None
    normalized = value.strip().lower()
    try:
        normalized.encode("utf-8")
    except UnicodeEncodeError:
        return None
    if re.fullmatch(r"[^\s@]+@[^\s@]+", normalized) is None:
        return None
    return normalized


def create_local_user(
    database: Database[dict[str, Any]], email: str, display_name: str,
    password: str, created_by: ObjectId | None = None, *,
    now: datetime | None = None, session: Any = None,
    password_hasher: Callable[[str], str] = hash_password,
) -> dict[str, Any]:
    """Operator-only bootstrap, not self-registration or a public endpoint.

    The operator should supply its majority transaction session for the two
    inserts. Without one, an interrupted creation is fail-closed (no working
    account until the credential exists), but requires operator repair.
    """
    normalized = _email(email)
    if normalized is None or not isinstance(display_name, str) or not 1 <= len(display_name.strip()) <= 200:
        raise ValueError("Valid email and display name are required")
    if not _password_valid(password) or len(password) < 15:
        raise ValueError("Bootstrap password must contain 15 to 1024 non-NUL characters")
    instant = _instant(now)
    identifier = ObjectId()
    user = {"_id": identifier, **_common(instant, created_by),
            "email_normalized": normalized, "display_name": display_name.strip(),
            "system_roles": [], "status": "ACTIVE"}
    credential = {"_id": ObjectId(), **_common(instant, created_by),
                  "user_id": identifier, "password_hash": password_hasher(password),
                  "status": "ACTIVE"}
    options = {"session": session} if session is not None else {}
    try:
        database.users.insert_one(user, **options)
        database.auth_credentials.insert_one(credential, **options)
    except DuplicateKeyError as error:
        raise DomainError(409, "IDENTITY_ALREADY_EXISTS", "Identity already exists") from error
    return {"id": str(identifier), "display_name": user["display_name"], "memberships": []}


class AuthService:
    def __init__(self, database: Database[dict[str, Any]], *,
                 password_verifier: Callable[[str, str], bool] = verify_password):
        self.db = database
        self._verify = password_verifier

    def _audit(self, event_type: str, actor: ObjectId | None = None,
               request_id: str | None = None) -> None:
        # Deliberately do not store email, network peer, password, session/CSRF
        # token, supplied hash or arbitrary exception strings in an audit row.
        safe_request_id = (request_id if isinstance(request_id, str)
                           and re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", request_id)
                           else "req-" + secrets.token_hex(16))
        append_event(self.db, actor_id=actor, workspace_id=None,
                     action=event_type, resource_type="AUTH_SESSION", resource_id=None,
                     request_id=safe_request_id,
                     outcome="DENY" if event_type in {"AUTH_RATE_LIMITED", "AUTH_LOGIN_REJECTED"} else "ALLOW")

    def _throttle(self, identity: str, peer: str, now: datetime, request_id: str | None) -> None:
        bucket = int(now.timestamp()) // THROTTLE_WINDOW_SECONDS
        expires = datetime.fromtimestamp((bucket + 1) * THROTTLE_WINDOW_SECONDS, timezone.utc)
        for namespace, value, limit in (("peer", peer, LOGIN_PEER_LIMIT),
                                         ("identity", identity, LOGIN_IDENTITY_LIMIT),
                                         ("pair", identity + "\x00" + peer, LOGIN_PAIR_LIMIT)):
            key = _digest(f"auth/{namespace}/{bucket}/{value}")
            try:
                self.db.auth_throttles.insert_one({"_id": key, **_common(now),
                                                   "attempts": 0, "expires_at": expires})
            except DuplicateKeyError:
                pass
            record = self.db.auth_throttles.find_one_and_update(
                {"_id": key, "attempts": {"$lt": limit}, "expires_at": {"$gt": now}},
                {"$inc": {"attempts": 1, "revision": 1}, "$set": {"updated_at": now}},
                return_document=ReturnDocument.AFTER,
            )
            if record is None:
                self._audit("AUTH_RATE_LIMITED", request_id=request_id)
                raise DomainError(429, "RATE_LIMITED", "Too many authentication attempts")

    def login(self, email: str, password: str, peer_key: str,
              old_token: str | None = None, now: datetime | None = None,
              request_id: str | None = None) -> dict[str, Any]:
        instant = _instant(now)
        normalized = _email(email)
        # Peer comes from the server socket, never a client forwarded header.
        peer = peer_key if isinstance(peer_key, str) and len(peer_key) <= 256 else "unknown"
        self._throttle(normalized or "invalid", peer, instant, request_id)
        user = self.db.users.find_one({"email_normalized": normalized}) if normalized else None
        credential = self.db.auth_credentials.find_one({"user_id": user["_id"]}) if user else None
        encoded = credential["password_hash"] if credential else _DUMMY_HASH
        valid_input = _password_valid(password)
        password_ok = self._verify(password if valid_input else "invalid-input", encoded)
        if (not password_ok or not valid_input or user is None or user.get("status") != "ACTIVE"
                or credential is None or credential.get("status") != "ACTIVE"):
            self._audit("AUTH_LOGIN_REJECTED", request_id=request_id)
            raise DomainError(401, "INVALID_CREDENTIALS", "Invalid credentials")
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        expires_at = instant + SESSION_LIFETIME
        session = {"_id": ObjectId(), **_common(instant, user["_id"]),
                   "user_id": user["_id"], "token_sha256": _digest(token),
                   "csrf_sha256": _digest(csrf), "credential_revision": credential["revision"],
                   "last_seen_at": instant, "expires_at": expires_at, "revoked_at": None}
        actor = self.actor(user["_id"], now=instant)
        if old_token:
            self.revoke(old_token, now=instant, request_id=request_id)
        self.db.auth_sessions.insert_one(session)
        self._audit("AUTH_LOGIN_SUCCEEDED", user["_id"], request_id)
        return {"token": token, "csrf_token": csrf, "expires_at": expires_at,
                "actor": actor}

    def authenticate(self, token: str | None, now: datetime | None = None) -> dict[str, Any]:
        instant = _instant(now)
        error = DomainError(401, "AUTHENTICATION_REQUIRED", "Authentication required")
        if not isinstance(token, str) or _TOKEN_PATTERN.fullmatch(token) is None:
            raise error
        session = self.db.auth_sessions.find_one({"token_sha256": _digest(token), "revoked_at": None})
        if (session is None or _utc(session["expires_at"]) <= instant
                or _utc(session["last_seen_at"]) + SESSION_IDLE <= instant):
            raise error
        user = self.db.users.find_one({"_id": session["user_id"], "status": "ACTIVE"}, {"_id": 1})
        credential = self.db.auth_credentials.find_one({"user_id": session["user_id"], "status": "ACTIVE"},
                                                        {"revision": 1})
        if user is None or credential is None or credential["revision"] != session["credential_revision"]:
            raise error
        updated = self.db.auth_sessions.find_one_and_update(
            {"_id": session["_id"], "revoked_at": None, "expires_at": {"$gt": instant},
             "last_seen_at": {"$gt": instant - SESSION_IDLE}},
            {"$set": {"last_seen_at": instant, "updated_at": instant}, "$inc": {"revision": 1}},
            return_document=ReturnDocument.AFTER,
        )
        if updated is None:
            raise error
        return updated

    def check_csrf(self, session: dict[str, Any], token: str | None) -> None:
        if (not isinstance(token, str) or _TOKEN_PATTERN.fullmatch(token) is None
                or not hmac.compare_digest(_digest(token), session.get("csrf_sha256", ""))):
            raise DomainError(403, "CSRF_INVALID", "CSRF validation failed")

    def revoke(self, token: str | None, now: datetime | None = None,
               request_id: str | None = None) -> None:
        if not isinstance(token, str) or _TOKEN_PATTERN.fullmatch(token) is None:
            return
        instant = _instant(now)
        record = self.db.auth_sessions.find_one_and_update(
            {"token_sha256": _digest(token), "revoked_at": None},
            {"$set": {"revoked_at": instant, "updated_at": instant}, "$inc": {"revision": 1}},
            return_document=ReturnDocument.AFTER,
        )
        if record:
            self._audit("AUTH_LOGOUT", record["user_id"], request_id)

    def _memberships(self, user_id: ObjectId, now: datetime) -> list[tuple[dict[str, Any], dict[str, Any]]]:
        result = []
        memberships = list(self.db.memberships.find({
            "user_id": user_id, "status": "ACTIVE",
            "$and": [{"$or": [{"valid_from": None}, {"valid_from": {"$lte": now}}]},
                     {"$or": [{"valid_until": None}, {"valid_until": {"$gt": now}}]}],
        }).sort("_id", 1).limit(201))
        if len(memberships) > 200:
            raise DomainError(503, "MEMBERSHIP_LIMIT_EXCEEDED", "Account requires membership review")
        for membership in memberships:
            workspace = self.db.workspaces.find_one({"_id": membership["workspace_id"], "status": "ACTIVE"})
            if workspace is not None:
                result.append((membership, workspace))
        if len(result) > 200:
            raise DomainError(503, "MEMBERSHIP_LIMIT_EXCEEDED", "Account requires membership review")
        return result

    def actor(self, user_id: ObjectId, now: datetime | None = None) -> dict[str, Any]:
        instant = _instant(now)
        user = self.db.users.find_one({"_id": user_id, "status": "ACTIVE"})
        if user is None:
            raise DomainError(401, "AUTHENTICATION_REQUIRED", "Authentication required")
        memberships = []
        for membership, workspace in self._memberships(user_id, instant):
            for role in sorted(set(membership["roles"])):
                if role in ROLE_CAPABILITIES:
                    memberships.append({"workspace_id": str(workspace["_id"]), "role": role,
                                        "capabilities": sorted(ROLE_CAPABILITIES[role])})
        if len(memberships) > 200:
            raise DomainError(503, "MEMBERSHIP_LIMIT_EXCEEDED", "Account requires membership review")
        return {"id": str(user_id), "display_name": user["display_name"], "memberships": memberships}

    def list_workspaces(self, user_id: ObjectId, now: datetime | None = None) -> list[dict[str, Any]]:
        self.actor(user_id, now=now)  # Re-check current account, no cached roles.
        return [{"id": str(workspace["_id"]), "key": workspace["workspace_key"],
                 "name": workspace["name"], "status": workspace["status"]}
                for _, workspace in self._memberships(user_id, _instant(now))]
