"""Dense retrieval adapter; the scientific path requires a real local model."""

from __future__ import annotations

import hashlib
import heapq
import math
from pathlib import Path
import re
from typing import Any, Iterable, Protocol, Sequence

from .aggregation import render_ranked_candidates

try:  # NumPy is present in research runs but optional for core-only installs.
    import numpy as _np
except ImportError:  # pragma: no cover - exercised by the dependency-light environment.
    _np = None


_QUERY_SCORE_BATCH_SIZE = 32


class Encoder(Protocol):
    metadata: dict[str, Any]

    def encode(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        """Encode texts into fixed-width numeric vectors."""


class MultiDeviceEncoder:
    """Encode one batch of texts on several encoders (one per GPU) in parallel.

    Texts are dealt out round-robin so every device gets a similar length mix,
    then re-assembled in the original order. Each underlying encoder is a full,
    independent copy of the same locked model.
    """

    def __init__(self, encoders: Sequence[Any]) -> None:
        if len(encoders) < 2:
            raise ValueError("MultiDeviceEncoder needs at least two encoders")
        self._encoders = list(encoders)
        first = dict(getattr(self._encoders[0], "metadata", {}))
        first["devices"] = [
            getattr(encoder, "metadata", {}).get("device") for encoder in self._encoders
        ]
        first.pop("device", None)
        self.metadata = first

    def set_mode(self, mode: str) -> None:
        for encoder in self._encoders:
            if hasattr(encoder, "set_mode"):
                encoder.set_mode(mode)

    def encode(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        from concurrent.futures import ThreadPoolExecutor

        count = len(self._encoders)
        if len(texts) < count:
            return self._encoders[0].encode(texts)
        shards = [list(texts[offset::count]) for offset in range(count)]
        with ThreadPoolExecutor(max_workers=count) as pool:
            parts = list(pool.map(lambda pair: pair[0].encode(pair[1]), zip(self._encoders, shards)))
        merged: list[Any] = [None] * len(texts)
        for offset, part in enumerate(parts):
            if len(part) != len(shards[offset]):
                raise ValueError("Dense encoder returned the wrong number of vectors")
            for position, vector in enumerate(part):
                merged[offset + position * count] = vector
        return merged


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
        dtype: str = "float32",
    ) -> None:
        if dtype not in {"float32", "float16"}:
            raise ValueError("Dense dtype must be float32 or float16")
        if dtype == "float16" and not str(device).startswith("cuda"):
            raise ValueError("Dense dtype float16 requires a CUDA device")
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
        if dtype == "float16":
            self._model.half()
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
            "dtype": dtype,
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
        )


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or len(left) == 0:
        raise ValueError("Dense vectors must be non-empty and have the same dimension")
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)


def _rank_dense_python(
    items: Sequence[dict[str, Any]],
    query_items: Sequence[dict[str, Any]],
    corpus_vectors: Sequence[Sequence[float]],
    query_vectors: Sequence[Sequence[float]],
    *,
    top_k: int,
    group_by_document: bool,
) -> dict[str, list[dict[str, Any]]]:
    """Reference implementation and safe fallback when NumPy is unavailable."""

    results: dict[str, list[dict[str, Any]]] = {}
    for query, query_vector in zip(query_items, query_vectors):
        query_id = str(query["query_id"])
        scored = [
            (_cosine(query_vector, vector), str(item["chunk_id"]), item)
            for item, vector in zip(items, corpus_vectors)
        ]
        results[query_id] = render_ranked_candidates(
            scored,
            top_k=top_k,
            group_by_document=group_by_document,
        )
    return results


def _validate_vector_dimensions(
    corpus_vectors: Sequence[Sequence[float]],
    query_vectors: Sequence[Sequence[float]],
) -> None:
    """Validate the rectangular matrices before handing them to NumPy."""

    dimension = len(corpus_vectors[0])
    if not dimension:
        raise ValueError("Dense vectors must be non-empty and have the same dimension")
    if any(len(vector) != dimension for vector in corpus_vectors) or any(
        len(vector) != dimension for vector in query_vectors
    ):
        raise ValueError("Dense vectors must be non-empty and have the same dimension")


def _select_top_chunk_indices(
    scores: Any,
    chunk_ids: Sequence[str],
    *,
    top_k: int,
) -> list[int]:
    """Select top chunks without sorting the full corpus in the common case.

    NumPy's partition chooses an arbitrary member when several rows tie at the
    cutoff. We explicitly collect the complete cutoff tie and choose the
    lexicographically smallest chunk IDs, matching ``render_ranked_candidates``.
    """

    count = len(chunk_ids)
    limit = min(top_k, count)
    if limit == count:
        selected = list(range(count))
    else:
        threshold = float(_np.partition(scores, count - limit)[count - limit])
        selected = _np.flatnonzero(scores > threshold).tolist()
        remaining = limit - len(selected)
        tied = _np.flatnonzero(scores == threshold).tolist()
        if remaining < len(tied):
            tied = heapq.nsmallest(
                remaining,
                tied,
                key=lambda index: chunk_ids[index],
            )
        selected.extend(tied)
    selected.sort(key=lambda index: (-float(scores[index]), chunk_ids[index]))
    return selected[:limit]


