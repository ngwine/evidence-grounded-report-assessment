"""Migration 002 catalog: local credentials/sessions and rubric lifecycle.

Do not modify migration 001's locked catalog to add runtime collections.
Cross-collection references, ownership and immutable publication are enforced
by application services/transactions as well as these BSON shape validators.
"""

from __future__ import annotations

from typing import Any

from .migrations import apply_migration
from .schema import _COMMON, _enum, _text


HASH = {"bsonType": "string", "pattern": "^[0-9a-f]{64}$"}
OID = {"bsonType": "objectId"}
DATE = {"bsonType": "date"}
NULL_ID = {"bsonType": ["objectId", "null"]}


def record(fields: dict[str, Any], *, immutable: bool = False) -> dict[str, Any]:
    common = {name: spec for name, spec in _COMMON.items()
              if not immutable or name not in {"updated_at", "updated_by", "revision"}}
    return {"$jsonSchema": {"bsonType": "object", "additionalProperties": False,
                            "required": sorted({*common, *fields}),
                            "properties": {**common, **fields}}}


VALIDATORS_V2 = {
    "auth_credentials": record({
        "user_id": OID, "password_hash": {"bsonType": "string", "maxLength": 512},
        "status": _enum("ACTIVE", "DISABLED"),
    }),
    "auth_sessions": record({
        "user_id": OID, "token_sha256": HASH, "csrf_sha256": HASH,
        "credential_revision": {"bsonType": "int", "minimum": 1},
        "last_seen_at": DATE, "expires_at": DATE, "revoked_at": {"bsonType": ["date", "null"]},
    }),
    "auth_throttles": record({
        "_id": HASH, "attempts": {"bsonType": "int", "minimum": 0, "maximum": 100},
        "expires_at": DATE,
    }),
    "audit_events": record({
        "event_id": _text(), "workspace_id": NULL_ID, "actor_id": NULL_ID,
        "actor_type": _enum("USER", "SYSTEM"), "action": _text(),
        "resource_type": _text(), "resource_id": NULL_ID,
        "outcome": _enum("ALLOW", "DENY", "ERROR"),
        "reason_code": {"bsonType": ["string", "null"]},
        "before_revision": {"bsonType": ["int", "null"]},
        "after_revision": {"bsonType": ["int", "null"]},
        "correlation_id": _text(), "occurred_at": DATE,
        "metadata_allowlist": {"bsonType": "object", "maxProperties": 0},
    }, immutable=True),
    "rubrics": record({
        "workspace_id": OID, "rubric_key": {**_text(), "maxLength": 128},
        "title": {**_text(), "maxLength": 500}, "current_version_id": OID,
        "lifecycle_state": _enum("ACTIVE", "ARCHIVED", "TOMBSTONED"),
        "version_counter": {"bsonType": "int", "minimum": 1},
    }),
    "rubric_versions": record({
        "workspace_id": OID, "rubric_id": OID,
        "version_no": {"bsonType": "int", "minimum": 1},
        "status": _enum("DRAFT", "PUBLISHED", "RETIRED"),
        "definition": {"bsonType": "object"}, "rubric_sha256": HASH,
        "compiled": {"bsonType": ["object", "null"]},
        "compiled_id": {"bsonType": ["string", "null"]},
        "compiled_sha256": {"bsonType": ["string", "null"], "pattern": "^[0-9a-f]{64}$"},
        "compiler_version": {"bsonType": ["string", "null"]},
        "published_at": {"bsonType": ["date", "null"]}, "published_by": NULL_ID,
    }),
    "rubric_operations": record({
        "workspace_id": OID, "actor_id": OID, "operation_key": _text(),
        "idempotency_key": {**_text(), "maxLength": 128}, "request_sha256": HASH,
        "response": {"bsonType": "object"}, "status": _enum("SUCCEEDED"),
    }, immutable=True),
}

INDEXES_V2 = {
    "auth_credentials": [{"key": {"user_id": 1}, "unique": True, "name": "uq_auth_user"}],
    "auth_sessions": [
        {"key": {"token_sha256": 1}, "unique": True, "name": "uq_auth_session"},
        {"key": {"expires_at": 1}, "expireAfterSeconds": 0, "name": "ttl_auth_session"},
        {"key": {"user_id": 1, "revoked_at": 1}, "name": "ix_auth_user_revoke"},
    ],
    "auth_throttles": [{"key": {"expires_at": 1}, "expireAfterSeconds": 0, "name": "ttl_auth_throttle"}],
    "audit_events": [
        {"key": {"event_id": 1}, "unique": True, "name": "uq_audit_event"},
        {"key": {"workspace_id": 1, "occurred_at": -1, "_id": 1}, "name": "ix_audit_scope_time"},
    ],
    "rubrics": [{"key": {"workspace_id": 1, "rubric_key": 1}, "unique": True, "name": "uq_rubric_key"}],
    "rubric_versions": [{"key": {"rubric_id": 1, "version_no": 1}, "unique": True, "name": "uq_rubric_version"}],
    "rubric_operations": [{"key": {"workspace_id": 1, "actor_id": 1, "operation_key": 1, "idempotency_key": 1},
                           "unique": True, "name": "uq_rubric_operation"}],
}


def apply_schema_v2(database, *, code_commit: str, applied_by: str):
    return apply_migration(
        database, code_commit=code_commit, applied_by=applied_by,
        migration_id="002-local-auth-and-rubric-lifecycle-v1",
        validators=VALIDATORS_V2, indexes=INDEXES_V2,
        description="Server-side local sessions, safe audit and immutable rubric publication",
    )
