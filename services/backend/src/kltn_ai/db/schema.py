"""Executable MongoDB identity/queue schema baseline; not the entire dictionary.

Validators enforce document shape only. Authorization, immutable versions,
cross-collection references and retention still belong to repositories.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def _text() -> dict[str, Any]:
    return {"bsonType": "string", "minLength": 1, "maxLength": 256}


def _enum(*values: str) -> dict[str, Any]:
    return {"bsonType": "string", "enum": list(values)}


def _array(item: dict[str, Any], *, minimum: int = 0) -> dict[str, Any]:
    return {"bsonType": "array", "items": item, "minItems": minimum,
            "maxItems": 100, "uniqueItems": True}


_COMMON = {
    "_id": {"bsonType": "objectId"},
    "schema_version": {"bsonType": "int", "enum": [1]},
    "created_at": {"bsonType": "date"},
    "created_by": {"bsonType": ["objectId", "null"]},
    "updated_at": {"bsonType": "date"},
    "updated_by": {"bsonType": ["objectId", "null"]},
    "revision": {"bsonType": "int", "minimum": 1},
}


def _schema(fields: dict[str, Any], *, optional: tuple[str, ...] = ()) -> dict[str, Any]:
    properties = {**deepcopy(_COMMON), **fields}
    return {"$jsonSchema": {
        "bsonType": "object", "additionalProperties": False,
        "required": sorted(set(properties) - set(optional)), "properties": properties,
    }}


VALIDATORS = {
    "users": _schema({
        "email_normalized": {**_text(), "pattern": r"^[^\s@]+@[^\s@]+$"},
        "display_name": _text(), "system_roles": _array(_enum("ADMIN")),
        "status": _enum("ACTIVE", "DISABLED", "DELETED"),
        "auth_subject": {"bsonType": ["string", "null"], "minLength": 1},
    }, optional=("auth_subject",)),
    "workspaces": _schema({
        "workspace_key": _text(), "kind": _enum("COURSE", "RESEARCH"),
        "name": _text(), "status": _enum("ACTIVE", "ARCHIVED"),
        "default_purpose": _text(),
    }),
    "memberships": _schema({
        "workspace_id": {"bsonType": "objectId"}, "user_id": {"bsonType": "objectId"},
        "roles": _array(_enum("STUDENT", "LECTURER", "OPERATOR", "DATA_APPROVER"), minimum=1),
        "status": _enum("ACTIVE", "REVOKED"),
        "valid_from": {"bsonType": ["date", "null"]},
        "valid_until": {"bsonType": ["date", "null"]},
    }),
    "jobs": _schema({
        "workspace_id": {"bsonType": "objectId"},
        "job_type": _enum("PARSE", "INDEX", "ANALYZE", "DELETE"),
        "resource_ref": {
            "bsonType": "object", "additionalProperties": False,
            "required": ["type", "id", "version_id"],
            "properties": {
                "type": _enum("DOCUMENT", "INDEX_GENERATION", "ANALYSIS_RUN"),
                "id": {"bsonType": "objectId"}, "version_id": {"bsonType": "objectId"},
            },
        },
        "config_ref": {
            "bsonType": ["object", "null"], "additionalProperties": False,
            "required": ["id", "version"],
            "properties": {"id": {"bsonType": "objectId"},
                           "version": {"bsonType": "int", "minimum": 1}},
        },
        "idempotency_scope": {**_text(), "maxLength": 128},
        "idempotency_key": {**_text(), "maxLength": 128},
        "correlation_id": {**_text(), "maxLength": 128},
        "state": _enum("QUEUED", "CLAIMED", "RUNNING", "SUCCEEDED", "FAILED_FINAL", "CANCELLED"),
        "priority": {"bsonType": "int", "minimum": -10, "maximum": 10},
        "available_at": {"bsonType": "date"},
        "lease_owner": {"bsonType": ["string", "null"], "minLength": 1, "maxLength": 128},
        "lease_expires_at": {"bsonType": ["date", "null"]},
        "heartbeat_at": {"bsonType": ["date", "null"]},
        "attempt": {"bsonType": "int", "minimum": 0},
        "max_attempts": {"bsonType": "int", "minimum": 1, "maximum": 10},
        "progress": {"bsonType": "object", "additionalProperties": False,
                     "required": ["step"], "properties": {"step": _text()}},
        "error_code": {"bsonType": ["string", "null"], "pattern": r"^[A-Z][A-Z0-9_]{0,63}$"},
        "finished_at": {"bsonType": "date"},
    }, optional=("finished_at",)),
}

# These names agree with MongoJobQueue.ensure_indexes(). Index creation is
# migration-only, never a permission granted to API or worker credentials.
INDEXES: dict[str, list[dict[str, Any]]] = {
    "users": [
        {"key": {"email_normalized": 1}, "name": "uq_user_email", "unique": True},
        {"key": {"auth_subject": 1}, "name": "uq_user_subject", "unique": True,
         "partialFilterExpression": {"auth_subject": {"$type": "string"}}},
    ],
    "workspaces": [
        {"key": {"workspace_key": 1}, "name": "uq_workspace_key", "unique": True},
    ],
    "memberships": [
        {"key": {"workspace_id": 1, "user_id": 1}, "name": "uq_membership", "unique": True},
        {"key": {"user_id": 1, "status": 1}, "name": "ix_membership_user_status"},
    ],
    "jobs": [
        {"key": {"idempotency_scope": 1, "idempotency_key": 1},
         "name": "uq_job_idempotency", "unique": True},
        {"key": {"state": 1, "available_at": 1, "priority": -1, "created_at": 1},
         "name": "ix_job_claim"},
        {"key": {"state": 1, "lease_expires_at": 1}, "name": "ix_job_expired_lease"},
        {"key": {"workspace_id": 1, "resource_ref.id": 1, "created_at": -1},
         "name": "ix_job_workspace_resource"},
    ],
}
