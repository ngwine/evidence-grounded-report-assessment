"""Durable INDEX worker with bounded offline models and fenced activation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from services.backend.src.kltn_ai.db.mongo_jobs import MongoJobQueue
from services.backend.src.kltn_ai.domain.audit import append_event
from services.backend.src.kltn_ai.domain.documents import _options
from services.backend.src.kltn_ai.domain.errors import DomainError
from services.backend.src.kltn_ai.domain.indexes import IndexService, build_lexical, locked_config
from services.backend.src.kltn_ai.integrations.local_ai.bounded_embeddings import EmbeddingRejected, encode_bounded
from .mongo_worker import LeaseLost


def _now() -> datetime:
    return datetime.now(UTC)


class MongoIndexWorker:
    def __init__(self, database: Any, private_root: Path | str, *, owner: str = "mongo-index-worker",
                 transactional: bool = True, encoder: Callable[..., dict[str, Any]] | None = None,
                 lease_seconds: int = 300):
        if type(lease_seconds) is not int or not 180 <= lease_seconds <= 3600:
            raise ValueError("Index lease must cover bounded model and commit budgets")
        self.db = database
        self.indexes = IndexService(database, private_root, transactional=transactional)
        self.queue = MongoJobQueue(database.jobs)
        self.owner = owner
        # Dependency injection exists for deterministic failure tests; the default
        # path always uses the actual cached model in a timeout-bounded child.
        self.encoder = encoder or encode_bounded
        self.lease_seconds = lease_seconds

    def _lease(self, job: dict[str, Any]) -> dict[str, Any]:
        return {"_id": job["_id"], "revision": job["revision"], "state": "RUNNING",
                "lease_owner": self.owner, "lease_expires_at": {"$gt": _now()}}

    def _authorized(self, job: dict[str, Any], *, session: Any = None) -> dict[str, Any]:
        generation = self.indexes.get(job["created_by"], job["workspace_id"], job["resource_ref"]["id"], session=session)["generation"]
        if (generation["job_id"] != job["_id"] or generation["document_version_id"] != job["resource_ref"]["version_id"]
                or generation["state"] not in {"QUEUED", "BUILDING"}):
            raise DomainError(409, "INDEX_NOT_WRITABLE", "Index generation is no longer writable")
        workspace, _document, version = self.indexes._version(job["created_by"], job["workspace_id"],
            generation["document_version_id"], session=session)
        config, digest = locked_config(generation["config_id"])
        if (config != generation["config"] or digest != generation["config_sha256"]
                or generation["parser_generation_key"] != version["generation_key"]
                or generation["governance_record_id"] != version["governance_record_id"]
                or generation["purpose"] != workspace["default_purpose"]):
            raise DomainError(409, "INDEX_INTEGRITY_FAILED", "Index input locks changed")
        return generation

    def _begin(self, job: dict[str, Any]) -> dict[str, Any]:
        with self.indexes.documents.transaction() as session:
            options = _options(session)
            generation = self._authorized(job, session=session)
            fenced = self.db.jobs.update_one(self._lease(job), {"$set": {
                "progress": {"step": "BUILDING_INDEX"}, "updated_at": _now()}}, **options)
            if fenced.matched_count != 1:
                raise LeaseLost("Lease lost")
            changed = self.db.index_generations.update_one({"_id": generation["_id"], "revision": generation["revision"],
                "state": {"$in": ["QUEUED", "BUILDING"]}}, {"$set": {"state": "BUILDING", "failure_code": None,
                "updated_at": _now(), "updated_by": job["created_by"]}, "$inc": {"revision": 1}}, **options)
            if changed.matched_count != 1:
                raise LeaseLost("Generation changed")
            generation["state"] = "BUILDING"
            generation["revision"] += 1
            return generation

    def _persist(self, job: dict[str, Any], payload: dict[str, Any], key: str, digest: str) -> None:
        with self.indexes.documents.transaction() as session:
            options = _options(session)
            generation = self._authorized(job, session=session)
            _workspace, _document, version = self.indexes._version(job["created_by"], job["workspace_id"],
                generation["document_version_id"], session=session)
            # Re-read canonical chunks after inference: no stale/private artifact
            # becomes active if authority or source integrity changed meanwhile.
            if payload["chunks"] != self.indexes._chunks(version, session=session):
                raise DomainError(409, "INDEX_INTEGRITY_FAILED", "Chunk generation changed during indexing")
            head = self.db.index_heads.find_one({"workspace_id": job["workspace_id"],
                "document_version_id": version["_id"], "config_id": generation["config_id"]}, **options)
            if head is None:
                raise DomainError(409, "INDEX_INTEGRITY_FAILED", "Index head is missing")
            now = _now()
            fenced = self.db.jobs.update_one(self._lease(job), {"$set": {
                "state": "SUCCEEDED", "lease_owner": None, "lease_expires_at": None,
                "finished_at": now, "updated_at": now, "progress": {"step": "SUCCEEDED"}},
                "$inc": {"revision": 1}}, **options)
            if fenced.matched_count != 1:
                raise LeaseLost("Lease lost")
            # A slower older rebuild is retained as historical, but cannot move
            # the pointer backwards after a newer generation was requested.
            activate = head["requested_generation_id"] == generation["_id"]
            state = "ACTIVE" if activate else "SUPERSEDED"
            changed = self.db.index_generations.update_one({"_id": generation["_id"], "revision": generation["revision"],
                "state": "BUILDING"}, {"$set": {"state": state, "artifact_key": key, "artifact_sha256": digest,
                    "chunk_count": len(payload["chunks"]), "dense_dimension": 384 if payload["vectors"] is not None else None,
                    "model": payload["model"], "activated_at": now if activate else None,
                    "failure_code": None, "updated_at": now, "updated_by": job["created_by"]},
                    "$inc": {"revision": 1}}, **options)
            if changed.matched_count != 1:
                raise LeaseLost("Generation changed")
            if activate:
                prior = head.get("active_generation_id")
                if prior is not None and prior != generation["_id"]:
                    self.db.index_generations.update_one({"_id": prior, "state": "ACTIVE"}, {"$set": {
                        "state": "SUPERSEDED", "updated_at": now, "updated_by": job["created_by"]},
                        "$inc": {"revision": 1}}, **options)
                moved = self.db.index_heads.update_one({"_id": head["_id"], "revision": head["revision"],
                    "requested_generation_id": generation["_id"]}, {"$set": {"active_generation_id": generation["_id"],
                    "updated_at": now, "updated_by": job["created_by"]}, "$inc": {"revision": 1}}, **options)
                if moved.matched_count != 1:
                    raise LeaseLost("Index head changed")
                ready = self.db.document_versions.update_one({"_id": version["_id"], "lifecycle_state": "ACTIVE",
                    "generation_key": generation["parser_generation_key"], "processing_state": {"$in": ["PARSED", "INDEXING", "READY"]}},
                    {"$set": {"processing_state": "READY", "ready_at": now, "updated_at": now,
                              "updated_by": job["created_by"]}, "$inc": {"revision": 1}}, **options)
                if ready.matched_count != 1:
                    raise LeaseLost("Version changed")
            append_event(self.db, actor_id=job["created_by"], workspace_id=job["workspace_id"],
                action="INDEX_ACTIVATED" if activate else "INDEX_SUPERSEDED", resource_type="INDEX_GENERATION",
                resource_id=generation["_id"], request_id=job["correlation_id"], session=session)

    def _fail(self, job: dict[str, Any], code: str, *, retryable: bool = False) -> None:
        with self.indexes.documents.transaction() as session:
            options = _options(session)
            again = retryable and job["attempt"] < job["max_attempts"]
            now = _now()
            updates = {"state": "QUEUED" if again else "FAILED_FINAL", "error_code": code,
                "lease_owner": None, "lease_expires_at": None, "updated_at": now,
                "available_at": now + timedelta(seconds=30) if again else now,
                "progress": {"step": "QUEUED" if again else "FAILED_FINAL"}}
            if not again:
                updates["finished_at"] = now
            fenced = self.db.jobs.update_one(self._lease(job), {"$set": updates, "$inc": {"revision": 1}}, **options)
            if fenced.matched_count != 1:
                return
            revoked = code in {"GOVERNANCE_NOT_APPROVED", "RESOURCE_NOT_FOUND", "AUTHENTICATION_REQUIRED", "FORBIDDEN"}
            self.db.index_generations.update_one({"_id": job["resource_ref"]["id"],
                "state": {"$in": ["QUEUED", "BUILDING"]}}, {"$set": {
                    "state": "QUEUED" if again else "REVOKED" if revoked else "FAILED",
                    "failure_code": code, "updated_at": now, "updated_by": job["created_by"]},
                    "$inc": {"revision": 1}}, **options)
            append_event(self.db, actor_id=job["created_by"], workspace_id=job["workspace_id"],
                action="INDEX_BUILD_FAILED", resource_type="INDEX_GENERATION", resource_id=job["resource_ref"]["id"],
                request_id=job["correlation_id"], outcome="ERROR", reason_code=code, session=session)

    def _reconcile_exhausted(self) -> bool:
        changed_any = False
        for job in self.db.jobs.find({"job_type": "INDEX", "state": "FAILED_FINAL", "error_code": "LEASE_EXHAUSTED"}).limit(20):
            with self.indexes.documents.transaction() as session:
                options = _options(session)
                terminal = self.db.jobs.find_one({"_id": job["_id"], "revision": job["revision"],
                    "state": "FAILED_FINAL", "error_code": "LEASE_EXHAUSTED"}, **options)
                if terminal is None:
                    continue
                changed = self.db.index_generations.update_one({"_id": job["resource_ref"]["id"],
                    "state": {"$in": ["QUEUED", "BUILDING"]}}, {"$set": {"state": "FAILED",
                    "failure_code": "LEASE_EXHAUSTED", "updated_at": _now()}, "$inc": {"revision": 1}}, **options)
                changed_any = changed_any or changed.matched_count == 1
        return changed_any

    def process_one(self) -> bool:
        claimed = self.queue.claim(owner=self.owner, lease_seconds=self.lease_seconds, job_type="INDEX")
        if claimed is None:
            return self._reconcile_exhausted()
        job = self.queue.start(job_id=claimed["_id"], owner=self.owner, revision=claimed["revision"])
        if job is None:
            return True
        try:
            generation = self._begin(job)
            _workspace, _document, version = self.indexes._version(job["created_by"], job["workspace_id"], generation["document_version_id"])
            chunks = self.indexes._chunks(version)
            vectors = model = None
            if generation["config_id"] == "research-v0":
                encoded = self.encoder([chunk["text"] for chunk in chunks], generation["config"]["models"]["dense"],
                                       mode="document", timeout_seconds=120)
                vectors = {chunk["chunk_id"]: vector for chunk, vector in zip(chunks, encoded["vectors"], strict=True)}
                model = encoded["metadata"]
                locked = generation["config"]["models"]["dense"]
                if model.get("model") != locked["model"] or model.get("revision") != locked["revision"]:
                    raise DomainError(409, "INDEX_INTEGRITY_FAILED", "Dense model locks differ")
            payload = {"schema_version": 1, "generation_id": str(generation["_id"]),
                "config_sha256": generation["config_sha256"], "chunks": chunks,
                "lexical": build_lexical(chunks), "vectors": vectors, "model": model}
            self._authorized(job)
            key, digest = self.indexes.write_artifact(generation["_id"], payload)
            self._persist(job, payload, key, digest)
        except LeaseLost:
            pass
        except DomainError as error:
            self._fail(job, error.code)
        except EmbeddingRejected as error:
            safe = str(error)
            self._fail(job, safe if safe in {"DENSE_TIMEOUT", "DENSE_MODEL_UNAVAILABLE", "DENSE_INPUT_LIMIT", "DENSE_OUTPUT_INVALID"}
                       else "DENSE_MODEL_UNAVAILABLE", retryable=safe == "DENSE_TIMEOUT")
        except Exception:
            self._fail(job, "INDEX_INTERNAL_ERROR", retryable=True)
        return True
