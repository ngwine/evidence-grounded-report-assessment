"""Locked, deterministic adapter for Cross-Encoder pair scoring.

This module intentionally has no knowledge of retrieval candidates or runner
configuration.  It scores text pairs; candidate selection, document-level
aggregation, and experiment manifests remain responsibilities of the caller.
"""

from __future__ import annotations

import math
from pathlib import Path
import re
from copy import deepcopy
from typing import Any, Protocol, Sequence, runtime_checkable

from .dense import local_model_revision


TextPair = tuple[str, str]
_IMMUTABLE_REVISION = re.compile(r"[0-9a-fA-F]{40,64}")
_EXPLICIT_DEVICE = re.compile(r"(?:cpu|mps|cuda(?::[0-9]+)?)")


@runtime_checkable
class PairScorer(Protocol):
    """Minimal injection boundary used by the offline experiment runner."""

    metadata: dict[str, Any]

    def score_pairs(self, pairs: Sequence[TextPair]) -> Sequence[float]:
        """Return one scalar relevance score for every input pair."""


def _validate_pairs(pairs: Sequence[TextPair]) -> list[TextPair]:
    validated: list[TextPair] = []
    for index, pair in enumerate(pairs):
        if not isinstance(pair, (tuple, list)) or len(pair) != 2:
            raise ValueError(f"Cross-Encoder pair {index} must contain two texts")
        query, passage = pair
        if not isinstance(query, str) or not isinstance(passage, str):
            raise ValueError(f"Cross-Encoder pair {index} must contain strings")
        validated.append((query, passage))
    return validated


def _as_python_values(values: Any) -> Any:
    """Detach optional tensor/array containers without importing their stacks."""

    if hasattr(values, "detach"):
        values = values.detach()
    if hasattr(values, "cpu"):
        values = values.cpu()
    if hasattr(values, "tolist"):
        values = values.tolist()
    return values


def _normalise_scores(values: Any, *, expected: int) -> list[float]:
    values = _as_python_values(values)
    if expected == 1 and not isinstance(values, (list, tuple)):
        values = [values]
    if not isinstance(values, (list, tuple)):
        raise ValueError("Cross-Encoder scorer must return a sequence of scores")
    if len(values) != expected:
        raise ValueError(
            "Cross-Encoder scorer returned the wrong number of scores: "
            f"expected {expected}, got {len(values)}"
        )

    scores: list[float] = []
    for index, value in enumerate(values):
        value = _as_python_values(value)
        if isinstance(value, (list, tuple)):
            if len(value) != 1:
                raise ValueError(
                    "Cross-Encoder must produce one scalar score per pair; "
                    f"pair {index} produced {len(value)} values"
                )
            value = value[0]
        if isinstance(value, bool):
            raise ValueError(f"Cross-Encoder score {index} is not numeric")
        try:
            score = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Cross-Encoder score {index} is not numeric") from exc
        if not math.isfinite(score):
            raise ValueError(f"Cross-Encoder score {index} must be finite")
        # Canonicalise negative zero, which otherwise creates needless artifact
        # differences while being numerically identical to positive zero.
        scores.append(0.0 if score == 0.0 else score)
    return scores


def score_pairs(
    pairs: Sequence[TextPair],
    *,
    scorer: PairScorer,
) -> list[float]:
    """Score pairs through an injected implementation with strict validation."""

    validated = _validate_pairs(pairs)
    if not validated:
        return []
    return _normalise_scores(
        scorer.score_pairs(validated),
        expected=len(validated),
    )


class MemoizedPairScorer:
    """Reuse exact pair scores across locked ablation methods.

    A4 and A5 often ask the same Cross-Encoder to score the same Dense support
    passage. Caching the immutable ``(query, passage)`` pair avoids redundant
    inference without changing candidate sets or ranking semantics.
    """

    def __init__(self, scorer: PairScorer) -> None:
        self._scorer = scorer
        self._cache: dict[TextPair, float] = {}
        self.metadata = deepcopy(scorer.metadata)
        self.metadata["exact_pair_memoization"] = {
            "enabled": True,
            "requests": 0,
            "cache_hits": 0,
            "unique_pairs_scored": 0,
        }

    def score_pairs(self, pairs: Sequence[TextPair]) -> list[float]:
        validated = _validate_pairs(pairs)
        missing: list[TextPair] = []
        pending: set[TextPair] = set()
        hits = 0
        for pair in validated:
            if pair in self._cache or pair in pending:
                hits += 1
                continue
            pending.add(pair)
            missing.append(pair)
        if missing:
            new_scores = score_pairs(missing, scorer=self._scorer)
            self._cache.update(zip(missing, new_scores))
        stats = self.metadata["exact_pair_memoization"]
        stats["requests"] += len(validated)
        stats["cache_hits"] += hits
        stats["unique_pairs_scored"] = len(self._cache)
        return [self._cache[pair] for pair in validated]


