"""Immutable private bytes and transaction-backed document upload/provenance.

Collection creation and indexes belong to maintenance migrations. The explicit
``transactional=False`` option exists only for the mongomock unit test harness;
the production default never falls back from replica-set transactions.
"""

from __future__ import annotations

import builtins
import hashlib
import json
import os
import re
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any

from bson import ObjectId
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern

from .access import AccessPolicy, object_id
from .audit import append_event
from .errors import DomainError

MAX_DOCUMENT_BYTES = 20 * 1024 * 1024
MIME = {".pdf": "application/pdf", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".txt": "text/plain", ".md": "text/markdown"}
AUTHOR_CONSENT_SCOPE = "INTERNAL_SELF_AUTHORED"
AUTHOR_CONSENT_PURPOSES = frozenset({"LOCAL_DEMO", "INTERNAL_TEST"})


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _common(actor_id: ObjectId, now: datetime) -> dict[str, Any]:
    return {"schema_version": 1, "created_at": now, "created_by": actor_id,
            "updated_at": now, "updated_by": actor_id, "revision": 1}


def _options(session: Any) -> dict[str, Any]:
    return {"session": session} if session is not None else {}


def validate_document(filename: str, payload: bytes) -> str:
    """Validate bytes without using a client filename as a storage path."""
    if (not isinstance(filename, str) or not filename or len(filename) > 255
            or any(ord(character) < 32 for character in filename)):
        raise DomainError(422, "INVALID_DOCUMENT", "Invalid document filename")
    suffix = Path(filename).suffix.casefold()
    if not isinstance(payload, bytes) or not payload:
        raise DomainError(422, "INVALID_DOCUMENT", "Document bytes are required")
    if len(payload) > MAX_DOCUMENT_BYTES:
        raise DomainError(413, "UPLOAD_TOO_LARGE", "Document exceeds upload limit")
    if suffix not in MIME:
        raise DomainError(422, "INVALID_DOCUMENT", "Expected PDF, DOCX, TXT or MD")
    if suffix == ".pdf":
        if not payload.startswith(b"%PDF-"):
            raise DomainError(422, "INVALID_DOCUMENT", "Invalid PDF signature")
    elif suffix == ".docx":
        try:
            with zipfile.ZipFile(BytesIO(payload)) as archive:
                entries = archive.infolist()
                if (len(entries) > 1000 or sum(item.file_size for item in entries) > 80 * 1024 * 1024
                        or any(item.flag_bits & 1 for item in entries)
                        or not {"word/document.xml", "[Content_Types].xml"} <= set(archive.namelist())):
                    raise ValueError("Invalid archive")
        except (OSError, ValueError, zipfile.BadZipFile):
            raise DomainError(422, "INVALID_DOCUMENT", "Invalid DOCX container") from None
    else:
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError:
            raise DomainError(422, "INVALID_DOCUMENT", "Text must use UTF-8") from None
        if "\x00" in text or not text.strip():
            raise DomainError(422, "INVALID_DOCUMENT", "Invalid text document")
    return suffix


