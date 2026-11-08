"""Private, immutable exact-cosine vector generations for a local W5.2 baseline.

This adapter deliberately does not decide which sources a user may read.  The
caller must obtain an *authoritative, current* list of allowed document-version
IDs before every search.  Build-time governance fields are a validated snapshot,
not an authentication or revocation service.  No model is loaded here.
"""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Iterator, Mapping, Sequence


SCHEMA_VERSION = 1
ENGINE = "local-exact-cosine-v1"
_GENERATION_RE = re.compile(r"vec-[0-9a-f]{64}\Z")
_SHA_RE = re.compile(r"[0-9a-fA-F]{64}\Z")
_VERSION_FIELDS = (
    "workspace_id",
    "document_id",
    "document_version_id",
    "content_sha256",
    "lifecycle_state",
    "processing_state",
    "governance_state",
    "allowed_purposes",
    "tombstoned",
    "rights_basis",
    "approver",
    "approved_at",
)


def _canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("Index metadata must be finite, JSON-serializable data") from exc


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _vector(value: Any, field: str, *, dimension: int | None = None) -> list[float]:
    if not isinstance(value, (list, tuple)) or not value:
        raise ValueError(f"{field} must be a non-empty numeric vector")
    result: list[float] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ValueError(f"{field} must contain only finite numbers")
        number = float(item)
        if not math.isfinite(number):
            raise ValueError(f"{field} must contain only finite numbers")
        result.append(0.0 if number == 0 else number)
    if dimension is not None and len(result) != dimension:
        raise ValueError(f"{field} has dimension {len(result)}, expected {dimension}")
    if not any(result):
        raise ValueError(f"{field} cannot be a zero vector")
    return result


def _unit_vector(values: Sequence[float]) -> list[float]:
    # Scale first: a finite vector can still have a norm exceeding float64.
    scale = max(abs(value) for value in values)
    scaled = [value / scale for value in values]
    norm = math.hypot(*scaled)
    return [value / norm for value in scaled]


def _version_records(
    values: Sequence[Mapping[str, Any]], *, workspace_id: str, purpose: str,
) -> list[dict[str, Any]]:
    if not isinstance(values, (list, tuple)) or not values:
        raise ValueError("corpus_versions must be a non-empty list")
    records: list[dict[str, Any]] = []
    seen_versions: set[str] = set()
    seen_documents: set[str] = set()
    for index, value in enumerate(values):
        if not isinstance(value, Mapping):
            raise ValueError(f"corpus_versions[{index}] must be an object")
        record = {key: deepcopy(value.get(key)) for key in _VERSION_FIELDS}
        version_id = _text(record["document_version_id"], "document_version_id")
        document_id = _text(record["document_id"], "document_id")
        if version_id in seen_versions or document_id in seen_documents:
            raise ValueError("Duplicate document/version in one vector generation")
        seen_versions.add(version_id)
        seen_documents.add(document_id)
        if record["workspace_id"] != workspace_id:
            raise ValueError("Corpus version belongs to a different workspace")
        digest = record["content_sha256"]
        if not isinstance(digest, str) or not _SHA_RE.fullmatch(digest):
            raise ValueError(f"Invalid content_sha256 for {version_id}")
        record["content_sha256"] = digest.lower()
        if (
            record["lifecycle_state"] != "ACTIVE"
            or record["processing_state"] != "READY"
            or record["governance_state"] != "APPROVED"
            or record["tombstoned"] is not False
        ):
            raise ValueError(f"Document version {version_id} is not indexable")
        purposes = record["allowed_purposes"]
        if (
            not isinstance(purposes, list)
            or not purposes
            or not all(isinstance(item, str) and item for item in purposes)
            or len(purposes) != len(set(purposes))
            or purpose not in purposes
        ):
            raise ValueError(f"Purpose {purpose} is not approved for {version_id}")
        record["allowed_purposes"] = sorted(purposes)
        for field in ("rights_basis", "approver", "approved_at"):
            record[field] = _text(record[field], f"{version_id}.{field}")
        records.append(record)
    return sorted(records, key=lambda item: item["document_version_id"])


