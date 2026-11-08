"""Locked, deterministic adapter for Cross-Encoder pair scoring.

This module intentionally has no knowledge of retrieval candidates or runner
configuration.  It scores text pairs; candidate selection, document-level
aggregation, and experiment manifests remain responsibilities of the caller.
"""

from __future__ import annotations

import math
from pathlib import Path
import re
import time
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
            tokenization = getattr(self._scorer, "metadata", {}).get("tokenization")
            if isinstance(tokenization, dict):
                self.metadata["tokenization"] = deepcopy(tokenization)
        stats = self.metadata["exact_pair_memoization"]
        stats["requests"] += len(validated)
        stats["cache_hits"] += hits
        stats["unique_pairs_scored"] = len(self._cache)
        return [self._cache[pair] for pair in validated]

    def pair_diagnostics(self, pairs: Sequence[TextPair]) -> list[dict[str, Any]]:
        """Expose diagnostics from the scorer that actually tokenized the pairs."""

        validated = _validate_pairs(pairs)
        diagnostics = getattr(self._scorer, "pair_diagnostics", None)
        if not callable(diagnostics):
            return [
                {
                    "available": False,
                    "truncated": None,
                    "reason": "scorer_does_not_expose_tokenization_diagnostics",
                }
                for _pair in validated
            ]
        values = diagnostics(validated)
        if not isinstance(values, list) or len(values) != len(validated):
            raise ValueError(
                "Cross-Encoder tokenization diagnostics must align with scored pairs"
            )
        return [deepcopy(value) for value in values]

    def set_deadline(self, deadline_monotonic: float | None) -> None:
        """Forward an optional cooperative deadline to the underlying scorer."""

        setter = getattr(self._scorer, "set_deadline", None)
        if callable(setter):
            setter(deadline_monotonic)
        self.metadata["cooperative_deadline_enabled"] = (
            deadline_monotonic is not None
        )

    @property
    def tokenizer(self) -> Any:
        """Expose the underlying tokenizer for explicit input-policy wrappers."""
        return getattr(self._scorer, "tokenizer", None)