def locked_model_revision(model: str | Path, revision: str) -> tuple[str, str]:
    """Resolve a model reference and prove that its revision is immutable.

    Local directories are locked by the same content-and-path checksum used by
    the Dense adapter.  Hugging Face cache identifiers must be accompanied by
    an exact 40--64 hexadecimal commit, never a mutable branch or tag.

    Returns ``(model_reference, resolved_revision)``.  A local model reference
    is converted to an absolute path so the loaded bytes are unambiguous.
    """

    model_text = str(model)
    if not model_text:
        raise ValueError("Cross-Encoder model must be specified")
    if not revision or revision.startswith("SET_"):
        raise ValueError("Cross-Encoder model and exact revision/checksum must be locked")

    model_path = Path(model_text).expanduser()
    if model_path.exists():
        if not model_path.is_dir():
            raise ValueError("Cross-Encoder local model path must be a directory")
        model_path = model_path.resolve()
        actual_revision = local_model_revision(model_path)
        if revision != actual_revision:
            raise ValueError(
                "Cross-Encoder local model checksum mismatch; expected revision "
                f"{revision}, got {actual_revision}"
            )
        return str(model_path), actual_revision

    if _IMMUTABLE_REVISION.fullmatch(revision) is None:
        raise ValueError(
            "Cached Cross-Encoder model revision must be an immutable "
            "40–64 hex commit"
        )
    return model_text, revision


class SentenceTransformersCrossEncoder:
    """Scalar pair scorer backed by a locked SentenceTransformers model.

    The adapter never downloads a model.  Inference is explicitly batched so
    CPU and Apple MPS runs have bounded pair memory, and results are returned as
    finite built-in ``float`` values in input order.
    """

    def __init__(
        self,
        *,
        model: str | Path,
        revision: str,
        device: str = "cpu",
        batch_size: int = 16,
        max_length: int | None = None,
    ) -> None:
        if _EXPLICIT_DEVICE.fullmatch(device) is None:
            raise ValueError(
                "Cross-Encoder device must be explicit: cpu, mps, cuda, or cuda:N"
            )
        if isinstance(batch_size, bool) or not isinstance(batch_size, int) or batch_size <= 0:
            raise ValueError("Cross-Encoder batch_size must be a positive integer")
        if max_length is not None and (
            isinstance(max_length, bool)
            or not isinstance(max_length, int)
            or max_length <= 0
        ):
            raise ValueError("Cross-Encoder max_length must be a positive integer")

        model_reference, resolved_revision = locked_model_revision(model, revision)
        is_local = Path(model_reference).is_dir()
        try:
            from sentence_transformers import CrossEncoder
        except ImportError as exc:  # pragma: no cover - optional environment.
            raise RuntimeError(
                "Cross-Encoder reranking requires the optional research "
                "environment; install research/requirements-research.txt"
            ) from exc

        model_kwargs: dict[str, Any] = {
            "device": device,
            "local_files_only": True,
        }
        if max_length is not None:
            model_kwargs["max_length"] = max_length
        if not is_local:
            model_kwargs["revision"] = resolved_revision

        self._model = CrossEncoder(model_reference, **model_kwargs)
        underlying_model = getattr(self._model, "model", None)
        eval_method = getattr(underlying_model, "eval", None)
        if callable(eval_method):
            eval_method()
        self._batch_size = batch_size
        self.metadata = {
            "backend": "sentence_transformers_cross_encoder",
            "model": str(model),
            "resolved_model": model_reference,
            "revision": resolved_revision,
            "device": device,
            "batch_size": batch_size,
            "max_length": max_length,
            "local_files_only": True,
            "output": "scalar_float",
        }

    def score_pairs(self, pairs: Sequence[TextPair]) -> list[float]:
        validated = _validate_pairs(pairs)
        scores: list[float] = []
        for start in range(0, len(validated), self._batch_size):
            batch = validated[start : start + self._batch_size]
            predicted = self._model.predict(
                batch,
                batch_size=self._batch_size,
                show_progress_bar=False,
                convert_to_numpy=True,
            )
            scores.extend(_normalise_scores(predicted, expected=len(batch)))
        return scores


# More explicit alias for call sites that name the role rather than the model.
SentenceTransformersCrossEncoderScorer = SentenceTransformersCrossEncoder
