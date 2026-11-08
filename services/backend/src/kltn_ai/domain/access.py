"""Current authoritative workspace/ownership policy, reused by API and worker."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from pymongo.database import Database

from .errors import DomainError


ROLE_CAPABILITIES = {
    "STUDENT": frozenset({"workspace.read", "report.read", "report.upload", "publication.read"}),
    "LECTURER": frozenset({"workspace.read", "report.read", "report.upload", "source.read",
                           "source.upload", "rubric.manage", "run.create", "run.read",
                           "review.create", "publication.read", "publication.create", "graph.read"}),
    # Non-academic roles do not inherit lecturer/student permissions.
    "OPERATOR": frozenset({"workspace.read"}),
    "DATA_APPROVER": frozenset({"workspace.read", "governance.approve"}),
}


def object_id(value: str | ObjectId) -> ObjectId:
    if isinstance(value, ObjectId):
        return value
    if not isinstance(value, str) or not ObjectId.is_valid(value):
        raise DomainError(404, "RESOURCE_NOT_FOUND", "Resource not found")
    return ObjectId(value)


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class AccessPolicy:
    def __init__(self, database: Database[dict[str, Any]]):
        self.db = database

    def require(
        self, actor_id: ObjectId, workspace_id: str | ObjectId, capability: str,
        *, owner_id: ObjectId | None = None, now: datetime | None = None, session: Any = None,
    ) -> dict[str, Any]:
        instant = now or datetime.now(timezone.utc)
        workspace = object_id(workspace_id)
        options = {"session": session} if session is not None else {}
        user = self.db.users.find_one({"_id": actor_id, "status": "ACTIVE"}, {"_id": 1}, **options)
        if user is None:
            raise DomainError(401, "AUTHENTICATION_REQUIRED", "Authentication required")
        membership = self.db.memberships.find_one({
            "workspace_id": workspace, "user_id": actor_id, "status": "ACTIVE",
        }, **options)
        if (membership is None
                or membership.get("valid_from") is not None and _utc(membership["valid_from"]) > instant
                or membership.get("valid_until") is not None and _utc(membership["valid_until"]) <= instant):
            raise DomainError(404, "RESOURCE_NOT_FOUND", "Resource not found")
        record = self.db.workspaces.find_one({"_id": workspace, "status": "ACTIVE"}, **options)
        if record is None:
            raise DomainError(404, "RESOURCE_NOT_FOUND", "Resource not found")
        roles = membership.get("roles", [])
        if not any(capability in ROLE_CAPABILITIES.get(role, ()) for role in roles):
            raise DomainError(403, "FORBIDDEN", "Capability not allowed")
        if owner_id is not None and "LECTURER" not in roles and owner_id != actor_id:
            raise DomainError(404, "RESOURCE_NOT_FOUND", "Resource not found")
        return record