def _document_groups(
    items: Sequence[dict[str, Any]],
    chunk_ids: Sequence[str],
) -> list[tuple[str, Any]]:
    """Precompute chunk indices per document in chunk-ID tie-break order."""

    indices_by_document: dict[str, list[int]] = {}
    for index, item in enumerate(items):
        document_id = item.get("document_id")
        if not isinstance(document_id, str) or not document_id:
            raise ValueError("Every retrieval candidate requires document_id")
        indices_by_document.setdefault(document_id, []).append(index)

    return [
        (
            document_id,
            _np.asarray(
                sorted(indices, key=lambda index: chunk_ids[index]),
                dtype=_np.intp,
            ),
        )
        for document_id, indices in indices_by_document.items()
    ]


def _select_top_document_indices(
    scores: Any,
    groups: Sequence[tuple[str, Any]],
    chunk_ids: Sequence[str],
    *,
    top_k: int,
) -> list[int]:
    """Select the best chunk per document before applying top-k."""

    best: list[tuple[int, str]] = []
    for document_id, indices in groups:
        # The group is ordered by chunk ID. np.argmax keeps its first maximum,
        # so exact score ties select the same chunk as the Python renderer.
        best_index = int(indices[int(_np.argmax(scores[indices]))])
        best.append((best_index, document_id))
    best.sort(
        key=lambda value: (
            -float(scores[value[0]]),
            value[1],
            chunk_ids[value[0]],
        )
    )
    return [index for index, _document_id in best[:top_k]]


def _rank_dense_numpy(
    items: Sequence[dict[str, Any]],
    query_items: Sequence[dict[str, Any]],
    corpus_vectors: Sequence[Sequence[float]],
    query_vectors: Sequence[Sequence[float]],
    *,
    top_k: int,
    group_by_document: bool,
) -> dict[str, list[dict[str, Any]]]:
    """Vectorized cosine scoring with bounded query-score memory."""

    _validate_vector_dimensions(corpus_vectors, query_vectors)
    corpus_matrix = _np.asarray(corpus_vectors, dtype=_np.float64)
    query_matrix = _np.asarray(query_vectors, dtype=_np.float64)
    if corpus_matrix.ndim != 2 or query_matrix.ndim != 2:
        raise ValueError("Dense vectors must be non-empty and have the same dimension")

    # Preserve the reference implementation's behavior for unusual non-finite
    # inputs rather than relying on platform-specific BLAS/partition handling.
    if not _np.isfinite(corpus_matrix).all() or not _np.isfinite(query_matrix).all():
        return _rank_dense_python(
            items,
            query_items,
            corpus_vectors,
            query_vectors,
            top_k=top_k,
            group_by_document=group_by_document,
        )

    corpus_norms = _np.linalg.norm(corpus_matrix, axis=1)
    query_norms = _np.linalg.norm(query_matrix, axis=1)
    chunk_ids = [str(item["chunk_id"]) for item in items]
    groups = _document_groups(items, chunk_ids) if group_by_document else []
    results: dict[str, list[dict[str, Any]]] = {}

    for start in range(0, len(query_items), _QUERY_SCORE_BATCH_SIZE):
        stop = min(start + _QUERY_SCORE_BATCH_SIZE, len(query_items))
        dots = query_matrix[start:stop] @ corpus_matrix.T
        denominators = query_norms[start:stop, None] * corpus_norms[None, :]
        score_batch = _np.zeros_like(dots)
        _np.divide(dots, denominators, out=score_batch, where=denominators != 0)

        for offset, scores in enumerate(score_batch):
            query = query_items[start + offset]
            query_id = str(query["query_id"])
            if group_by_document:
                selected = _select_top_document_indices(
                    scores,
                    groups,
                    chunk_ids,
                    top_k=top_k,
                )
            else:
                selected = _select_top_chunk_indices(
                    scores,
                    chunk_ids,
                    top_k=top_k,
                )
            scored = [
                (float(scores[index]), chunk_ids[index], items[index])
                for index in selected
            ]
            results[query_id] = render_ranked_candidates(
                scored,
                top_k=top_k,
                group_by_document=group_by_document,
            )
    return results


def rank_dense(
    corpus: Iterable[dict[str, Any]],
    queries: Iterable[dict[str, Any]],
    *,
    encoder: Encoder,
    top_k: int,
    group_by_document: bool = False,
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
    if not query_items:
        return {}
    if not items:
        return {str(query["query_id"]): [] for query in query_items}
    if _np is None:
        return _rank_dense_python(
            items,
            query_items,
            corpus_vectors,
            query_vectors,
            top_k=top_k,
            group_by_document=group_by_document,
        )
    return _rank_dense_numpy(
        items,
        query_items,
        corpus_vectors,
        query_vectors,
        top_k=top_k,
        group_by_document=group_by_document,
    )
