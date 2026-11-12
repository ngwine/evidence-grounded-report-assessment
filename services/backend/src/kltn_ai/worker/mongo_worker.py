"""Durable PARSE worker: bounded parsing, current access and atomic publication.

PARSED is not READY: activating lexical/vector indexes is a separate job. A
stale/cancelled lease cannot publish any chunks because the lease CAS and every
generation write occur in one replica-set transaction.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bson import ObjectId
from pymongo.database import Database

from research.core_mvp.bounded_documents import (
    ParseLimits,
    ParserRejected,
    parse_document_bounded,
)
from research.core_mvp.documents import ParsedDocument
from services.backend.src.kltn_ai.db.mongo_jobs import MongoJobQueue
from services.backend.src.kltn_ai.domain.audit import append_event
from services.backend.src.kltn_ai.domain.documents import (
    DocumentService,
    _common,
    _options,
)
from services.backend.src.kltn_ai.domain.errors import DomainError


class LeaseLost(RuntimeError):
    """A stale attempt must not publish any state."""


def _now() -> datetime:
    return datetime.now(UTC)


def _stable_object_id(version_id: ObjectId, generation: str, kind: str, key: str) -> ObjectId:
    digest = hashlib.sha256(f"{version_id}\0{generation}\0{kind}\0{key}".encode()).digest()
    return ObjectId(digest[:12])


class MongoParseWorker:
    def __init__(self, database: Database[dict[str, Any]], private_root: Path | str,
                 *, owner: str = "mongo-parse-worker", transactional: bool = True,
                 parser: Callable[..., ParsedDocument] | None = None, lease_seconds: int = 120):
        if type(lease_seconds) is not int or not 90 <= lease_seconds <= 3600:
            raise ValueError("Parser lease must cover bounded parser and commit budgets")
        self.db = database
        self.documents = DocumentService(database, private_root, transactional=transactional)
        self.queue = MongoJobQueue(database.jobs)
        self.owner = owner
        self.parser = parser or parse_document_bounded
        self.lease_seconds = lease_seconds

    def _authorized(self, job: dict[str, Any], *, session: Any = None) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        options = _options(session)
        resource = job["resource_ref"]
        workspace, document = self.documents._document(job["created_by"], job["workspace_id"], resource["id"], session=session)
        self.documents.policy.require(job["created_by"], job["workspace_id"],
            "report.upload" if document["kind"] == "REPORT" else "source.upload",
            owner_id=document.get("owner_user_id"), session=session)
        self.documents.require_governance(workspace, document, session=session)
        version = self.db.document_versions.find_one({"_id": resource["version_id"], "document_id": document["_id"],
            "workspace_id": job["workspace_id"], "lifecycle_state": "ACTIVE"}, **options)
        if version is None or self.db.tombstones.find_one({"resource_type": "DOCUMENT_VERSION", "resource_id": resource["version_id"]}, **options):
            raise DomainError(404, "RESOURCE_NOT_FOUND", "Resource not found")
        self.documents.require_governance(workspace, {**document,
            "current_governance_record_id": version["governance_record_id"]}, session=session)
        file_object = self.db.file_objects.find_one({"_id": version["file_object_id"], "workspace_id": job["workspace_id"],
                                                    "storage_state": "COMMITTED"}, **options)
        if (file_object is None or file_object["content_sha256"] != version["content_sha256"]
                or self.db.tombstones.find_one({"resource_type": "FILE_OBJECT", "resource_id": version["file_object_id"]}, **options)):
            raise DomainError(409, "FILE_INTEGRITY_FAILED", "Stored file integrity failed")
        expiry = file_object.get("retention_expires_at")
        if expiry is not None:
            expiry = expiry.replace(tzinfo=UTC) if expiry.tzinfo is None else expiry
            if expiry <= _now():
                raise DomainError(409, "GOVERNANCE_NOT_APPROVED", "Document retention expired")
        return document, version, file_object

    def _lease(self, job: dict[str, Any]) -> dict[str, Any]:
        return {"_id": job["_id"], "revision": job["revision"], "state": "RUNNING",
                "lease_owner": self.owner, "lease_expires_at": {"$gt": _now()}}

    def _persist(self, job: dict[str, Any], parsed: ParsedDocument) -> None:
        if (parsed.document["document_id"] != str(job["resource_ref"]["id"])
                or parsed.document["document_version_id"] != str(job["resource_ref"]["version_id"])):
            raise DomainError(409, "PROVENANCE_INVALID", "Parser identity mismatch")
        if not parsed.elements or not parsed.chunks:
            raise DomainError(409, "PROVENANCE_INVALID", "Empty parser generation")
        generation = parsed.chunks[0]["generation_key"]
        version_id = job["resource_ref"]["version_id"]
        now = _now()
        element_ids = {item["element_key"]: _stable_object_id(version_id, generation, "element", item["element_key"])
                       for item in parsed.elements}
        if len(element_ids) != len(parsed.elements):
            raise DomainError(409, "PROVENANCE_INVALID", "Duplicate parser element")
        elements = []
        for raw in parsed.elements:
            if raw["document_version_id"] != str(version_id):
                raise DomainError(409, "PROVENANCE_INVALID", "Cross-version parser element")
            record = deepcopy(raw)
            record.update({"_id": element_ids[raw["element_key"]], **_common(job["created_by"], now),
                "workspace_id": job["workspace_id"], "document_version_id": version_id,
                "document_id": job["resource_ref"]["id"], "generation_key": generation,
                "parser_generation_key": raw["generation_key"], "artifact_schema_version": raw["schema_version"]})
            record["locator"]["source_element_ids"] = [record["_id"]]
            elements.append(record)
        chunks = []
        chunk_keys = set()
        for raw in parsed.chunks:
            key = raw["chunk_key"]
            if (key in chunk_keys or raw["generation_key"] != generation
                    or raw["document_id"] != str(job["resource_ref"]["id"])
                    or raw["document_version_id"] != str(version_id)):
                raise DomainError(409, "PROVENANCE_INVALID", "Mixed chunk generation")
            chunk_keys.add(key)
            record = deepcopy(raw)
            references = []
            for span in record["source_spans"]:
                element_key = span.get("element_id", span.get("element_key"))
                if (element_key not in element_ids or span.get("document_version_id") != str(version_id)):
                    raise DomainError(409, "PROVENANCE_INVALID", "Dangling chunk provenance")
                span["stable_element_key"] = element_key
                span["element_id"] = element_ids[element_key]
                span["document_id"] = job["resource_ref"]["id"]
                span["document_version_id"] = version_id
                span["locator"]["source_element_ids"] = [element_ids[element_key]]
                references.append(element_ids[element_key])
            if not references:
                raise DomainError(409, "PROVENANCE_INVALID", "Chunk lacks source elements")
            record.update({"_id": _stable_object_id(version_id, generation, "chunk", key),
                **_common(job["created_by"], now), "workspace_id": job["workspace_id"],
                "document_id": job["resource_ref"]["id"], "document_version_id": version_id,
                "element_ids": list(dict.fromkeys(references)),
                "artifact_schema_version": raw["schema_version"],
                "content_sha256": hashlib.sha256(record["normalized_text"].encode()).hexdigest(),
                "language": None, "structure_path": record.get("section_path", [])})
            record["locator"]["source_element_ids"] = record["element_ids"]
            record["source_element_ids"] = record["element_ids"]
            # The offline parser retains legacy source_refs aliases: PDF page
            # numbers and DOCX paragraph numbers, while UTF-8 uses locators.
            # Mongo storage uses one canonical locator shape for every format;
            # exact page/paragraph coordinates remain in each source span.
            record["source_refs"] = [deepcopy(span["locator"]) for span in record["source_spans"]]
            chunks.append(record)
        with self.documents.transaction() as session:
            options = _options(session)
            self._authorized(job, session=session)
            for record in elements:
                self._assert_immutable(self.db.document_elements, record, options)
            for record in chunks:
                self._assert_immutable(self.db.chunks, record, options)
            # This write is the transaction fence. If another attempt already
            # claimed, heartbeated, cancelled or finished, no artifact is visible.
            fenced = self.db.jobs.update_one(self._lease(job), {"$set": {
                "state": "SUCCEEDED", "lease_owner": None, "lease_expires_at": None,
                "finished_at": now, "updated_at": now, "progress": {"step": "SUCCEEDED"}},
                "$inc": {"revision": 1}}, **options)
            if fenced.matched_count != 1:
                raise LeaseLost("Lease lost")
            for record in elements:
                self.db.document_elements.update_one({"_id": record["_id"]}, {"$setOnInsert": record}, upsert=True, **options)
            for record in chunks:
                self.db.chunks.update_one({"_id": record["_id"]}, {"$setOnInsert": record}, upsert=True, **options)
            result = self.db.document_versions.update_one({"_id": version_id, "workspace_id": job["workspace_id"],
                "lifecycle_state": "ACTIVE", "processing_state": {"$in": ["PARSING", "QUEUED", "FAILED"]}},
                {"$set": {"processing_state": "PARSED", "generation_key": generation,
                    "parser_spec": parsed.elements[0]["parser_spec"], "chunker_spec": parsed.chunks[0]["chunker_spec"],
                    "element_count": len(elements), "chunk_count": len(chunks), "failure_code": None,
                    "updated_at": now, "updated_by": job["created_by"]}, "$inc": {"revision": 1}}, **options)
            if result.matched_count != 1:
                raise LeaseLost("Version is no longer writable")
            append_event(self.db, actor_id=job["created_by"], workspace_id=job["workspace_id"], action="DOCUMENT_PARSED",
                         resource_type="DOCUMENT_VERSION", resource_id=version_id,
                         request_id=job["correlation_id"], session=session)

    @staticmethod
    def _assert_immutable(collection: Any, record: dict[str, Any], options: dict[str, Any]) -> None:
        previous = collection.find_one({"_id": record["_id"]}, **options)
        if previous is None:
            return
        mutable_envelope = {"created_at", "created_by", "updated_at", "updated_by", "revision"}
        def content(item: dict[str, Any]) -> dict[str, Any]:
            return {key: value for key, value in item.items() if key not in mutable_envelope}
        if content(previous) != content(record):
            raise DomainError(409, "PROVENANCE_INVALID", "Existing generation integrity failed")

    def _fail(self, job: dict[str, Any], code: str, *, retryable: bool) -> None:
        with self.documents.transaction() as session:
            options = _options(session)
            # No raw exception message or filename enters a persisted job/audit.
            again = retryable and job["attempt"] < job["max_attempts"]
            state = "QUEUED" if again else "FAILED_FINAL"
            now = _now()
            updates = {"state": state, "error_code": code,
                "lease_owner": None, "lease_expires_at": None, "updated_at": now,
                "available_at": now, "progress": {"step": state}}
            if not again:
                updates["finished_at"] = now
            changed = self.db.jobs.update_one(self._lease(job), {"$set": updates,
                "$inc": {"revision": 1}}, **options)
            if changed.matched_count != 1:
                return
            self.db.document_versions.update_one({"_id": job["resource_ref"]["version_id"],
                "lifecycle_state": "ACTIVE", "processing_state": {"$in": ["QUEUED", "PARSING", "FAILED"]}},
                {"$set": {"processing_state": "QUEUED" if again else "FAILED", "failure_code": code,
                           "updated_at": now}, "$inc": {"revision": 1}}, **options)
            append_event(self.db, actor_id=job["created_by"], workspace_id=job["workspace_id"], action="DOCUMENT_PARSE_FAILED",
                resource_type="DOCUMENT_VERSION", resource_id=job["resource_ref"]["version_id"],
                request_id=job["correlation_id"], outcome="ERROR", reason_code=code, session=session)

    def _reconcile_exhausted(self) -> bool:
        """Bring version status in sync after queue lease-exhaustion recovery.

        Claiming is intentionally queue-only. Its terminal exhaustion transition
        can precede this idempotent reconciliation when a worker process died.
        """
        changed_any = False
        for candidate in self.db.jobs.find({"job_type": "PARSE", "state": "FAILED_FINAL",
                                             "error_code": "LEASE_EXHAUSTED"}).limit(20):
            with self.documents.transaction() as session:
                options = _options(session)
                terminal = self.db.jobs.find_one({"_id": candidate["_id"], "revision": candidate["revision"],
                    "state": "FAILED_FINAL", "error_code": "LEASE_EXHAUSTED"}, **options)
                if terminal is None:
                    continue
                changed = self.db.document_versions.update_one({"_id": terminal["resource_ref"]["version_id"],
                    "workspace_id": terminal["workspace_id"], "lifecycle_state": "ACTIVE",
                    "processing_state": {"$in": ["QUEUED", "PARSING"]}},
                    {"$set": {"processing_state": "FAILED", "failure_code": "LEASE_EXHAUSTED", "updated_at": _now()},
                     "$inc": {"revision": 1}}, **options)
                if changed.matched_count == 1:
                    changed_any = True
                    append_event(self.db, actor_id=None, workspace_id=terminal["workspace_id"],
                        action="DOCUMENT_PARSE_FAILED", resource_type="DOCUMENT_VERSION",
                        resource_id=terminal["resource_ref"]["version_id"], request_id=terminal["correlation_id"],
                        outcome="ERROR", reason_code="LEASE_EXHAUSTED", session=session)
        return changed_any

    def process_one(self) -> bool:
        job = self.queue.claim(owner=self.owner, lease_seconds=self.lease_seconds, job_type="PARSE")
        if job is None:
            return self._reconcile_exhausted()
        running = self.queue.start(job_id=job["_id"], owner=self.owner, revision=job["revision"])
        if running is None:
            return True
        try:
            document, version, file_object = self._authorized(running)
            path = self.documents.storage_path(file_object)
            if path.stat().st_size != file_object["size_bytes"] or hashlib.sha256(path.read_bytes()).hexdigest() != version["content_sha256"]:
                raise DomainError(409, "FILE_INTEGRITY_FAILED", "Stored file integrity failed")
            # The parent budget is always shorter than the fixed lease. No
            # unbounded in-process parser runs under the production default.
            with self.documents.transaction() as session:
                options = _options(session)
                self._authorized(running, session=session)
                fenced = self.db.jobs.update_one(self._lease(running), {"$set": {
                    "progress": {"step": "PARSING"}, "updated_at": _now()}}, **options)
                if fenced.matched_count != 1:
                    raise LeaseLost("Lease lost")
                started = self.db.document_versions.update_one({"_id": version["_id"], "lifecycle_state": "ACTIVE",
                    "processing_state": {"$in": ["QUEUED", "PARSING", "FAILED"]}},
                    {"$set": {"processing_state": "PARSING", "updated_at": _now()}, "$inc": {"revision": 1}}, **options)
                if started.matched_count != 1:
                    raise LeaseLost("Version is no longer writable")
            parsed = self.parser(path, role="report" if document["kind"] == "REPORT" else "source",
                limits=ParseLimits(), document_id=str(document["_id"]), document_version_id=str(version["_id"]))
            if parsed.document["sha256"] != version["content_sha256"]:
                raise DomainError(409, "FILE_INTEGRITY_FAILED", "Parser checksum mismatch")
            if path.stat().st_size != file_object["size_bytes"] or hashlib.sha256(path.read_bytes()).hexdigest() != version["content_sha256"]:
                raise DomainError(409, "FILE_INTEGRITY_FAILED", "Stored file changed during parsing")
            self._authorized(running)
            self._persist(running, parsed)
        except LeaseLost:
            pass
        except DomainError as error:
            self._fail(running, error.code, retryable=False)
        except ParserRejected as error:
            safe = str(error)
            self._fail(running, safe if safe.startswith("PARSER_") and len(safe) <= 64 else "PARSER_REJECTED", retryable=False)
        except Exception:  # noqa: BLE001 - worker boundary persists a content-safe failure, never a traceback.
            self._fail(running, "PARSE_INTERNAL_ERROR", retryable=True)
        return True


def process_one(database: Database[dict[str, Any]], private_root: Path | str, *,
                owner: str = "mongo-parse-worker", transactional: bool = True,
                parser: Callable[..., ParsedDocument] | None = None, lease_seconds: int = 120) -> bool:
    return MongoParseWorker(database, private_root, owner=owner, transactional=transactional,
                            parser=parser, lease_seconds=lease_seconds).process_one()
