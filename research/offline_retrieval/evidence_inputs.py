"""Inference-only, token-bounded Cross-Encoder input windows.

This policy changes visible text within a fixed query/support-passage pair.
It has no access to retrieval labels or gold spans and never selects another
source document or support passage. Character ranges are relative to the
original pair strings, not automatically raw-document coordinates.
"""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import math
import re
import time
from typing import Any, Sequence

from .cross_encoder import PairScorer, TextPair, _validate_pairs, pair_diagnostics, score_pairs


INPUT_POLICY = "lexical_window_v1"
_WORD = re.compile(r"\b\w+\b", re.UNICODE)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _positive_integer(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


@dataclass(frozen=True)
class _PreparedPair:
    pair: TextPair
    evidence_window: dict[str, Any]


class EvidenceWindowPairScorer:
    """Score one shorter pair per existing support through the same model.

    Queries use a deterministic prefix. A contiguous passage token window is
    chosen by distinct whole-query-term coverage, with earliest-position ties.
    The actual fast tokenizer verifies the resulting leg and pair budgets.
    Unsupported offsets or a budget mismatch fail instead of silently using
    a different input policy.
    """

    def __init__(
        self,
        base: PairScorer,
        *,
        tokenizer: Any,
        max_length: int = 512,
        query_token_budget: int = 192,
        passage_token_budget: int = 256,
    ) -> None:
        self._max_length = _positive_integer(max_length, "max_length")
        self._query_budget = _positive_integer(query_token_budget, "query_token_budget")
        self._passage_budget = _positive_integer(passage_token_budget, "passage_token_budget")
        if not callable(tokenizer) or getattr(tokenizer, "is_fast", False) is not True:
            raise ValueError("Evidence input windows require a fast tokenizer with character offsets")
        self._base = base
        self._tokenizer = tokenizer
        self._prepared: dict[TextPair, _PreparedPair] = {}
        self._deadline: float | None = None
        self.metadata = deepcopy(base.metadata)
        self.metadata["input_policy"] = {
            "strategy": INPUT_POLICY,
            "query_selection": "prefix",
            "passage_selection": "maximum_distinct_visible_query_terms_earliest_tie",
            "max_length": self._max_length,
            "query_token_budget": self._query_budget,
            "passage_token_budget": self._passage_budget,
            "offset_unit": "python_unicode_character_half_open",
            "budget_repair": "shrink_end_to_previous_original_token_boundary",
            "gold_used": False,
        }
        self.metadata["input_preparation"] = {
            "unique_original_pairs": 0,
            "query_cropped_pairs": 0,
            "passage_cropped_pairs": 0,
            "query_budget_repaired_pairs": 0,
            "passage_budget_repaired_pairs": 0,
            "max_original_pair_tokens": None,
            "max_prepared_pair_tokens": None,
        }

    @property
    def tokenizer(self) -> Any:
        return self._tokenizer

    def set_deadline(self, deadline_monotonic: float | None) -> None:
        if deadline_monotonic is not None and (
            isinstance(deadline_monotonic, bool)
            or not isinstance(deadline_monotonic, (int, float))
            or not math.isfinite(float(deadline_monotonic))
        ):
            raise ValueError("Evidence input deadline must be a finite number")
        self._deadline = None if deadline_monotonic is None else float(deadline_monotonic)
        setter = getattr(self._base, "set_deadline", None)
        if callable(setter):
            setter(deadline_monotonic)
        self.metadata["cooperative_deadline_enabled"] = deadline_monotonic is not None

    def _check_deadline(self) -> None:
        if self._deadline is not None and time.perf_counter() >= self._deadline:
            raise TimeoutError("Evidence input preparation deadline exceeded")

    def _tokens(self, text: str) -> tuple[list[int], list[tuple[int, int]]]:
        encoded = self._tokenizer(
            text,
            add_special_tokens=False,
            truncation=False,
            padding=False,
            return_offsets_mapping=True,
            return_attention_mask=False,
            return_token_type_ids=False,
        )
        ids = encoded.get("input_ids")
        offsets = encoded.get("offset_mapping")
        if not isinstance(ids, list) or not isinstance(offsets, list) or len(ids) != len(offsets):
            raise ValueError("Evidence input tokenizer did not return aligned token offsets")
        checked: list[tuple[int, int]] = []
        previous_start = previous_end = 0
        for identifier, offset in zip(ids, offsets, strict=True):
            if isinstance(identifier, bool) or not isinstance(identifier, int) or identifier < 0:
                raise ValueError("Evidence input tokenizer returned invalid token identifiers")
            if not isinstance(offset, (tuple, list)) or len(offset) != 2:
                raise ValueError("Evidence input tokenizer returned invalid character offsets")
            start, end = offset
            if (
                isinstance(start, bool) or isinstance(end, bool)
                or not isinstance(start, int) or not isinstance(end, int)
                or not 0 <= start < end <= len(text)
                or start < previous_start or end < previous_end
            ):
                raise ValueError("Evidence input tokenizer returned out-of-range or unordered offsets")
            checked.append((start, end))
            previous_start, previous_end = start, end
        if text.strip() and not ids:
            raise ValueError("Evidence input tokenizer discarded nonempty text")
        return ids, checked

    def _pair_token_count(self, pair: TextPair) -> int:
        encoded = self._tokenizer(
            pair[0], pair[1], add_special_tokens=True,
            truncation=False, padding=False,
            return_attention_mask=False, return_token_type_ids=False,
        )
        identifiers = encoded.get("input_ids")
        if not isinstance(identifiers, list) or any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in identifiers
        ):
            raise ValueError("Evidence input tokenizer returned invalid paired tokens")
        return len(identifiers)

    def _passage_range(
        self, passage: str, offsets: list[tuple[int, int]], query_terms: set[str],
    ) -> tuple[int, int, int]:
        if len(offsets) <= self._passage_budget:
            terms = {match.group().casefold() for match in _WORD.finditer(passage)}
            return 0, len(passage), len(terms & query_terms)
        # Whole-word matches come from the complete passage; a word fragment
        # exposed by a token window cannot count as a matching query word.
        matches = [
            (match.start(), match.end(), match.group().casefold())
            for match in _WORD.finditer(passage)
            if match.group().casefold() in query_terms
        ]
        counts: Counter[str] = Counter()
        left = right = 0
        best: tuple[int, int, int] | None = None
        for token_start in range(len(offsets) - self._passage_budget + 1):
            start = offsets[token_start][0]
            end = offsets[token_start + self._passage_budget - 1][1]
            while right < len(matches) and matches[right][1] <= end:
                counts[matches[right][2]] += 1
                right += 1
            while left < right and matches[left][0] < start:
                term = matches[left][2]
                counts[term] -= 1
                if not counts[term]:
                    del counts[term]
                left += 1
            coverage = len(counts)
            if best is None or coverage > best[2]:
                best = start, end, coverage
        assert best is not None
        return best

    def _fit_end_to_budget(
        self, text: str, start: int, end: int,
        original_offsets: list[tuple[int, int]], budget: int,
    ) -> tuple[int, int, int]:
        """Repair boundary retokenization without moving a chosen window start.

        A WordPiece continuation at the start/end of a substring can tokenize
        differently in isolation. Each repair strictly shortens the string at
        an existing original token boundary; it does not select another source
        or silently fall back to the full passage.
        """
        repair_steps = 0
        while True:
            self._check_deadline()
            token_count = len(self._tokens(text[start:end])[0])
            if token_count <= budget:
                return end, token_count, repair_steps
            previous = [boundary_end for _, boundary_end in original_offsets
                        if start < boundary_end < end]
            if not previous:
                raise ValueError("Evidence input cannot satisfy its token budget at original boundaries")
            end = max(previous)
            repair_steps += 1

    def _prepare(self, pair: TextPair) -> _PreparedPair:
        self._check_deadline()
        existing = self._prepared.get(pair)
        if existing is not None:
            return existing
        query, passage = pair
        query_ids, query_offsets = self._tokens(query)
        passage_ids, passage_offsets = self._tokens(passage)
        query_end = (
            query_offsets[self._query_budget - 1][1]
            if len(query_ids) > self._query_budget else len(query)
        )
        query_end, query_count, query_repairs = self._fit_end_to_budget(
            query, 0, query_end, query_offsets, self._query_budget,
        )
        visible_query = query[:query_end]
        query_terms = {
            match.group().casefold() for match in _WORD.finditer(visible_query)
            if len(match.group()) >= 2
        }
        passage_start, passage_end, selection_overlap = self._passage_range(passage, passage_offsets, query_terms)
        selection_end = passage_end
        passage_end, passage_count, passage_repairs = self._fit_end_to_budget(
            passage, passage_start, passage_end, passage_offsets, self._passage_budget,
        )
        visible_passage = passage[passage_start:passage_end]
        prepared = visible_query, visible_passage
        prepared_tokens = self._pair_token_count(prepared)
        if (
            query_count > self._query_budget
            or passage_count > self._passage_budget
            or prepared_tokens > self._max_length
        ):
            raise ValueError("Prepared evidence input exceeds its locked token budget")
        original_tokens = self._pair_token_count(pair)
        diagnostic = {
            "policy": INPUT_POLICY,
            "query_char_range": {"start": 0, "end": query_end},
            "passage_char_range": {"start": passage_start, "end": passage_end},
            "passage_selection_char_range": {"start": passage_start, "end": selection_end},
            "original_query_sha256": _sha(query),
            "original_passage_sha256": _sha(passage),
            "cropped_query_sha256": _sha(visible_query),
            "cropped_passage_sha256": _sha(visible_passage),
            "original_query_char_count": len(query),
            "original_passage_char_count": len(passage),
            "query_cropped": visible_query != query,
            "passage_cropped": visible_passage != passage,
            "original_query_tokens": len(query_ids),
            "original_passage_tokens": len(passage_ids),
            "prepared_query_tokens": query_count,
            "prepared_passage_tokens": passage_count,
            "original_pair_tokens": original_tokens,
            "prepared_pair_tokens": prepared_tokens,
            "selection_distinct_query_term_overlap": selection_overlap,
            "distinct_query_term_overlap": len({
                match.group().casefold() for match in _WORD.finditer(passage)
                if passage_start <= match.start() and match.end() <= passage_end
            } & query_terms),
            "query_budget_repair_steps": query_repairs,
            "passage_budget_repair_steps": passage_repairs,
            "offset_unit": "python_unicode_character_half_open",
            "gold_used": False,
        }
        result = _PreparedPair(prepared, diagnostic)
        self._prepared[pair] = result
        stats = self.metadata["input_preparation"]
        stats["unique_original_pairs"] += 1
        stats["query_cropped_pairs"] += int(diagnostic["query_cropped"])
        stats["passage_cropped_pairs"] += int(diagnostic["passage_cropped"])
        stats["query_budget_repaired_pairs"] += int(query_repairs > 0)
        stats["passage_budget_repaired_pairs"] += int(passage_repairs > 0)
        stats["max_original_pair_tokens"] = max(stats["max_original_pair_tokens"] or 0, original_tokens)
        stats["max_prepared_pair_tokens"] = max(stats["max_prepared_pair_tokens"] or 0, prepared_tokens)
        self._check_deadline()
        return result

    def score_pairs(self, pairs: Sequence[TextPair]) -> list[float]:
        originals = _validate_pairs(pairs)
        prepared = [self._prepare(pair).pair for pair in originals]
        values = score_pairs(prepared, scorer=self._base)
        if "tokenization" in self._base.metadata:
            self.metadata["tokenization"] = deepcopy(self._base.metadata["tokenization"])
        return values

    def pair_diagnostics(self, pairs: Sequence[TextPair]) -> list[dict[str, Any]]:
        originals = _validate_pairs(pairs)
        prepared = [self._prepare(pair) for pair in originals]
        actual = pair_diagnostics([item.pair for item in prepared], scorer=self._base)
        output = []
        for item, diagnostic in zip(prepared, actual, strict=True):
            if diagnostic.get("available") is True and (
                diagnostic.get("truncated") is True
                or diagnostic.get("tokens_before_truncation") != item.evidence_window["prepared_pair_tokens"]
            ):
                raise ValueError("Evidence input diagnostics disagree with actual Cross-Encoder tokenization")
            output.append({
                **deepcopy(diagnostic),
                "evidence_window": deepcopy(item.evidence_window),
                "source_span_scope": "CROPPED_PAIR_OFFSETS_ONLY",
            })
        return output