def _chunk_records(
    values: Sequence[Mapping[str, Any]],
    *, versions: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    if not isinstance(values, (list, tuple)) or not values:
        raise ValueError("chunks must be a non-empty list")
    by_version = {item["document_version_id"]: item for item in versions}
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    dimension: int | None = None
    for index, value in enumerate(values):
        if not isinstance(value, Mapping):
            raise ValueError(f"chunks[{index}] must be an object")
        chunk_id = _text(value.get("chunk_id"), "chunk_id")
        if chunk_id in seen:
            raise ValueError(f"Duplicate chunk_id: {chunk_id}")
        seen.add(chunk_id)
        version_id = _text(value.get("document_version_id"), "document_version_id")
        version = by_version.get(version_id)
        if version is None or value.get("document_id", version["document_id"]) != version["document_id"]:
            raise ValueError(f"Chunk {chunk_id} has unknown/mismatched document version")
        spans = value.get("source_spans")
        if not isinstance(spans, list) or not spans or not all(
            isinstance(span, Mapping) and span.get("element_key") and
            isinstance(span.get("locator"), Mapping)
            for span in spans
        ):
            raise ValueError(f"Chunk {chunk_id} requires authoritative source_spans")
        content_hash = value.get("content_sha256")
        if not isinstance(content_hash, str) or not _SHA_RE.fullmatch(content_hash):
            raise ValueError(f"Chunk {chunk_id} requires content_sha256")
        vector = _vector(value.get("vector"), f"chunks[{index}].vector", dimension=dimension)
        dimension = len(vector)
        record = {
            "chunk_id": chunk_id,
            "document_id": version["document_id"],
            "document_version_id": version_id,
            "content_sha256": content_hash.lower(),
            "source_spans": deepcopy(spans),
            "vector": vector,
        }
        _canonical_bytes(record)
        records.append(record)
    assert dimension is not None
    return sorted(records, key=lambda item: item["chunk_id"]), dimension


def _manifest(payload: Mapping[str, Any], payload_bytes: bytes) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "engine": ENGINE,
        "generation_id": "vec-" + _sha256(payload_bytes),
        "payload_filename": "vectors.json",
        "payload_sha256": _sha256(payload_bytes),
        "payload_size_bytes": len(payload_bytes),
        "workspace_id": payload["workspace_id"],
        "purpose": payload["purpose"],
        "dimension": payload["dimension"],
        "chunk_count": len(payload["chunks"]),
        "corpus_versions": payload["corpus_versions"],
        "model": payload["model"],
        "config": payload["config"],
        "local_state": "READY_NOT_ACTIVE",
    }


