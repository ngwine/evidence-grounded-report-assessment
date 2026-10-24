"""Author consent for exact private bytes, not independent dataset approval.

The uploader explicitly declares authority over their own/co-authored work and
PII review. This limited consent only permits local/demo processing for 30 days;
research/publication and third-party datasets still require separate approval.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from .access import object_id
from .audit import append_event
from .documents import (
    AUTHOR_CONSENT_PURPOSES,
    AUTHOR_CONSENT_SCOPE,
    MIME,
    DocumentService,
    _common,
    _options,
)
from .errors import DomainError
from .governance_options import GovernanceOptionsService


class UploadDeclarationService:
    def __init__(self, documents: DocumentService):
        self.documents = documents
        self.db = documents.db
        self.policy = documents.policy

    def create(self, actor_id: ObjectId, workspace_id: str | ObjectId, body: dict[str, Any],
               *, idempotency_key: str, request_id: str) -> dict[str, Any]:
        workspace_id = object_id(workspace_id)
        self.policy.require(actor_id, workspace_id, "workspace.read")
        fields = {"kind", "filename", "content_sha256", "rights_basis", "attested_authority",
                  "pii_reviewed", "internal_use_only"}
        if not isinstance(body, dict) or not fields <= body.keys() or body.keys() - fields - {"document_id"}:
            raise DomainError(422, "INVALID_DECLARATION", "Complete author consent is required")
        kind, filename, digest = body["kind"], body["filename"], body["content_sha256"]
        if (not isinstance(kind, str) or kind not in {"REPORT", "CORPUS_SOURCE"}
                or not isinstance(filename, str) or not 1 <= len(filename) <= 255
                or any(ord(character) < 32 for character in filename)
                or Path(filename).suffix.casefold() not in MIME
                or not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None
                or body["rights_basis"] != "SELF_AUTHORED"
                or any(body[field] is not True for field in (
                    "attested_authority", "pii_reviewed", "internal_use_only"))
                or not isinstance(idempotency_key, str)
                or re.fullmatch(r"[A-Za-z0-9_.:-]{16,128}", idempotency_key) is None
                or not isinstance(request_id, str)
                or re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", request_id) is None):
            raise DomainError(422, "INVALID_DECLARATION", "Complete author consent is required")
        capability = "report.upload" if kind == "REPORT" else "source.upload"
        workspace = self.policy.require(actor_id, workspace_id, capability)
        if workspace.get("default_purpose") not in AUTHOR_CONSENT_PURPOSES:
            raise DomainError(409, "DECLARATION_SCOPE_NOT_ALLOWED", "Author declaration only permits local internal use")
        existing_id = object_id(body["document_id"]) if "document_id" in body else None
        if existing_id is not None:
            _, document = self.documents._document(actor_id, workspace_id, existing_id)
            if document["kind"] != kind:
                raise DomainError(404, "RESOURCE_NOT_FOUND", "Resource not found")
        request_hash = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        # The primary-key uniqueness constraint makes parallel retries safe
        # without mutating locked migrations or creating runtime collections.
        identifier = ObjectId(hashlib.sha256(
            f"upload-declaration-v1:{workspace_id}:{actor_id}:{idempotency_key}".encode()).digest()[:12])

        def replay(record: dict[str, Any]) -> dict[str, Any]:
            evidence = record.get("rights_evidence", {})
            if (record.get("workspace_id") != workspace_id or record.get("created_by") != actor_id
                    or evidence.get("kind") != "SELF_DECLARATION"
                    or evidence.get("request_sha256") != request_hash):
                raise DomainError(409, "IDEMPOTENCY_CONFLICT", "Key belongs to another declaration")
            current_workspace = self.policy.require(actor_id, workspace_id, capability)
            if existing_id is not None:
                self.documents._document(actor_id, workspace_id, existing_id)
            self.documents.require_governance(current_workspace, {"_id": record["resource_id"],
                "current_governance_record_id": identifier})
            return {**GovernanceOptionsService._dto(record), "declaration_scope": AUTHOR_CONSENT_SCOPE,
                    "independent_approval": False}

        prior = self.db.governance_records.find_one({"_id": identifier})
        if prior is not None:
            return replay(prior)
        now = datetime.now(UTC)
        expires = now + timedelta(days=30)
        record = {"_id": identifier, **_common(actor_id, now), "workspace_id": workspace_id,
            "resource_type": "DOCUMENT", "resource_id": existing_id or ObjectId(), "record_version": 1,
            "data_owner": {"kind": "UPLOADER_AUTHOR", "user_id": actor_id},
            "rights_basis": "CONSENT", "license_id": None,
            "rights_evidence": {"kind": "SELF_DECLARATION", "declaration_version": 1,
                "declaration_scope": AUTHOR_CONSENT_SCOPE, "declared_by": actor_id,
                "sha256": digest, "filename": filename, "document_kind": kind,
                "attested_authority": True, "pii_reviewed": True, "internal_use_only": True,
                "independent_approval": False, "request_sha256": request_hash},
            "allowed_purposes": [workspace["default_purpose"]], "redistribution": "PROHIBITED",
            "data_class": "RESTRICTED", "anonymization": {"required": False, "reviewed_by": actor_id},
            "retention_policy": {"expires_at": expires, "policy": "INTERNAL_USE_30_DAYS"},
            # The consent giver is the uploader, NOT an independent DATA_APPROVER.
            "approver_id": actor_id, "approved_at": now, "valid_from": now,
            "valid_until": expires, "status": "APPROVED"}
        try:
            with self.documents.transaction() as session:
                options = _options(session)
                current_workspace = self.policy.require(actor_id, workspace_id, capability, session=session)
                if current_workspace.get("default_purpose") != workspace["default_purpose"]:
                    raise DomainError(409, "DECLARATION_SCOPE_NOT_ALLOWED", "Workspace purpose changed")
                if existing_id is not None:
                    self.documents._document(actor_id, workspace_id, existing_id, session=session)
                    previous = self.db.governance_records.find_one({
                        "resource_type": "DOCUMENT", "resource_id": existing_id},
                        sort=[("record_version", -1)], **options)
                    if previous is not None:
                        if type(previous.get("record_version")) is not int or previous["record_version"] < 1:
                            raise DomainError(409, "GOVERNANCE_NOT_APPROVED", "Invalid consent lineage")
                        record["record_version"] = previous["record_version"] + 1
                self.db.governance_records.insert_one(record, **options)
                append_event(self.db, actor_id=actor_id, workspace_id=workspace_id,
                    action="UPLOAD_AUTHOR_CONSENT_DECLARED", resource_type="GOVERNANCE_RECORD",
                    resource_id=identifier, request_id=request_id, session=session)
        except DuplicateKeyError:
            prior = self.db.governance_records.find_one({"_id": identifier})
            if prior is None:
                raise DomainError(409, "REVISION_CONFLICT", "Declaration changed; retry") from None
            return replay(prior)
        stored = self.db.governance_records.find_one({"_id": identifier})
        if stored is None:
            raise DomainError(409, "REVISION_CONFLICT", "Declaration changed; retry")
        return replay(stored)
