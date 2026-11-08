"""Immutable product lexical/vector generations, with current authority gates.

Mongo stores the authoritative generation/head. Private JSON files are rebuildable
artifacts, not permission registries. Every read checks both current and pinned
governance, version/chunk integrity, retention and tombstones again.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from research.offline_retrieval.common import tokenize
from .access import object_id
from .audit import append_event
from .documents import DocumentService, _common, _options
from .errors import DomainError
from .provenance import validate_chunk_generation

REPO_ROOT = Path(__file__).resolve().parents[5]
CONFIG_FILES = {
    "bm25-smoke": REPO_ROOT / "services/backend/configs/bm25-smoke.json",
    "research-v0": REPO_ROOT / "research/configs/core-mvp-v0.json",
    "bm25-nli-v1": REPO_ROOT / "services/backend/configs/bm25-nli-v1.json",
    "rrf-nli-v1": REPO_ROOT / "services/backend/configs/rrf-nli-v1.json",
    "bm25-nli-v2": REPO_ROOT / "services/backend/configs/bm25-nli-v2.json",
    "rrf-nli-v2": REPO_ROOT / "services/backend/configs/rrf-nli-v2.json",
    "bm25-p2-llm-v1": REPO_ROOT / "services/backend/configs/bm25-p2-llm-v1.json",
    "bm25-p2-llm-v2": REPO_ROOT / "services/backend/configs/bm25-p2-llm-v2.json",
}
MAX_ARTIFACT_BYTES = 64 * 1024 * 1024


def _now() -> datetime:
    return datetime.now(UTC)


def _bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def locked_config(config_id: str) -> tuple[dict[str, Any], str]:
    if config_id not in CONFIG_FILES:
        raise DomainError(422, "INVALID_CONFIG", "Unknown server configuration")
    payload = CONFIG_FILES[config_id].read_bytes()
    return json.loads(payload), hashlib.sha256(payload).hexdigest()


def dense_index_required(config: dict[str, Any]) -> bool:
    """A locked pipeline's Dense flag determines vector requirements.

    Profile names do not describe which models are actually needed. Source
    generations cover both pipelines; a Dense view in either one requires
    the locked model vectors before that generation can be reused.
    """
    return any(config[name].get("dense_enabled", True)
               for name in ("pipeline1", "pipeline2"))


def _json_value(value: Any) -> Any:
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    return value


def canonical_chunk(raw: dict[str, Any]) -> dict[str, Any]:
    # Operational timestamps/revisions do not belong in an immutable text artifact.
    ignored = {"created_at", "created_by", "updated_at", "updated_by", "revision"}
    chunk = _json_value({key: value for key, value in raw.items() if key not in ignored})
    chunk["chunk_id"] = str(raw["_id"])
    chunk["text"] = raw["normalized_text"]
    for span in chunk.get("source_spans", []):
        span["element_key"] = span.get("stable_element_key", span.get("element_key"))
    return chunk


def build_lexical(chunks: list[dict[str, Any]]) -> dict[str, Any]:
    postings: dict[str, list[list[int]]] = defaultdict(list)
    lengths = []
    for offset, chunk in enumerate(chunks):
        counts = Counter(tokenize(chunk["text"]))
        lengths.append(sum(counts.values()))
        for term, frequency in counts.items():
            postings[term].append([offset, frequency])
    return {"engine": "okapi-bm25-v1", "lengths": lengths,
            "average_length": sum(lengths) / len(lengths) or 1.0,
            "postings": dict(postings)}


class IndexService:
    def __init__(self, database: Any, private_root: Path | str, *, transactional: bool = True):
        self.db = database
        self.documents = DocumentService(database, private_root, transactional=transactional)
        self.artifacts = self.documents.root / "index-artifacts"
        if (self.artifacts.is_symlink() or self.artifacts.exists() and
                (not self.artifacts.is_dir() or self.artifacts.stat().st_mode & 0o077)):
            raise ValueError("Index storage must already be private")
        self.artifacts.mkdir(mode=0o700, exist_ok=True)

    def _version(self, actor_id: ObjectId, workspace_id: ObjectId | str,
                 version_id: ObjectId | str, *, session: Any = None) -> tuple[dict, dict, dict]:
        workspace_id, version_id = object_id(workspace_id), object_id(version_id)
        options = _options(session)
        workspace = self.documents.policy.require(actor_id, workspace_id, "run.create", session=session)
        version = self.db.document_versions.find_one({"_id": version_id, "workspace_id": workspace_id,
            "lifecycle_state": "ACTIVE"}, **options)
        if version is None or self.db.tombstones.find_one({"resource_type": "DOCUMENT_VERSION", "resource_id": version_id}, **options):
            raise DomainError(404, "RESOURCE_NOT_FOUND", "Resource not found")
        _, document = self.documents._document(actor_id, workspace_id, version["document_id"], session=session)
        self.documents.require_governance(workspace, document, session=session)
        self.documents.require_governance(workspace, {**document,
            "current_governance_record_id": version["governance_record_id"]}, session=session)
        file_object = self.db.file_objects.find_one({"_id": version["file_object_id"], "workspace_id": workspace_id,
                                                    "storage_state": "COMMITTED"}, **options)
        if (file_object is None or file_object.get("content_sha256") != version["content_sha256"]
                or self.db.tombstones.find_one({"resource_type": "FILE_OBJECT", "resource_id": version["file_object_id"]}, **options)):
            raise DomainError(409, "FILE_INTEGRITY_FAILED", "File is not available")
        expiry = file_object.get("retention_expires_at")
        if expiry is not None and (expiry.replace(tzinfo=UTC) if expiry.tzinfo is None else expiry) <= _now():
            raise DomainError(409, "GOVERNANCE_NOT_APPROVED", "File retention expired")
        if version["processing_state"] not in {"PARSED", "INDEXING", "READY"} or not version.get("generation_key"):
            raise DomainError(409, "DOCUMENT_NOT_PARSED", "Document must be parsed before indexing")
        return workspace, document, version

    def _chunks(self, version: dict[str, Any], *, session: Any = None) -> list[dict[str, Any]]:
        raw = list(self.db.chunks.find({"workspace_id": version["workspace_id"],
            "document_version_id": version["_id"], "generation_key": version["generation_key"]}, **_options(session)).sort("order", 1))
        if not raw or len(raw) != version["chunk_count"] or len(raw) > 5000:
            raise DomainError(409, "INDEX_INPUT_INVALID", "Incomplete or excessive chunk generation")
        validate_chunk_generation(self.db, version, raw, session=session)
        result = []
        for chunk in raw:
            if (chunk.get("document_id") != version["document_id"] or not chunk.get("source_spans")
                    or hashlib.sha256(chunk["normalized_text"].encode()).hexdigest() != chunk["content_sha256"]
                    or self.db.tombstones.find_one({"resource_type": "CHUNK", "resource_id": chunk["_id"]}, **_options(session))):
                raise DomainError(409, "INDEX_INPUT_INVALID", "Chunk integrity failed")
            result.append(canonical_chunk(chunk))
        return result

    def request(self, actor_id: ObjectId, workspace_id: ObjectId | str,
                version_id: ObjectId | str, config_id: str, *, idempotency_key: str,
                request_id: str, rebuild: bool = False) -> dict[str, Any]:
        workspace_id, version_id = object_id(workspace_id), object_id(version_id)
        if (type(rebuild) is not bool or not isinstance(idempotency_key, str)
                or not 1 <= len(idempotency_key) <= 128):
            raise DomainError(422, "INVALID_REQUEST", "Invalid index request")
        config, config_sha = locked_config(config_id)
        digest = hashlib.sha256(_bytes({"version_id": str(version_id), "config_id": config_id,
            "config_sha256": config_sha, "rebuild": rebuild})).hexdigest()
        try:
            with self.documents.transaction() as session:
                options = _options(session)
                workspace, document, version = self._version(actor_id, workspace_id, version_id, session=session)
                self._chunks(version, session=session)
                prior = self.db.index_operations.find_one({"actor_id": actor_id, "workspace_id": workspace_id,
                    "operation": "INDEX_REQUEST", "idempotency_key": idempotency_key}, **options)
                if prior is not None:
                    if prior["request_sha256"] != digest:
                        raise DomainError(409, "IDEMPOTENCY_CONFLICT", "Key already belongs to another input")
                    return self._get_records(workspace_id, prior["generation_id"], session=session)
                head_query = {"workspace_id": workspace_id, "document_version_id": version_id, "config_id": config_id}
                head = self.db.index_heads.find_one(head_query, **options)
                generation = None
                if head is not None and not rebuild:
                    generation = self.db.index_generations.find_one({"_id": head["requested_generation_id"],
                        "state": {"$in": ["QUEUED", "BUILDING", "ACTIVE"]}, "config_sha256": config_sha,
                        "parser_generation_key": version["generation_key"]}, **options)
                now = _now()
                if generation is None:
                    generation_id, job_id = ObjectId(), ObjectId()
                    number = head["generation_no"] + 1 if head else 1
                    generation = {"_id": generation_id, **_common(actor_id, now), **head_query,
                        "document_id": document["_id"], "governance_record_id": version["governance_record_id"],
                        "purpose": workspace["default_purpose"], "parser_generation_key": version["generation_key"],
                        "config_sha256": config_sha, "config": config, "request_sha256": digest,
                        "generation_no": number, "state": "QUEUED", "artifact_sha256": None, "artifact_key": None,
                        "chunk_count": 0, "dense_dimension": None, "model": None, "failure_code": None,
                        "activated_at": None, "job_id": job_id,
                        "supersedes_generation_id": head.get("active_generation_id") if head else None}
                    self.db.index_generations.insert_one(generation, **options)
                    job = {"_id": job_id, **_common(actor_id, now), "workspace_id": workspace_id, "job_type": "INDEX",
                        "resource_ref": {"type": "INDEX_GENERATION", "id": generation_id, "version_id": version_id},
                        "config_ref": None, "idempotency_scope": "index:" + str(actor_id) + ":" + str(workspace_id),
                        "idempotency_key": str(generation_id), "correlation_id": request_id, "state": "QUEUED",
                        "priority": 0, "available_at": now, "lease_owner": None, "lease_expires_at": None,
                        "heartbeat_at": None, "attempt": 0, "max_attempts": 3, "progress": {"step": "QUEUED"}, "error_code": None}
                    self.db.jobs.insert_one(job, **options)
                    if head:
                        changed = self.db.index_heads.update_one({"_id": head["_id"], "revision": head["revision"]},
                            {"$set": {"requested_generation_id": generation_id, "generation_no": number,
                                "updated_at": now, "updated_by": actor_id}, "$inc": {"revision": 1}}, **options)
                        if changed.matched_count != 1:
                            raise DomainError(409, "REVISION_CONFLICT", "Index generation changed; retry request")
                    else:
                        self.db.index_heads.insert_one({"_id": ObjectId(), **_common(actor_id, now), **head_query,
                            "generation_no": number, "requested_generation_id": generation_id, "active_generation_id": None}, **options)
                    append_event(self.db, actor_id=actor_id, workspace_id=workspace_id, action="INDEX_REQUESTED",
                        resource_type="INDEX_GENERATION", resource_id=generation_id, request_id=request_id, session=session)
                self.db.index_operations.insert_one({"_id": ObjectId(), "schema_version": 1,
                    "created_at": now, "created_by": actor_id, "actor_id": actor_id, "workspace_id": workspace_id,
                    "operation": "INDEX_REQUEST", "idempotency_key": idempotency_key, "request_sha256": digest,
                    "generation_id": generation["_id"], "job_id": generation["job_id"]}, **options)
                return self._get_records(workspace_id, generation["_id"], session=session)
        except DuplicateKeyError:
            raise DomainError(409, "REVISION_CONFLICT", "Index request changed; retry request") from None

    def _get_records(self, workspace_id: ObjectId, generation_id: ObjectId, *, session: Any = None) -> dict[str, Any]:
        generation = self.db.index_generations.find_one({"_id": generation_id, "workspace_id": workspace_id}, **_options(session))
        if generation is None:
            raise DomainError(404, "RESOURCE_NOT_FOUND", "Resource not found")
        job = self.db.jobs.find_one({"_id": generation["job_id"], "workspace_id": workspace_id}, **_options(session))
        return {"generation": generation, "job": job}

    def get(self, actor_id: ObjectId, workspace_id: ObjectId | str, generation_id: ObjectId | str,
            *, session: Any = None) -> dict[str, Any]:
        workspace_id = object_id(workspace_id)
        self.documents.policy.require(actor_id, workspace_id, "run.read", session=session)
        records = self._get_records(workspace_id, object_id(generation_id), session=session)
        self._version(actor_id, workspace_id, records["generation"]["document_version_id"], session=session)
        if self.db.tombstones.find_one({"resource_type": "INDEX_GENERATION", "resource_id": records["generation"]["_id"]}, **_options(session)):
            raise DomainError(404, "RESOURCE_NOT_FOUND", "Resource not found")
        return records

    def write_artifact(self, generation_id: ObjectId, payload: dict[str, Any]) -> tuple[str, str]:
        data = _bytes(payload)
        if len(data) > MAX_ARTIFACT_BYTES:
            raise DomainError(409, "INDEX_INPUT_INVALID", "Index artifact exceeds local limit")
        key = str(generation_id) + ".json"
        path = self.artifacts / key
        if path.exists() or path.is_symlink():
            if path.is_symlink() or path.stat().st_mode & 0o077 or path.read_bytes() != data:
                raise DomainError(409, "INDEX_INTEGRITY_FAILED", "Immutable index artifact conflicts")
        else:
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
            descriptor = os.open(path, flags, 0o600)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            descriptor = os.open(self.artifacts, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        return key, hashlib.sha256(data).hexdigest()

    def get_snapshot(self, actor_id: ObjectId, workspace_id: ObjectId | str, generation_id: ObjectId | str,
                     *, session: Any = None, allow_superseded: bool = True) -> dict[str, Any]:
        generation = self.get(actor_id, workspace_id, generation_id, session=session)["generation"]
        states = {"ACTIVE", "SUPERSEDED"} if allow_superseded else {"ACTIVE"}
        if generation["state"] not in states:
            raise DomainError(409, "INDEX_NOT_READY", "Index generation is not available")
        workspace, document, version = self._version(actor_id, workspace_id, generation["document_version_id"], session=session)
        config, config_sha = locked_config(generation["config_id"])
        if (generation["config_sha256"] != config_sha or generation["config"] != config
                or generation["parser_generation_key"] != version["generation_key"]
                or generation["governance_record_id"] != version["governance_record_id"]
                or generation["purpose"] != workspace["default_purpose"]):
            raise DomainError(409, "INDEX_INTEGRITY_FAILED", "Index locks do not match")
        key = generation.get("artifact_key")
        if not isinstance(key, str) or re.fullmatch(r"[0-9a-f]{24}\.json", key) is None or key != str(generation["_id"]) + ".json":
            raise DomainError(409, "INDEX_INTEGRITY_FAILED", "Invalid index artifact")
        path = self.artifacts / key
        if (path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o077
                or path.stat().st_size > MAX_ARTIFACT_BYTES):
            raise DomainError(409, "INDEX_INTEGRITY_FAILED", "Index artifact is not available")
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != generation["artifact_sha256"]:
            raise DomainError(409, "INDEX_INTEGRITY_FAILED", "Index artifact checksum failed")
        try:
            payload = json.loads(data)
        except (ValueError, RecursionError):
            raise DomainError(409, "INDEX_INTEGRITY_FAILED", "Index artifact is not valid") from None
        chunks = self._chunks(version, session=session)
        if (payload.get("schema_version") != 1 or payload.get("generation_id") != str(generation["_id"])
                or payload.get("chunks") != chunks or payload.get("config_sha256") != config_sha
                or payload.get("lexical") != build_lexical(chunks)
                or len(chunks) != generation["chunk_count"]):
            raise DomainError(409, "INDEX_INTEGRITY_FAILED", "Index content locks failed")
        vectors = payload.get("vectors")
        if dense_index_required(config):
            expected = {chunk["chunk_id"] for chunk in chunks}
            if (not isinstance(vectors, dict) or set(vectors) != expected or generation["dense_dimension"] != 384
                    or payload.get("model") != generation["model"]
                    or not isinstance(payload.get("model"), dict)
                    or payload["model"].get("model") != config["models"]["dense"]["model"]
                    or payload["model"].get("revision") != config["models"]["dense"]["revision"]
                    or any(not isinstance(row, list) or len(row) != 384 for row in vectors.values())
                    or any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
                           for row in vectors.values() for value in row)):
                raise DomainError(409, "INDEX_INTEGRITY_FAILED", "Dense artifact integrity failed")
        elif (vectors is not None or generation["dense_dimension"] is not None
              or payload.get("model") is not None or generation["model"] is not None):
            raise DomainError(409, "INDEX_INTEGRITY_FAILED", "Unexpected dense artifact")
        return {"generation": generation, "document": document, "version": version, "chunks": chunks,
                "config": config, "vectors": vectors, "model": payload.get("model"), "lexical": payload["lexical"]}

    def get_active_snapshot(self, actor_id: ObjectId, workspace_id: ObjectId | str,
                            version_id: ObjectId | str, config_id: str,
                            *, session: Any = None) -> dict[str, Any]:
        workspace_id, version_id = object_id(workspace_id), object_id(version_id)
        self._version(actor_id, workspace_id, version_id, session=session)
        locked_config(config_id)
        head = self.db.index_heads.find_one({"workspace_id": workspace_id,
            "document_version_id": version_id, "config_id": config_id}, **_options(session))
        if head is None or head.get("active_generation_id") is None:
            raise DomainError(409, "INDEX_NOT_READY", "No active index for this version and configuration")
        return self.get_snapshot(actor_id, workspace_id, head["active_generation_id"],
                                 session=session, allow_superseded=False)

    def search(self, actor_id: ObjectId, workspace_id: ObjectId | str, generation_id: ObjectId | str,
               query: str, *, top_k: int = 10) -> list[dict[str, Any]]:
        if not isinstance(query, str) or not 1 <= len(query) <= 20000 or type(top_k) is not int or not 1 <= top_k <= 100:
            raise DomainError(422, "INVALID_REQUEST", "Invalid search request")
        snapshot = self.get_snapshot(actor_id, workspace_id, generation_id)
        index = snapshot["lexical"]
        k1 = float(snapshot["config"]["pipeline1"]["bm25_k1"])
        b = float(snapshot["config"]["pipeline1"]["bm25_b"])
        scores: dict[int, float] = defaultdict(float)
        size = len(snapshot["chunks"])
        for term, query_count in Counter(tokenize(query)).items():
            postings = index["postings"].get(term, [])
            inverse = math.log(1 + (size - len(postings) + 0.5) / (len(postings) + 0.5))
            for offset, frequency in postings:
                denominator = frequency + k1 * (1 - b + b * index["lengths"][offset] / index["average_length"])
                scores[offset] += query_count * inverse * frequency * (k1 + 1) / denominator
        ranked = sorted(scores, key=lambda offset: (-scores[offset], snapshot["chunks"][offset]["chunk_id"]))[:top_k]
        return [{"chunk": snapshot["chunks"][offset], "score": scores[offset], "method": "BM25"} for offset in ranked]