def pair_diagnostics(
    pairs: Sequence[TextPair],
    *,
    scorer: PairScorer,
) -> list[dict[str, Any]]:
    """Return aligned model-input diagnostics, or an explicit unavailable marker."""

    validated = _validate_pairs(pairs)
    diagnostics = getattr(scorer, "pair_diagnostics", None)
    if not callable(diagnostics):
        return [
            {
                "available": False,
                "truncated": None,
                "reason": "scorer_does_not_expose_tokenization_diagnostics",
            }
            for _pair in validated
        ]
    values = diagnostics(validated)
    if not isinstance(values, list) or len(values) != len(validated):
        raise ValueError(
            "Cross-Encoder tokenization diagnostics must align with scored pairs"
        )
    if any(not isinstance(value, dict) for value in values):
        raise ValueError("Cross-Encoder tokenization diagnostics must be objects")
    return [deepcopy(value) for value in values]


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
        score_output: str = "raw_logit",
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
        if score_output != "raw_logit":
            raise ValueError("Cross-Encoder score_output must be raw_logit")

        model_reference, resolved_revision = locked_model_revision(model, revision)
        is_local = Path(model_reference).is_dir()
        try:
            from sentence_transformers import CrossEncoder
            from torch.nn import Identity
        except ImportError as exc:  # pragma: no cover - optional environment.
            raise RuntimeError(
                "Cross-Encoder reranking requires the optional research "
                "environment; install research/requirements-research.txt"
            ) from exc

        self._activation_fn = Identity()
        model_kwargs: dict[str, Any] = {
            "device": device,
            "local_files_only": True,
            "activation_fn": self._activation_fn,
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
        effective_max_length = getattr(self._model, "max_seq_length", None)
        if (
            isinstance(effective_max_length, bool)
            or not isinstance(effective_max_length, int)
            or effective_max_length <= 0
        ):
            effective_max_length = max_length
        self._max_length = effective_max_length
        self._pair_diagnostics: dict[TextPair, dict[str, Any]] = {}
        self._deadline_monotonic: float | None = None
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
            "score_output": "raw_logit",
            "activation": "torch.nn.Identity",
            "apply_softmax": False,
            "cooperative_deadline_enabled": False,
            "tokenization": {
                "available": callable(getattr(self._model, "tokenizer", None)),
                "truncation_strategy": "longest_first",
                "max_length": effective_max_length,
                "unique_pairs_inspected": 0,
                "pairs_truncated": 0,
                "max_tokens_before_truncation": None,
                "max_tokens_model_input": None,
            },
        }

    @property
    def tokenizer(self) -> Any:
        """Return the exact tokenizer used to score pairs, without reloading it."""
        return getattr(self._model, "tokenizer", None)

    def set_deadline(self, deadline_monotonic: float | None) -> None:
        """Set a monotonic deadline checked around every inference batch."""

        if deadline_monotonic is not None and (
            isinstance(deadline_monotonic, bool)
            or not isinstance(deadline_monotonic, (int, float))
            or not math.isfinite(float(deadline_monotonic))
        ):
            raise ValueError("Cross-Encoder deadline must be a finite number")
        self._deadline_monotonic = (
            None if deadline_monotonic is None else float(deadline_monotonic)
        )
        self.metadata["cooperative_deadline_enabled"] = (
            self._deadline_monotonic is not None
        )

    def _check_deadline(self) -> None:
        if (
            self._deadline_monotonic is not None
            and time.perf_counter() >= self._deadline_monotonic
        ):
            raise TimeoutError(
                "Cross-Encoder cooperative stage timeout exceeded between batches"
            )

    def _inspect_pair(self, pair: TextPair) -> dict[str, Any]:
        cached = self._pair_diagnostics.get(pair)
        if cached is not None:
            return cached

        tokenizer = getattr(self._model, "tokenizer", None)
        if not callable(tokenizer):
            diagnostic = {
                "available": False,
                "truncated": None,
                "reason": "cross_encoder_tokenizer_unavailable",
            }
        else:
            query, passage = pair
            common_kwargs = {
                "add_special_tokens": True,
                "padding": False,
                "return_attention_mask": False,
                "return_token_type_ids": False,
            }
            full = tokenizer(
                query,
                passage,
                truncation=False,
                **common_kwargs,
            )
            model_input = tokenizer(
                query,
                passage,
                truncation="longest_first",
                max_length=self._max_length,
                **common_kwargs,
            )
            full_count = len(full["input_ids"])
            model_count = len(model_input["input_ids"])
            diagnostic = {
                "available": True,
                "truncated": model_count < full_count,
                "tokens_before_truncation": full_count,
                "tokens_model_input": model_count,
                "max_length": self._max_length,
                "truncation_strategy": "longest_first",
                "source_span_scope": (
                    "candidate_passage_before_model_tokenization"
                ),
            }
        self._pair_diagnostics[pair] = diagnostic
        self._record_tokenization_diagnostic(diagnostic)
        return diagnostic

    def _record_tokenization_diagnostic(self, diagnostic: dict[str, Any]) -> None:
        """Update aggregate counters once, without rescanning every prior pair."""

        metadata = self.metadata["tokenization"]
        metadata["unique_pairs_inspected"] += 1
        if diagnostic.get("available") is not True:
            return
        metadata["pairs_truncated"] += int(diagnostic.get("truncated") is True)
        before = int(diagnostic["tokens_before_truncation"])
        model_input = int(diagnostic["tokens_model_input"])
        previous_before = metadata["max_tokens_before_truncation"]
        previous_model = metadata["max_tokens_model_input"]
        metadata["max_tokens_before_truncation"] = (
            before if previous_before is None else max(int(previous_before), before)
        )
        metadata["max_tokens_model_input"] = (
            model_input
            if previous_model is None
            else max(int(previous_model), model_input)
        )

    def pair_diagnostics(self, pairs: Sequence[TextPair]) -> list[dict[str, Any]]:
        """Describe the exact token-length/truncation treatment of each pair."""

        return [deepcopy(self._inspect_pair(pair)) for pair in _validate_pairs(pairs)]

    def score_pairs(self, pairs: Sequence[TextPair]) -> list[float]:
        validated = _validate_pairs(pairs)
        self._check_deadline()
        self.pair_diagnostics(validated)
        self._check_deadline()
        scores: list[float] = []
        for start in range(0, len(validated), self._batch_size):
            self._check_deadline()
            batch = validated[start : start + self._batch_size]
            predicted = self._model.predict(
                batch,
                batch_size=self._batch_size,
                show_progress_bar=False,
                activation_fn=self._activation_fn,
                apply_softmax=False,
                convert_to_numpy=True,
            )
            scores.extend(_normalise_scores(predicted, expected=len(batch)))
            self._check_deadline()
        return scores


# More explicit alias for call sites that name the role rather than the model.
SentenceTransformersCrossEncoderScorer = SentenceTransformersCrossEncoder
