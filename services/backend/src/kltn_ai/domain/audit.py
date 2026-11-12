"""Append safe event identifiers, never academic text, credentials or PII."""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any
from uuid import uuid4

from bson import ObjectId
from pymongo.database import Database


def append_event(
    database: Database[dict[str, Any]], *, actor_id: ObjectId | None,
    workspace_id: ObjectId | None, action: str, resource_type: str,
    resource_id: ObjectId | None, request_id: str, outcome: str = "ALLOW",
    reason_code: str | None = None, session: Any = None,
) -> None:
    if (not re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", action)
            or not re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", resource_type)
            or not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", request_id)
            or outcome not in {"ALLOW", "DENY", "ERROR"}
            or reason_code is not None and not re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", reason_code)):
        raise ValueError("Audit fields must contain safe identifiers only")
    now = datetime.now(timezone.utc)
    database.audit_events.insert_one({
        "_id": ObjectId(), "schema_version": 1, "event_id": uuid4().hex,
        "created_at": now, "created_by": actor_id, "workspace_id": workspace_id,
        "actor_id": actor_id, "actor_type": "USER" if actor_id is not None else "SYSTEM",
        "action": action, "resource_type": resource_type, "resource_id": resource_id,
        "outcome": outcome, "reason_code": reason_code,
        "before_revision": None, "after_revision": None,
        "correlation_id": request_id, "occurred_at": now, "metadata_allowlist": {},
    }, **({"session": session} if session is not None else {}))
