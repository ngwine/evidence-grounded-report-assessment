"""Dense retrieval adapter; the scientific path requires a real local model."""

from __future__ import annotations

import math
from pathlib import Path
import hashlib
import re
from typing import Any, Iterable, Protocol, Sequence


class Encoder(Protocol):
    metadata: dict[str, Any]

    def encode(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        """Encode texts into fixed-width numeric vectors."""


def local_model_revision(model_path: str | Path) -> str:
    """Return the immutable directory checksum used in Dense manifests."""

    root = Path(model_path)
    if not root.is_dir():
        raise ValueError("Dense local model path must be a directory")
    digest = hashlib.sha256()
    for path in sorted(value for value in root.rglob("*") if value.is_file()):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(relative)
        digest.update(b"\0")
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    return "sha256:" + digest.hexdigest()


class SentenceTransformerEncoder:
    """Load a SentenceTransformers model without network access."""

    def __init__(
        self,
        *,
        model: str,
        revision: str,
        device: str = "cpu",
        batch_size: int = 16,
        query_prefix: str = "",
        document_prefix: str = "",
    ) -> None:
        if not model or not revision or revision.startswith("SET_"):
            raise ValueError("Dense model and exact revision/checksum must be locked")
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "Dense retrieval requires the optional research environment; "
                "install research/requirements-research.txt in Python 3.12"
            ) from exc

        model_path = Path(model)
        resolved_revision = revision
        kwargs: dict[str, Any] = {
            "device": device,
            "local_files_only": True,
        }
        if model_path.exists():
            actual_revision = local_model_revision(model_path)
            if revision != actual_revision:
                raise ValueError(
                    "Dense local model checksum mismatch; expected revision "
                    f"{revision}, got {actual_revision}"
                )
            resolved_revision = actual_revision
        else:
            if not re.fullmatch(r"[0-9a-fA-F]{40,64}", revision):
                raise ValueError(
                    "Remote/cached Dense model revision must be an immutable 40–64 hex commit"
                )
            kwargs["revision"] = revision
        self._model = SentenceTransformer(model, **kwargs)
        self._batch_size = batch_size
        self._query_prefix = query_prefix
        self._document_prefix = document_prefix
        self._mode = "document"
        self.metadata = {
            "backend": "sentence_transformers",
            "model": model,
            "revision": resolved_revision,
            "device": device,
            "batch_size": batch_size,
            "local_files_only": True,
            "query_prefix": query_prefix,
            "document_prefix": document_prefix,
        }

    def set_mode(self, mode: str) -> None:
        if mode not in {"query", "document"}:
            raise ValueError("Dense encoder mode must be query or document")
        self._mode = mode

    def encode(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        prefix = self._query_prefix if self._mode == "query" else self._document_prefix
        values = [prefix + text for text in texts]
        return self._model.encode(
            values,
            batch_size=self._batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        ).tolist()


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or not left:
        raise ValueError("Dense vectors must be non-empty and have the same dimension")
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)


def rank_dense(
    corpus: Iterable[dict[str, Any]],
    queries: Iterable[dict[str, Any]],
    *,
    encoder: Encoder,
    top_k: int,
) -> dict[str, list[dict[str, Any]]]:
    if top_k <= 0:
        raise ValueError("top_k must be positive")
    items = list(corpus)
    query_items = list(queries)
    if hasattr(encoder, "set_mode"):
        encoder.set_mode("document")
    corpus_vectors = list(encoder.encode([str(item["text"]) for item in items]))
    if len(corpus_vectors) != len(items):
        raise ValueError("Dense encoder returned the wrong number of corpus vectors")
    if hasattr(encoder, "set_mode"):
        encoder.set_mode("query")
    query_vectors = list(encoder.encode([str(query["text"]) for query in query_items]))
    if len(query_vectors) != len(query_items):
        raise ValueError("Dense encoder returned the wrong number of query vectors")

    results: dict[str, list[dict[str, Any]]] = {}
    for query, query_vector in zip(query_items, query_vectors):
        query_id = str(query["query_id"])
        scored = [
            (_cosine(query_vector, vector), str(item["chunk_id"]), item)
            for item, vector in zip(items, corpus_vectors)
        ]
        scored.sort(key=lambda row: (-row[0], row[1]))
        results[query_id] = [
            {
                "chunk_id": chunk_id,
                "document_id": item["document_id"],
                "score": score,
                "rank": rank,
                "source_spans": item.get("source_spans", []),
            }
            for rank, (score, chunk_id, item) in enumerate(scored[:top_k], 1)
        ]
    return results
