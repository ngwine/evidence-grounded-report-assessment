"""Pinned, workspace-scoped analysis proposals over persisted provenance.

This is the application adapter for the existing research pipelines, not a
second classifier. Results remain immutable proposals; a review is recorded as
a separate revision and cannot turn a heuristic score into an official grade.
"""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bson import BSON, ObjectId
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from .access import object_id
from .audit import append_event
from .documents import DocumentService, _common, _options
from .errors import DomainError
from .rubrics import RubricService
from .provenance import validate_chunk_generation
from ..worker.bounded_pipeline import configuration


def json_value(value: Any) -> Any:
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [json_value(item) for item in value]
    return value


def _sha(value: Any) -> str:
    return hashlib.sha256(json.dumps(json_value(value), sort_keys=True,
        separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def evidence_sha(records: list[dict[str, Any]]) -> str:
    fields = ("_id", "workspace_id", "analysis_run_id", "document_version_id", "pipeline",
              "report_chunk_id", "source_chunk_id", "source_version_id", "checklist_id", "evidence")
    return _sha([{key: row[key] for key in fields} for row in sorted(records, key=lambda row: str(row["_id"]))])


def _now() -> datetime:
    return datetime.now(UTC)


def canonical_chunk(raw: dict[str, Any]) -> dict[str, Any]:
    """Expose canonical BSON identities without losing exact source mappings."""
    chunk = json_value(deepcopy(raw))
    chunk["chunk_id"] = str(raw["_id"])
    chunk["document_version"] = str(raw["document_version_id"])
    chunk["text"] = raw["normalized_text"]
    # Administrative timestamps are not part of a parser generation digest.
    for key in ("_id", "created_at", "created_by", "updated_at", "updated_by", "revision", "workspace_id"):
        chunk.pop(key, None)
    chunk["schema_version"] = raw.get("artifact_schema_version", 2)
    return chunk


def bson_limit(record: dict[str, Any]) -> None:
    # Leave space below Mongo's 16 MiB document ceiling and bound result APIs.
    if len(BSON.encode(record)) > 10 * 1024 * 1024:
        raise DomainError(409, "ANALYSIS_OUTPUT_LIMIT", "Analysis result exceeds the persistence limit")


class AnalysisService:
    def __init__(self, database: Database[dict[str, Any]], private_root: Path | str,
                 *, transactional: bool = True, indexes: Any = None):
        self.db = database
        self.documents = DocumentService(database, private_root, transactional=transactional)
        self.policy = self.documents.policy
        self.rubrics = RubricService(database, transaction_mode=transactional)
        if indexes is None:
            from .indexes import IndexService
            indexes = IndexService(database, private_root, transactional=transactional)
        self.indexes = indexes

    @staticmethod
    def _page(rows: list[dict[str, Any]], limit: int) -> dict[str, Any]:
        more = len(rows) > limit
        items = rows[:limit]
        return {"items": items, "page": {"limit": limit, "has_more": more,
            "next_cursor": str(items[-1]["_id"]) if more else None}}

    def _report(self, actor_id: ObjectId, workspace_id: ObjectId, version_id: ObjectId,
                *, session: Any = None) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
        options = _options(session)
        self.policy.require(actor_id, workspace_id, "run.read", session=session)
        version = self.db.document_versions.find_one({"_id": version_id,
            "workspace_id": workspace_id, "lifecycle_state": "ACTIVE"}, **options)
        if version is None:
            raise DomainError(404, "RESOURCE_NOT_FOUND", "Resource not found")
        workspace, document = self.documents._document(actor_id, workspace_id, version["document_id"], session=session)
        if document["kind"] != "REPORT" or self.db.tombstones.find_one({
            "resource_type": "DOCUMENT_VERSION", "resource_id": version_id}, **options):
            raise DomainError(404, "RESOURCE_NOT_FOUND", "Resource not found")
        self.documents.require_governance(workspace, document, session=session)
        self.documents.require_governance(workspace, {**document,
            "current_governance_record_id": version["governance_record_id"]}, session=session)
        if version["processing_state"] not in {"PARSED", "INDEXING", "READY"} or not version.get("generation_key"):
            raise DomainError(409, "DOCUMENT_NOT_PARSED", "Analysis requires a parsed report version")
        file_object = self.db.file_objects.find_one({"_id": version["file_object_id"],
            "workspace_id": workspace_id, "storage_state": "COMMITTED"}, **options)
        if (file_object is None or file_object["content_sha256"] != version["content_sha256"]
                or self.db.tombstones.find_one({"resource_type": "FILE_OBJECT", "resource_id": version["file_object_id"]}, **options)):
            raise DomainError(409, "FILE_INTEGRITY_FAILED", "Stored file integrity failed")
        expiry = file_object.get("retention_expires_at")
        if expiry is not None and (expiry.replace(tzinfo=UTC) if expiry.tzinfo is None else expiry) <= _now():
            raise DomainError(409, "GOVERNANCE_NOT_APPROVED", "Report retention expired")
        chunks = list(self.db.chunks.find({"workspace_id": workspace_id,
            "document_version_id": version_id, "generation_key": version["generation_key"]}, **options).sort("order", 1))
        if not chunks or len(chunks) != version["chunk_count"]:
            raise DomainError(409, "PROVENANCE_INVALID", "Report parser generation is incomplete")
        validate_chunk_generation(self.db, version, chunks, session=session)
        for chunk in chunks:
            if (chunk["document_id"] != document["_id"] or chunk["content_sha256"] !=
                    hashlib.sha256(chunk["normalized_text"].encode()).hexdigest()):
                raise DomainError(409, "PROVENANCE_INVALID", "Stored chunk integrity failed")
        return document, version, [canonical_chunk(item) for item in chunks]

    def snapshot(self, actor_id: ObjectId, workspace_id: ObjectId, run: dict[str, Any],
                 *, session: Any = None, verify: bool = True) -> dict[str, Any]:
        self.policy.require(actor_id, workspace_id, "run.read", session=session)
        document, version, chunks = self._report(actor_id, workspace_id, run["document_version_id"], session=session)
        sources: list[dict[str, Any]] = []
        vector_cache: dict[str, list[float]] = {}
        pins = []
        for generation_id in run["index_generation_ids"]:
            snapshot = self.indexes.get_snapshot(actor_id, workspace_id, generation_id,
                session=session, allow_superseded=True)
            source_version = snapshot["version"]
            if snapshot["document"]["kind"] != "CORPUS_SOURCE":
                raise DomainError(409, "SOURCE_SCOPE_INVALID", "Similarity requires comparison-source documents")
            if (source_version["_id"] not in run["source_version_ids"]
                    or source_version["content_sha256"] == version["content_sha256"]):
                raise DomainError(409, "SELF_SOURCE_FORBIDDEN", "Source corpus cannot contain the submitted report")
            # Index adapters may already return canonical JSON chunks.
            source_chunks = [canonical_chunk(item) if isinstance(item.get("_id"), ObjectId)
                             else json_value(deepcopy(item)) for item in snapshot["chunks"]]
            sources.extend(source_chunks)
            if snapshot["vectors"] is not None:
                for chunk in source_chunks:
                    vector = snapshot["vectors"][chunk["chunk_id"]]
                    key = chunk["text"]
                    if key in vector_cache and vector_cache[key] != vector:
                        raise DomainError(409, "INDEX_INTEGRITY_FAILED", "Identical text has inconsistent stored embeddings")
                    vector_cache[key] = vector
            pins.append({"document_id": str(snapshot["document"]["_id"]),
                "document_version_id": str(source_version["_id"]),
                "content_sha256": source_version["content_sha256"],
                "index_generation_id": str(generation_id), "chunks_sha256": _sha(source_chunks)})
        if len({pin["document_version_id"] for pin in pins}) != len(run["source_version_ids"]):
            raise DomainError(409, "INDEX_SCOPE_INVALID", "Index generation scope does not match the run")
        compiled = None
        if run["rubric_version_id"] is not None:
            compiled = self.rubrics.get_compiled_published(actor_id, workspace_id, run["rubric_version_id"])
        frozen = {"report": {"document_id": str(document["_id"]),
            "document_version_id": str(version["_id"]), "content_sha256": version["content_sha256"],
            "generation_key": version["generation_key"], "chunks_sha256": _sha(chunks)},
            "sources": pins, "rubric_compiled_sha256": compiled["compiled_sha256"] if compiled else None}
        config, config_sha = configuration(run["config_id"])
        if config_sha != run["config_sha256"] or verify and frozen != run["frozen_inputs"]:
            raise DomainError(409, "ANALYSIS_INPUT_CHANGED", "Pinned analysis inputs failed their integrity check")
        if len(chunks) > config["limits"]["max_report_chunks"] or len(sources) > config["limits"]["max_source_chunks"]:
            raise DomainError(409, "ANALYSIS_INPUT_LIMIT", "Document scope exceeds the local analysis budget")
        return {"frozen_inputs": frozen, "config_id": run["config_id"], "config_sha256": config_sha,
            "report_chunks": chunks, "source_chunks": sources, "compiled_rubric": compiled,
            "run_type": run["run_type"], "source_vector_cache": vector_cache}

    def create(self, actor_id: ObjectId, workspace_id: ObjectId | str, report_id: ObjectId | str,
               body: dict[str, Any], *, idempotency_key: str, request_id: str) -> dict[str, Any]:
        workspace_id, report_id = object_id(workspace_id), object_id(report_id)
        self.policy.require(actor_id, workspace_id, "run.create")
        if (not isinstance(body, dict) or set(body) - {"run_type", "report_version_id", "source_scope", "rubric_version_id", "config_id", "mode"}
                or not {"run_type", "report_version_id", "source_scope", "config_id"} <= set(body)
                or body.get("run_type") not in {"SIMILARITY", "ASSESSMENT", "BOTH"}
                or body.get("mode") is not None):
            raise DomainError(422, "VALIDATION_FAILED", "Invalid analysis request; checklist evidence modes belong to the published rubric")
        scope = body["source_scope"]
        if (not isinstance(scope, dict) or set(scope) != {"source_version_ids"}
                or not isinstance(scope["source_version_ids"], list) or len(scope["source_version_ids"]) > 20):
            raise DomainError(422, "VALIDATION_FAILED", "Analysis requires an explicit bounded source scope")
        source_versions = [object_id(value) for value in scope["source_version_ids"]]
        if len(set(source_versions)) != len(source_versions):
            raise DomainError(422, "VALIDATION_FAILED", "Source versions must be unique")
        source_versions.sort(key=str)
        if body["run_type"] in {"SIMILARITY", "BOTH"} and not source_versions:
            raise DomainError(422, "VALIDATION_FAILED", "Similarity analysis requires source versions")
        if body["run_type"] == "ASSESSMENT" and source_versions:
            raise DomainError(422, "CROSS_SOURCE_VERIFICATION_UNSUPPORTED", "Assessment v0 evaluates report evidence only")
        rubric_id = object_id(body["rubric_version_id"]) if body.get("rubric_version_id") is not None else None
        if (body["run_type"] in {"ASSESSMENT", "BOTH"}) != (rubric_id is not None):
            raise DomainError(422, "VALIDATION_FAILED", "Assessment requires exactly one published rubric version")
        try:
            _, config_sha = configuration(body["config_id"])
        except (ValueError, TypeError):
            raise DomainError(422, "VALIDATION_FAILED", "Unknown server-locked analysis configuration") from None
        if (not isinstance(idempotency_key, str) or re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", idempotency_key) is None):
            raise DomainError(422, "VALIDATION_FAILED", "Invalid idempotency key")
        identity = {"actor_id": actor_id, "workspace_id": workspace_id,
                    "operation": "ANALYSIS_CREATE", "idempotency_key": idempotency_key}
        request_sha = _sha({"report_id": report_id, "body": body})

        def replay(previous: dict[str, Any]) -> dict[str, Any]:
            if previous["request_sha256"] != request_sha:
                raise DomainError(409, "IDEMPOTENCY_CONFLICT", "Idempotency key used for a different request")
            run = self.get(actor_id, workspace_id, previous["analysis_run_id"])
            return {"run": run, "job": self.db.jobs.find_one({"_id": run["job_id"]})}

        previous = self.db.analysis_operations.find_one(identity)
        if previous is not None:
            return replay(previous)
        now = _now()
        run_id, job_id = ObjectId(), ObjectId()
        run = {"_id": run_id, **_common(actor_id, now), "workspace_id": workspace_id,
            "document_id": report_id, "document_version_id": object_id(body["report_version_id"]),
            "run_type": body["run_type"], "config_id": body["config_id"], "config_sha256": config_sha,
            "source_version_ids": source_versions, "index_generation_ids": [], "rubric_version_id": rubric_id,
            "rubric_compiled_sha256": None, "frozen_inputs": {}, "manifest": None,
            "state": "QUEUED", "lifecycle_state": "ACTIVE", "job_id": job_id,
            "failure_code": None, "result_id": None, "review_state": "UNREVIEWED", "completed_at": None}
        try:
            with self.documents.transaction() as session:
                options = _options(session)
                self.policy.require(actor_id, workspace_id, "run.create", session=session)
                doc, _, _ = self._report(actor_id, workspace_id, run["document_version_id"], session=session)
                if doc["_id"] != report_id:
                    raise DomainError(404, "RESOURCE_NOT_FOUND", "Resource not found")
                for source_version_id in source_versions:
                    source = self.indexes.get_active_snapshot(actor_id, workspace_id, source_version_id,
                        body["config_id"], session=session)
                    run["index_generation_ids"].append(source["generation"]["_id"])
                snapshot = self.snapshot(actor_id, workspace_id, run, session=session, verify=False)
                run["frozen_inputs"] = snapshot["frozen_inputs"]
                run["rubric_compiled_sha256"] = snapshot["frozen_inputs"]["rubric_compiled_sha256"]
                job = {"_id": job_id, **_common(actor_id, now), "workspace_id": workspace_id,
                    "job_type": "ANALYZE", "resource_ref": {"type": "ANALYSIS_RUN", "id": run_id, "version_id": run_id},
                    "config_ref": None, "idempotency_scope": f"analysis:{workspace_id}:{actor_id}",
                    "idempotency_key": idempotency_key, "correlation_id": request_id,
                    "state": "QUEUED", "priority": 0, "available_at": now, "lease_owner": None,
                    "lease_expires_at": None, "heartbeat_at": None, "attempt": 0, "max_attempts": 3,
                    "progress": {"step": "QUEUED"}, "error_code": None}
                self.db.analysis_runs.insert_one(run, **options)
                self.db.jobs.insert_one(job, **options)
                self.db.analysis_operations.insert_one({"_id": ObjectId(), **_common(actor_id, now),
                    **identity, "request_sha256": request_sha, "analysis_run_id": run_id, "job_id": job_id}, **options)
                append_event(self.db, actor_id=actor_id, workspace_id=workspace_id, action="ANALYSIS_CREATED",
                    resource_type="ANALYSIS_RUN", resource_id=run_id, request_id=request_id, session=session)
        except DuplicateKeyError:
            prior = self.db.analysis_operations.find_one(identity)
            if prior is None:
                raise DomainError(409, "ANALYSIS_CONFLICT", "Analysis identity conflict") from None
            return replay(prior)
        return {"run": run, "job": job}

    def get(self, actor_id: ObjectId, workspace_id: ObjectId | str,
            run_id: ObjectId | str, *, session: Any = None) -> dict[str, Any]:
        workspace_id, run_id = object_id(workspace_id), object_id(run_id)
        self.policy.require(actor_id, workspace_id, "run.read", session=session)
        run = self.db.analysis_runs.find_one({"_id": run_id, "workspace_id": workspace_id,
                                              "lifecycle_state": "ACTIVE"}, **_options(session))
        if run is None or self.db.tombstones.find_one({"resource_type": "ANALYSIS_RUN", "resource_id": run_id}, **_options(session)):
            raise DomainError(404, "RESOURCE_NOT_FOUND", "Resource not found")
        self.snapshot(actor_id, workspace_id, run, session=session)
        return run

    def get_result(self, actor_id: ObjectId, workspace_id: ObjectId | str,
                   run_id: ObjectId | str) -> dict[str, Any]:
        run = self.get(actor_id, workspace_id, run_id)
        if run["state"] != "SUCCEEDED" or run["result_id"] is None:
            raise DomainError(409, "ANALYSIS_NOT_READY", "Analysis results are not available")
        result = self.db.analysis_results.find_one({"_id": run["result_id"], "analysis_run_id": run["_id"],
                                                   "workspace_id": run["workspace_id"]})
        if (result is None or _sha({key: result[key] for key in ("similarity", "assessment", "manifest")}) != result["result_sha256"]
                or run["manifest"] != result["manifest"]):
            raise DomainError(409, "RESULT_INTEGRITY_FAILED", "Stored result integrity failed")
        records = list(self.db.evidence_items.find({"analysis_run_id": run["_id"], "workspace_id": run["workspace_id"]}).limit(3001))
        if len(records) > 3000 or evidence_sha(records) != result["evidence_sha256"]:
            raise DomainError(409, "RESULT_INTEGRITY_FAILED", "Stored evidence integrity failed")
        return {key: deepcopy(result[key]) for key in ("similarity", "assessment", "manifest")}

    def list_evidence(self, actor_id: ObjectId, workspace_id: ObjectId | str, run_id: ObjectId | str,
                      *, limit: int = 25, cursor: str | None = None) -> dict[str, Any]:
        run = self.get(actor_id, workspace_id, run_id)
        self.get_result(actor_id, workspace_id, run_id)
        if type(limit) is not int or not 1 <= limit <= 100:
            raise DomainError(422, "VALIDATION_FAILED", "Invalid evidence page")
        query: dict[str, Any] = {"analysis_run_id": run["_id"], "workspace_id": run["workspace_id"]}
        if cursor is not None:
            query["_id"] = {"$gt": object_id(cursor)}
        return self._page(list(self.db.evidence_items.find(query).sort("_id", 1).limit(limit + 1)), limit)

    def list(self, actor_id: ObjectId, workspace_id: ObjectId | str, report_id: ObjectId | str,
             *, limit: int = 25, cursor: str | None = None) -> dict[str, Any]:
        workspace_id, report_id = object_id(workspace_id), object_id(report_id)
        self.policy.require(actor_id, workspace_id, "run.read")
        _, document = self.documents._document(actor_id, workspace_id, report_id)
        if document["kind"] != "REPORT":
            raise DomainError(404, "RESOURCE_NOT_FOUND", "Resource not found")
        if type(limit) is not int or not 1 <= limit <= 100:
            raise DomainError(422, "VALIDATION_FAILED", "Invalid analysis page")
        query: dict[str, Any] = {"workspace_id": workspace_id, "document_id": report_id, "lifecycle_state": "ACTIVE"}
        if cursor is not None:
            query["_id"] = {"$gt": object_id(cursor)}
        rows = []
        # Skip revoked scopes without disclosing their metadata. Bounded scan
        # avoids turning a page into an unbounded series of artifact reads.
        for candidate in self.db.analysis_runs.find(query).sort("_id", 1).limit(500):
            try:
                rows.append(self.get(actor_id, workspace_id, candidate["_id"]))
            except DomainError as error:
                if error.status not in {404, 409}:
                    raise
            if len(rows) > limit:
                break
        return self._page(rows, limit)

    def list_reviews(self, actor_id: ObjectId, workspace_id: ObjectId | str, run_id: ObjectId | str,
                     *, limit: int = 25, cursor: str | None = None) -> dict[str, Any]:
        run = self.get(actor_id, workspace_id, run_id)
        if type(limit) is not int or not 1 <= limit <= 100:
            raise DomainError(422, "VALIDATION_FAILED", "Invalid review page")
        query: dict[str, Any] = {"workspace_id": run["workspace_id"], "analysis_run_id": run["_id"]}
        if cursor is not None:
            query["_id"] = {"$gt": object_id(cursor)}
        return self._page(list(self.db.reviews.find(query).sort("_id", 1).limit(limit + 1)), limit)

    def review(self, actor_id: ObjectId, workspace_id: ObjectId | str, run_id: ObjectId | str,
               body: dict[str, Any], *, expected_revision: int, request_id: str) -> dict[str, Any]:
        if (type(expected_revision) is not int or expected_revision < 1 or not isinstance(body, dict)
                or set(body) - {"decision", "reason_code", "reason_text"}
                or body.get("decision") not in {"ACCEPT", "REJECT"}
                or not isinstance(body.get("reason_code"), str)
                or re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", body["reason_code"]) is None
                or body.get("reason_text") is not None and
                (not isinstance(body["reason_text"], str) or len(body["reason_text"]) > 4000)):
            raise DomainError(422, "VALIDATION_FAILED", "Review requires ACCEPT or REJECT and an explicit reason code")
        with self.documents.transaction() as session:
            options = _options(session)
            run = self.get(actor_id, workspace_id, run_id, session=session)
            self.policy.require(actor_id, run["workspace_id"], "review.create", session=session)
            prior = self.db.reviews.find_one({"analysis_run_id": run["_id"],
                                              "based_on_revision": expected_revision}, **options)
            if prior is not None:
                if (prior["created_by"] == actor_id and prior["decision"] == body["decision"]
                        and prior["reason_code"] == body["reason_code"] and prior["reason_text"] == body.get("reason_text")):
                    return prior
                raise DomainError(409, "REVISION_CONFLICT", "A different review already used this revision")
            if run["state"] != "SUCCEEDED":
                raise DomainError(409, "ANALYSIS_NOT_READY", "Only completed proposals can be reviewed")
            self.get_result(actor_id, workspace_id, run_id)
            now = _now()
            record = {"_id": ObjectId(), **_common(actor_id, now), "workspace_id": run["workspace_id"],
                "analysis_run_id": run["_id"], "decision": body["decision"], "reason_code": body["reason_code"],
                "reason_text": body.get("reason_text"), "based_on_revision": expected_revision}
            changed = self.db.analysis_runs.update_one({"_id": run["_id"], "revision": expected_revision,
                "state": "SUCCEEDED", "lifecycle_state": "ACTIVE"}, {"$set": {"review_state": "REVIEWED",
                "updated_at": now, "updated_by": actor_id}, "$inc": {"revision": 1}}, **options)
            if changed.matched_count != 1:
                raise DomainError(409, "REVISION_CONFLICT", "Analysis revision has changed; reload before reviewing")
            self.db.reviews.insert_one(record, **options)
            append_event(self.db, actor_id=actor_id, workspace_id=run["workspace_id"], action="ANALYSIS_REVIEWED",
                resource_type="ANALYSIS_RUN", resource_id=run["_id"], request_id=request_id, session=session)
        return self.db.reviews.find_one({"_id": record["_id"], "workspace_id": record["workspace_id"]})