def _private_regular_file(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Missing or non-regular index file: {path.name}")
    mode = path.stat().st_mode
    if mode & 0o077:
        raise PermissionError(f"Index file is not private: {path.name}")
    return path.read_bytes()


def _write_private(path: Path, value: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(value)
        stream.flush()
        os.fsync(stream.fileno())


class LocalExactVectorIndex:
    """A rebuildable local artifact, never an authoritative permissions registry."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).absolute()
        probe = self.root
        while probe != probe.parent:
            if probe.is_symlink():
                raise ValueError("Index path must not traverse a symlink")
            probe = probe.parent
        self.root.mkdir(parents=True, mode=0o700, exist_ok=True)
        if not self.root.is_dir() or self.root.stat().st_mode & 0o077:
            raise PermissionError("Index directory must be private (0700)")

    @contextmanager
    def _build_lock(self) -> Iterator[None]:
        lock_path = self.root / ".build.lock"
        flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(lock_path, flags, 0o600)
        try:
            if os.fstat(fd).st_mode & 0o077:
                raise PermissionError("Index build lock must be private")
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def load(self, generation_id: str) -> dict[str, Any]:
        if not isinstance(generation_id, str) or not _GENERATION_RE.fullmatch(generation_id):
            raise ValueError("Invalid vector generation ID")
        directory = self.root / generation_id
        if directory.is_symlink() or not directory.is_dir():
            raise ValueError("Vector generation does not exist")
        if directory.stat().st_mode & 0o077:
            raise PermissionError("Vector generation directory must be private")
        payload_bytes = _private_regular_file(directory / "vectors.json")
        manifest_bytes = _private_regular_file(directory / "manifest.json")
        try:
            payload = json.loads(payload_bytes)
            manifest = json.loads(manifest_bytes)
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("Vector generation JSON is corrupt") from exc
        if not isinstance(payload, dict) or not isinstance(manifest, dict):
            raise ValueError("Vector generation files must be objects")
        if payload_bytes != _canonical_bytes(payload):
            raise ValueError("Vector payload is not canonical")
        if payload.get("schema_version") != SCHEMA_VERSION or payload.get("engine") != ENGINE:
            raise ValueError("Unsupported vector generation schema/engine")
        expected = _manifest(payload, payload_bytes)
        if expected["generation_id"] != generation_id or manifest != expected:
            raise ValueError("Vector generation ID/manifest/checksum mismatch")
        if manifest_bytes != _canonical_bytes(manifest):
            raise ValueError("Vector manifest is not canonical")
        # Revalidate all rows, not only the file digest. This also refuses a
        # self-consistent but malformed generation imported from elsewhere.
        workspace_id = _text(payload.get("workspace_id"), "workspace_id")
        purpose = _text(payload.get("purpose"), "purpose")
        versions = _version_records(
            payload.get("corpus_versions"), workspace_id=workspace_id, purpose=purpose,
        )
        chunks, dimension = _chunk_records(payload.get("chunks"), versions=versions)
        if (
            versions != payload["corpus_versions"]
            or chunks != payload["chunks"]
            or dimension != payload.get("dimension")
        ):
            raise ValueError("Vector generation content is not normalized/valid")
        return {"manifest": deepcopy(manifest), "payload": deepcopy(payload)}

    def _check_version_reuse(self, payload: Mapping[str, Any], generation_id: str) -> None:
        versions = {
            item["document_version_id"]: (item["workspace_id"], item["content_sha256"])
            for item in payload["corpus_versions"]
        }
        scope = {
            key: payload[key]
            for key in ("workspace_id", "purpose", "corpus_versions", "model", "config")
        }
        for directory in self.root.iterdir():
            if not _GENERATION_RE.fullmatch(directory.name):
                continue
            previous = self.load(directory.name)["payload"]
            previous_versions = {
                item["document_version_id"]: (item["workspace_id"], item["content_sha256"])
                for item in previous["corpus_versions"]
            }
            for version_id in versions.keys() & previous_versions.keys():
                if versions[version_id] != previous_versions[version_id]:
                    raise ValueError(f"Immutable document version reused with changed content: {version_id}")
            previous_scope = {
                key: previous[key]
                for key in ("workspace_id", "purpose", "corpus_versions", "model", "config")
            }
            if scope == previous_scope and directory.name != generation_id:
                raise ValueError("Identical corpus/model/config produced different vector generation")

    def build(
        self,
        *,
        workspace_id: str,
        purpose: str,
        corpus_versions: Sequence[Mapping[str, Any]],
        model: Mapping[str, Any],
        config: Mapping[str, Any],
        chunks: Sequence[Mapping[str, Any]],
    ) -> str:
        workspace_id = _text(workspace_id, "workspace_id")
        purpose = _text(purpose, "purpose")
        if not isinstance(model, Mapping):
            raise ValueError("model must be an object")
        model_record = {
            "name": _text(model.get("name"), "model.name"),
            "revision": _text(model.get("revision"), "model.revision"),
        }
        if not re.fullmatch(
            r"(?:sha256:)?[0-9a-fA-F]{40,64}", model_record["revision"]
        ):
            raise ValueError("model.revision must be an immutable commit/checksum")
        if not isinstance(config, Mapping):
            raise ValueError("config must be an object")
        config_record = deepcopy(dict(config))
        for field in ("parser_version", "chunker_version", "code_version"):
            _text(config_record.get(field), f"config.{field}")
        _canonical_bytes(config_record)
        versions = _version_records(corpus_versions, workspace_id=workspace_id, purpose=purpose)
        rows, dimension = _chunk_records(chunks, versions=versions)
        payload = {
            "schema_version": SCHEMA_VERSION,
            "engine": ENGINE,
            "workspace_id": workspace_id,
            "purpose": purpose,
            "corpus_versions": versions,
            "model": model_record,
            "config": config_record,
            "dimension": dimension,
            "chunks": rows,
        }
        payload_bytes = _canonical_bytes(payload)
        manifest = _manifest(payload, payload_bytes)
        generation_id = manifest["generation_id"]
        with self._build_lock():
            self._check_version_reuse(payload, generation_id)
            target = self.root / generation_id
            if target.exists() or target.is_symlink():
                self.load(generation_id)
                return generation_id
            temporary = Path(tempfile.mkdtemp(prefix=".building-", dir=self.root))
            try:
                _write_private(temporary / "vectors.json", payload_bytes)
                _write_private(temporary / "manifest.json", _canonical_bytes(manifest))
                os.rename(temporary, target)
            except BaseException:
                for name in ("vectors.json", "manifest.json"):
                    (temporary / name).unlink(missing_ok=True)
                temporary.rmdir()
                raise
        return generation_id

    def search(
        self,
        generation_id: str,
        query_vector: Sequence[float],
        *,
        workspace_id: str,
        purpose: str,
        allowed_document_version_ids: Sequence[str],
        top_k: int,
    ) -> list[dict[str, Any]]:
        if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k <= 0:
            raise ValueError("top_k must be a positive integer")
        if isinstance(allowed_document_version_ids, (str, bytes)) or not isinstance(
            allowed_document_version_ids, (list, tuple, set, frozenset)
        ):
            raise ValueError("Explicit allowed_document_version_ids are required")
        allowed: set[str] = set()
        for version_id in allowed_document_version_ids:
            allowed.add(_text(version_id, "allowed_document_version_ids item"))
        stored = self.load(generation_id)
        payload = stored["payload"]
        if workspace_id != payload["workspace_id"] or purpose != payload["purpose"]:
            raise PermissionError("Vector generation workspace/purpose does not match")
        query = _vector(query_vector, "query_vector", dimension=payload["dimension"])
        unit_query = _unit_vector(query)
        scored: list[tuple[float, dict[str, Any]]] = []
        for row in payload["chunks"]:
            # Authorization and version filtering happen before any score call.
            if row["document_version_id"] not in allowed:
                continue
            vector = _unit_vector(row["vector"])
            score = math.fsum(
                left * right for left, right in zip(unit_query, vector)
            )
            if not math.isfinite(score):
                raise ValueError("Cosine score is not finite")
            score = max(-1.0, min(1.0, score))
            scored.append((score, row))
        scored.sort(key=lambda item: (-item[0], item[1]["chunk_id"]))
        return [
            {
                "rank": rank,
                "score": score,
                "score_type": "exact_cosine",
                "generation_id": generation_id,
                "workspace_id": payload["workspace_id"],
                "chunk_id": row["chunk_id"],
                "document_id": row["document_id"],
                "document_version_id": row["document_version_id"],
                "content_sha256": row["content_sha256"],
                "source_spans": deepcopy(row["source_spans"]),
            }
            for rank, (score, row) in enumerate(scored[:top_k], 1)
        ]
