"""Safe, bounded choices for creating documents under existing approvals.

This is a discovery aid, not an approval or reservation. DocumentService checks
the authoritative approval again when the selected bytes are uploaded.
"""

from __future__ import annotations

from datetime import datetime
import re
from typing import Any

from bson import ObjectId

from .access import AccessPolicy, object_id
from .documents import DocumentService
from .errors import DomainError


RIGHTS = {"LICENSE", "CONSENT", "RESEARCH_USE_STATEMENT", "INTERNAL_APPROVAL"}
CLASSIFICATIONS = {"RESTRICTED", "INTERNAL", "PUBLIC_LICENSED"}


class GovernanceOptionsService:
    def __init__(self, database: Any, documents: DocumentService):
        self.db = database
        self.documents = documents
        self.policy = AccessPolicy(database)

    @staticmethod
    def _safe_record(row: dict[str, Any]) -> bool:
        """Reject malformed legacy records; never echo free-form metadata."""
        purposes = row.get("allowed_purposes")
        return (row.get("schema_version") == 1
            and type(row.get("record_version")) is int and row["record_version"] >= 1
            and isinstance(row.get("resource_id"), ObjectId)
            and isinstance(row.get("rights_basis"), str) and row["rights_basis"] in RIGHTS
            and isinstance(row.get("data_class"), str) and row["data_class"] in CLASSIFICATIONS
            and isinstance(row.get("approver_id"), ObjectId)
            and isinstance(row.get("approved_at"), datetime)
            and all(row.get(field) is None or isinstance(row[field], datetime)
                    for field in ("valid_from", "valid_until"))
            and isinstance(row.get("retention_policy"), dict)
            and (row["retention_policy"].get("expires_at") is None
                 or isinstance(row["retention_policy"]["expires_at"], datetime))
            and isinstance(row.get("anonymization"), dict)
            and isinstance(purposes, list) and 0 < len(purposes) <= 100
            and len(set(item for item in purposes if isinstance(item, str))) == len(purposes)
            and all(isinstance(item, str) and re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", item)
                    for item in purposes))

    @staticmethod
    def _dto(row: dict[str, Any]) -> dict[str, Any]:
        # Governance data_owner, rights_evidence and other free-form fields can
        # contain names, contact details or private references. Names are derived
        # solely from public enum values and an opaque identifier.
        return {"id": str(row["_id"]),
            "name": f"{row['rights_basis'].replace('_', ' ').title()} · {row['data_class'].replace('_', ' ').title()}",
            "rights_basis": row["rights_basis"], "allowed_purposes": row["allowed_purposes"],
            "valid_until": row.get("valid_until"), "resource_id": str(row["resource_id"]),
            "classification": row["data_class"]}

    def list(self, actor_id: ObjectId, workspace_id: str | ObjectId, *, kind: str,
             limit: int = 25, cursor: str | None = None) -> dict[str, Any]:
        workspace_id = object_id(workspace_id)
        # Check current membership before disclosing even pagination/record state.
        self.policy.require(actor_id, workspace_id, "workspace.read")
        if kind not in {"REPORT", "CORPUS_SOURCE"}:
            raise DomainError(422, "INVALID_REQUEST", "Invalid document kind")
        workspace = self.policy.require(actor_id, workspace_id,
            "report.upload" if kind == "REPORT" else "source.upload")
        if kind == "CORPUS_SOURCE":
            self.policy.require(actor_id, workspace_id, "source.read")
        if (type(limit) is not int or not 1 <= limit <= 100
                or cursor is not None and (not isinstance(cursor, str) or not ObjectId.is_valid(cursor))):
            raise DomainError(400, "INVALID_PAGINATION", "Invalid pagination")
        query: dict[str, Any] = {"workspace_id": workspace_id,
            "resource_type": "DOCUMENT", "status": "APPROVED"}
        if cursor is not None:
            query["_id"] = {"$gt": ObjectId(cursor)}
        scan_limit = min(1000, max(100, limit * 10))
        rows = list(self.db.governance_records.find(query).sort("_id", 1).limit(scan_limit + 1))
        items: list[dict[str, Any]] = []
        last_scanned = None
        for row in rows[:scan_limit]:
            last_scanned = str(row["_id"])
            if not self._safe_record(row):
                continue
            # A resource already bound to any document is not a new upload
            # choice, including archived/foreign documents and prior approvals.
            if self.db.documents.find_one({"_id": row["resource_id"]}, {"_id": 1}):
                continue
            try:
                current = self.documents.require_governance(workspace, {"_id": row["resource_id"],
                    "current_governance_record_id": row["_id"]})
            except DomainError as error:
                if error.code not in {"GOVERNANCE_NOT_APPROVED", "RESOURCE_NOT_FOUND"}:
                    raise
                continue
            # Re-read through the upload gate can observe a changed record.
            if not self._safe_record(current):
                continue
            items.append(self._dto(current))
            if len(items) > limit:
                return {"items": items[:limit], "page": {"limit": limit,
                    "has_more": True, "next_cursor": items[limit - 1]["id"]}}
        has_more = len(rows) > scan_limit
        return {"items": items, "page": {"limit": limit, "has_more": has_more,
            "next_cursor": last_scanned if has_more else None}}