class DocumentService:
    def __init__(self, database: Database[dict[str, Any]], private_root: Path | str,
                 *, transactional: bool = True):
        self.db = database
        self.policy = AccessPolicy(database)
        self.transactional = transactional
        root = Path(private_root).expanduser()
        if root.is_symlink():
            raise ValueError("Private storage root must not be a symlink")
        resolved = root.resolve()
        if resolved in {Path("/"), Path.home().resolve(), Path(__file__).resolve().parents[5]}:
            raise ValueError("Use a dedicated private application storage directory")
        if root.exists() and (not root.is_dir() or root.stat().st_mode & 0o077):
            raise ValueError("Existing application storage must already be private")
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.root = root.resolve(strict=True)
        self.files = self.root / "document-files"
        if (self.files.is_symlink() or self.files.exists() and
                (not self.files.is_dir() or self.files.stat().st_mode & 0o077)):
            raise ValueError("Existing file storage must already be private")
        self.files.mkdir(mode=0o700, exist_ok=True)

    @contextmanager
    def transaction(self) -> Iterator[Any]:
        if not self.transactional:
            yield None
            return
        with self.db.client.start_session() as session, session.start_transaction(
            read_concern=ReadConcern("snapshot"),
            write_concern=WriteConcern(w="majority", wtimeout=30000)
        ):
            yield session

    def storage_path(self, file_object: dict[str, Any]) -> Path:
        key = file_object.get("storage_key", "")
        if not isinstance(key, str) or re.fullmatch(r"[0-9a-f]{24}\.(?:pdf|docx|txt|md)", key) is None:
            raise DomainError(409, "FILE_INTEGRITY_FAILED", "Stored file cannot be read")
        path = self.files / key
        if path.is_symlink() or not path.is_file():
            raise DomainError(409, "FILE_INTEGRITY_FAILED", "Stored file cannot be read")
        if path.resolve(strict=True).parent != self.files:
            raise DomainError(409, "FILE_INTEGRITY_FAILED", "Stored file cannot be read")
        return path

    def _write_bytes(self, key: str, payload: bytes) -> Path:
        destination = self.files / key
        temporary = self.files / (key + ".upload")
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        # IDs are server generated and destination must never replace an existing version.
        if destination.exists() or destination.is_symlink():
            raise DomainError(409, "FILE_INTEGRITY_FAILED", "Storage identity conflict")
        os.replace(temporary, destination)
        directory = os.open(self.files, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        return destination

    def require_governance(self, workspace: dict[str, Any], document: dict[str, Any],
                           *, session: Any = None) -> dict[str, Any]:
        options = _options(session)
        instant = _now()
        if self.db.tombstones.find_one({"resource_type": "DOCUMENT", "resource_id": document["_id"]}, **options):
            raise DomainError(404, "RESOURCE_NOT_FOUND", "Resource not found")
        record = self.db.governance_records.find_one({
            "_id": document.get("current_governance_record_id"),
            "workspace_id": workspace["_id"], "resource_type": "DOCUMENT",
            "resource_id": document["_id"], "status": "APPROVED",
        }, **options)
        if (record is None or record.get("approver_id") is None or record.get("approved_at") is None
                or workspace.get("default_purpose") not in record.get("allowed_purposes", [])
                or record.get("rights_basis") in (None, "UNKNOWN")
                or record.get("valid_from") is not None and _aware(record["valid_from"]) > instant
                or record.get("valid_until") is not None and _aware(record["valid_until"]) <= instant):
            raise DomainError(409, "GOVERNANCE_NOT_APPROVED", "Document use is not currently approved")
        retention = record.get("retention_policy") or {}
        expiry = retention.get("expires_at")
        anonymization = record.get("anonymization") or {}
        if (expiry is not None and _aware(expiry) <= instant
                or anonymization.get("required") is True and anonymization.get("status") not in {"COMPLETED", "VERIFIED"}):
            raise DomainError(409, "GOVERNANCE_NOT_APPROVED", "Document use is not currently approved")
        evidence = record.get("rights_evidence", {})
        if not isinstance(evidence, dict):
            raise DomainError(409, "GOVERNANCE_NOT_APPROVED", "Invalid consent metadata")
        # Author consent is NOT a DATA_APPROVER decision. Its narrow scope
        # must remain enforced on reads, worker execution and retries too.
        if ((evidence.get("kind") == "SELF_DECLARATION" or "declaration_scope" in evidence)
                and (evidence.get("kind") != "SELF_DECLARATION"
                    or evidence.get("declaration_scope") != AUTHOR_CONSENT_SCOPE
                    or evidence.get("declaration_version") != 1
                    or record.get("rights_basis") != "CONSENT"
                    or workspace.get("default_purpose") not in AUTHOR_CONSENT_PURPOSES
                    or record.get("allowed_purposes") != [workspace.get("default_purpose")]
                    or evidence.get("declared_by") != record.get("created_by")
                    or record.get("approver_id") != record.get("created_by")
                    or not isinstance(record.get("created_by"), ObjectId)
                    or evidence.get("independent_approval") is not False
                    or any(evidence.get(field) is not True for field in (
                        "attested_authority", "pii_reviewed", "internal_use_only"))
                    or record.get("redistribution") != "PROHIBITED"
                    or expiry is None or record.get("valid_until") is None)):
            raise DomainError(409, "GOVERNANCE_NOT_APPROVED", "Author consent does not permit this use")
        return record

    @staticmethod
    def _check_upload_consent(record: dict[str, Any], *, actor_id: ObjectId,
                              kind: str, filename: str, digest: str) -> None:
        evidence = record.get("rights_evidence") or {}
        if evidence.get("kind") == "SELF_DECLARATION" and (
                evidence.get("declared_by") != actor_id or evidence.get("document_kind") != kind
                or evidence.get("filename") != filename or evidence.get("sha256") != digest):
            raise DomainError(409, "DECLARATION_FILE_MISMATCH", "Consent is bound to the declared uploader and exact file")

    def _document(self, actor_id: ObjectId, workspace_id: ObjectId | str,
                  document_id: ObjectId | str, *, session: Any = None) -> tuple[dict[str, Any], dict[str, Any]]:
        workspace_id, document_id = object_id(workspace_id), object_id(document_id)
        # Membership must be checked before disclosing whether an academic resource exists.
        self.policy.require(actor_id, workspace_id, "workspace.read", session=session)
        document = self.db.documents.find_one({"_id": document_id, "workspace_id": workspace_id,
                                               "lifecycle_state": "ACTIVE"}, **_options(session))
        if document is None or self.db.tombstones.find_one({"resource_type": "DOCUMENT", "resource_id": document_id}, **_options(session)):
            raise DomainError(404, "RESOURCE_NOT_FOUND", "Resource not found")
        capability = "report.read" if document["kind"] == "REPORT" else "source.read"
        workspace = self.policy.require(actor_id, workspace_id, capability,
                                        owner_id=document.get("owner_user_id"), session=session)
        return workspace, document

    def get(self, actor_id: ObjectId, workspace_id: ObjectId | str,
            document_id: ObjectId | str) -> dict[str, Any]:
        return self._document(actor_id, workspace_id, document_id)[1]

    def list(self, actor_id: ObjectId, workspace_id: ObjectId | str,
             *, kind: str = "REPORT", limit: int = 50) -> list[dict[str, Any]]:
        workspace_id = object_id(workspace_id)
        if kind not in {"REPORT", "CORPUS_SOURCE"} or type(limit) is not int or not 1 <= limit <= 100:
            raise DomainError(422, "INVALID_REQUEST", "Invalid document list request")
        self.policy.require(actor_id, workspace_id, "report.read" if kind == "REPORT" else "source.read")
        result = []
        for document in self.db.documents.find({"workspace_id": workspace_id, "kind": kind,
                                                "lifecycle_state": "ACTIVE"}).sort("_id", 1):
            try:
                result.append(self.get(actor_id, workspace_id, document["_id"]))
            except DomainError as error:
                if error.status != 404:
                    raise
            if len(result) >= limit:
                break
        return result

    def get_version(self, actor_id: ObjectId, workspace_id: ObjectId | str,
                    document_id: ObjectId | str, version_id: ObjectId | str) -> dict[str, Any]:
        _, document = self._document(actor_id, workspace_id, document_id)
        version = self.db.document_versions.find_one({"_id": object_id(version_id),
            "document_id": document["_id"], "workspace_id": document["workspace_id"], "lifecycle_state": "ACTIVE"})
        if version is None or self.db.tombstones.find_one({"resource_type": "DOCUMENT_VERSION", "resource_id": version["_id"]}):
            raise DomainError(404, "RESOURCE_NOT_FOUND", "Resource not found")
        return version

    def get_chunks(self, actor_id: ObjectId, workspace_id: ObjectId | str,
                   document_id: ObjectId | str, version_id: ObjectId | str,
                   *, limit: int = 100, after: int = -1) -> builtins.list[dict[str, Any]]:
        version = self.get_version(actor_id, workspace_id, document_id, version_id)
        if type(limit) is not int or not 1 <= limit <= 100 or type(after) is not int or after < -1:
            raise DomainError(422, "INVALID_REQUEST", "Invalid chunk page")
        workspace, document = self._document(actor_id, workspace_id, document_id)
        self.require_governance(workspace, document)
        if version["governance_record_id"] != document["current_governance_record_id"]:
            frozen_governance = {**document, "current_governance_record_id": version["governance_record_id"]}
            self.require_governance(workspace, frozen_governance)
        if version["processing_state"] not in {"PARSED", "INDEXING", "READY"}:
            raise DomainError(409, "DOCUMENT_NOT_PARSED", "Document has not been parsed")
        return list(self.db.chunks.find({"workspace_id": version["workspace_id"],
            "document_version_id": version["_id"], "generation_key": version["generation_key"],
            "order": {"$gt": after}}).sort("order", 1).limit(limit))

    def upload(self, actor_id: ObjectId, workspace_id: ObjectId | str, *, kind: str,
               document_key: str, title: str, filename: str, payload: bytes,
               idempotency_key: str, request_id: str,
               governance_record_id: ObjectId | str | None = None,
               document_id: ObjectId | str | None = None,
               expected_revision: int | None = None, create_only: bool = False) -> dict[str, Any]:
        workspace_id = object_id(workspace_id)
        if kind not in {"REPORT", "CORPUS_SOURCE"}:
            raise DomainError(422, "INVALID_REQUEST", "Invalid document kind")
        if (not isinstance(document_key, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", document_key) is None
                or not isinstance(title, str) or not 1 <= len(title.strip()) <= 256
                or not isinstance(idempotency_key, str) or not 1 <= len(idempotency_key) <= 128
                or not isinstance(request_id, str) or re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", request_id) is None):
            raise DomainError(422, "INVALID_REQUEST", "Invalid document metadata")
        workspace = self.policy.require(actor_id, workspace_id, "report.upload" if kind == "REPORT" else "source.upload")
        if expected_revision is not None and (type(expected_revision) is not int or expected_revision < 1):
            raise DomainError(422, "INVALID_REQUEST", "Invalid expected document revision")
        if type(create_only) is not bool:
            raise DomainError(422, "INVALID_REQUEST", "Invalid document operation")
        suffix = validate_document(filename, payload)
        digest = hashlib.sha256(payload).hexdigest()
        governance_id = object_id(governance_record_id) if governance_record_id is not None else None
        supplied_id = object_id(document_id) if document_id is not None else None
        body = {"kind": kind, "document_key": document_key, "title": title.strip(),
                "filename": filename, "sha256": digest, "governance_record_id": str(governance_id) if governance_id else None,
                "document_id": str(supplied_id) if supplied_id else None, "expected_revision": expected_revision,
                "create_only": create_only}
        request_hash = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        operation_key = {"actor_id": actor_id, "workspace_id": workspace_id,
                         "operation": "DOCUMENT_UPLOAD", "idempotency_key": idempotency_key}

        def replay(record: dict[str, Any]) -> dict[str, Any]:
            if record["request_sha256"] != request_hash:
                raise DomainError(409, "IDEMPOTENCY_CONFLICT", "Key belongs to a different request")
            # Do not use idempotency as an authorization bypass after revocation.
            document = self.get(actor_id, workspace_id, record["document_id"])
            version = self.get_version(actor_id, workspace_id, document["_id"], record["document_version_id"])
            current_workspace = self.policy.require(actor_id, workspace_id, "workspace.read")
            self.require_governance(current_workspace, document)
            self.require_governance(current_workspace, {**document,
                "current_governance_record_id": version["governance_record_id"]})
            job = self.db.jobs.find_one({"_id": record["job_id"], "workspace_id": workspace_id})
            return {"document": document, "version": version, "job": job}

        prior = self.db.document_operations.find_one(operation_key)
        if prior:
            return replay(prior)
        existing = self.db.documents.find_one({"workspace_id": workspace_id, "kind": kind, "document_key": document_key})
        if existing is not None:
            _, existing = self._document(actor_id, workspace_id, existing["_id"])
            if create_only:
                raise DomainError(409, "DOCUMENT_KEY_CONFLICT", "Document key already exists; create a version explicitly")
            if supplied_id is not None and supplied_id != existing["_id"]:
                raise DomainError(409, "DOCUMENT_KEY_CONFLICT", "Document identity does not match key")
            if expected_revision is not None and existing["revision"] != expected_revision:
                raise DomainError(409, "REVISION_CONFLICT", "Document changed; retry request")
        elif supplied_id is not None:
            raise DomainError(404, "RESOURCE_NOT_FOUND", "Resource not found")
        identifier = existing["_id"] if existing else ObjectId()
        if governance_id is not None:
            approval = self.db.governance_records.find_one({"_id": governance_id, "workspace_id": workspace_id,
                                                           "resource_type": "DOCUMENT"})
            if approval is None:
                raise DomainError(409, "GOVERNANCE_NOT_APPROVED", "Document use is not currently approved")
            if existing is None:
                identifier = approval["resource_id"]
                if not isinstance(identifier, ObjectId) or self.db.documents.find_one({"_id": identifier}) is not None:
                    raise DomainError(409, "GOVERNANCE_NOT_APPROVED", "Approval target does not match document")
            elif approval["resource_id"] != identifier:
                raise DomainError(409, "GOVERNANCE_NOT_APPROVED", "Approval target does not match document")
        else:
            governance_id = existing.get("current_governance_record_id") if existing else None
        now = _now()
        document = dict(existing) if existing else {
            "_id": identifier, **_common(actor_id, now), "workspace_id": workspace_id, "kind": kind,
            "document_key": document_key, "title": title.strip(), "owner_user_id": actor_id,
            "subject_user_ids": [actor_id] if kind == "REPORT" else [], "current_version_id": None,
            "current_governance_record_id": governance_id, "lifecycle_state": "ACTIVE",
        }
        document["current_governance_record_id"] = governance_id
        # Neither student reports nor corpus sources can reach parser before approval.
        consent = self.require_governance(workspace, document)
        self._check_upload_consent(consent, actor_id=actor_id, kind=kind, filename=filename, digest=digest)
        file_id, version_id, job_id = ObjectId(), ObjectId(), ObjectId()
        storage_key = str(file_id) + suffix
        self._write_bytes(storage_key, payload)
        previous = self.db.document_versions.find_one({"_id": existing["current_version_id"]}) if existing and existing.get("current_version_id") else None
        if existing and existing.get("current_version_id") and previous is None:
            raise DomainError(409, "FILE_INTEGRITY_FAILED", "Document version lineage is incomplete")
        version_no = previous["version_no"] + 1 if previous else 1
        file_object = {"_id": file_id, **_common(actor_id, now), "workspace_id": workspace_id,
            "storage_backend": "LOCAL_VOLUME", "storage_key": storage_key, "original_filename": filename,
            "media_type": MIME[suffix], "size_bytes": len(payload), "content_sha256": digest,
            "storage_state": "COMMITTED", "data_class": "RESTRICTED", "verified_at": now,
            "retention_expires_at": None}
        version = {"_id": version_id, **_common(actor_id, now), "workspace_id": workspace_id,
            "document_id": identifier, "version_no": version_no, "file_object_id": file_id,
            "content_sha256": digest, "supersedes_version_id": existing.get("current_version_id") if existing else None,
            "processing_state": "QUEUED", "lifecycle_state": "ACTIVE", "governance_record_id": governance_id,
            "parser_spec": None, "chunker_spec": None, "element_count": 0, "chunk_count": 0,
            "failure_code": None, "ready_at": None, "generation_key": None}
        job = {"_id": job_id, **_common(actor_id, now), "workspace_id": workspace_id, "job_type": "PARSE",
            "resource_ref": {"type": "DOCUMENT", "id": identifier, "version_id": version_id}, "config_ref": None,
            "idempotency_scope": "parse:" + str(version_id), "idempotency_key": "parse-v1", "correlation_id": request_id,
            "state": "QUEUED", "priority": 0, "available_at": now, "lease_owner": None, "lease_expires_at": None,
            "heartbeat_at": None, "attempt": 0, "max_attempts": 3, "progress": {"step": "QUEUED"}, "error_code": None}
        try:
            with self.transaction() as session:
                options = _options(session)
                current_workspace = self.policy.require(actor_id, workspace_id,
                    "report.upload" if kind == "REPORT" else "source.upload",
                    owner_id=document.get("owner_user_id"), session=session)
                consent = self.require_governance(current_workspace, document, session=session)
                self._check_upload_consent(consent, actor_id=actor_id, kind=kind, filename=filename, digest=digest)
                if existing is None:
                    document["current_version_id"] = version_id
                    self.db.documents.insert_one(document, **options)
                else:
                    updated = self.db.documents.update_one({"_id": identifier, "revision": existing["revision"],
                        "lifecycle_state": "ACTIVE"}, {"$set": {"current_version_id": version_id,
                            "current_governance_record_id": governance_id, "title": title.strip(), "updated_at": now,
                            "updated_by": actor_id}, "$inc": {"revision": 1}}, **options)
                    if updated.matched_count != 1:
                        raise DomainError(409, "REVISION_CONFLICT", "Document changed; retry request")
                self.db.file_objects.insert_one(file_object, **options)
                self.db.document_versions.insert_one(version, **options)
                self.db.jobs.insert_one(job, **options)
                self.db.document_operations.insert_one({"_id": ObjectId(), **_common(actor_id, now), **operation_key,
                    "request_sha256": request_hash, "document_id": identifier,
                    "document_version_id": version_id, "job_id": job_id}, **options)
                append_event(self.db, actor_id=actor_id, workspace_id=workspace_id, action="DOCUMENT_UPLOADED",
                             resource_type="DOCUMENT_VERSION", resource_id=version_id, request_id=request_id, session=session)
        except DuplicateKeyError:
            prior = self.db.document_operations.find_one(operation_key)
            if prior:
                return replay(prior)
            raise DomainError(409, "REVISION_CONFLICT", "Document changed; retry request") from None
        # A failed/unknown transaction may leave a private orphan file. Never remove
        # a possibly committed version; maintenance reconciliation handles orphans.
        return {"document": self.get(actor_id, workspace_id, identifier), "version": version, "job": job}
