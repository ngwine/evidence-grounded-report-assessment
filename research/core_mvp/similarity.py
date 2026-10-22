"""Executable baseline for Pipeline 1: retrieval to similarity report."""

from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from difflib import SequenceMatcher
import math
import unicodedata
from typing import Any, Mapping, Sequence

from research.offline_retrieval.bm25 import rank_bm25
from research.offline_retrieval.common import token_spans, tokenize
from research.offline_retrieval.cross_encoder import PairScorer, pair_diagnostics, score_pairs
from research.offline_retrieval.dense import Encoder, rank_dense
from research.offline_retrieval.rrf import fuse_rrf


SIMILARITY_TYPES = {"VERBATIM", "PARAPHRASE", "SUMMARY", "NONE"}
CLASSIFICATION_POLICY = "EXACT_EVIDENCE_OR_UNVERIFIED_RETRIEVAL_V1"
# An exact alignment can be shown with fewer characters, but automatic
# document coverage needs a substantial run of complete, varied words.
_VERBATIM_MIN_EXACT_CHARS = 60
_VERBATIM_MIN_EXACT_TOKENS = 8
_VERBATIM_MIN_DISTINCT_TOKENS = 6
_VERBATIM_MIN_LONG_DISTINCT_TOKENS = 2


def _require_positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field} must be a positive integer")
    return value


def _probability(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be numeric")
    number = float(value)
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        raise ValueError(f"{field} must be in [0, 1]")
    return number


def _finite_number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field} must be finite")
    return number


def validate_similarity_config(config: Mapping[str, Any]) -> dict[str, Any]:
    candidate_depth = _require_positive_int(
        config.get("candidate_depth", 30), "pipeline1.candidate_depth"
    )
    rerank_depth = _require_positive_int(
        config.get("rerank_depth", 10), "pipeline1.rerank_depth"
    )
    top_k = _require_positive_int(config.get("top_k", 5), "pipeline1.top_k")
    if rerank_depth > candidate_depth:
        raise ValueError("pipeline1.rerank_depth must be <= candidate_depth")
    if top_k > candidate_depth:
        raise ValueError("pipeline1.top_k must be <= candidate_depth")
    reranker_enabled = bool(config.get("reranker_enabled", True))
    if reranker_enabled and top_k > rerank_depth:
        raise ValueError(
            "pipeline1.top_k must be <= rerank_depth when reranking is enabled"
        )
    dense_enabled = bool(config.get("dense_enabled", True))
    candidate_selection = config.get("candidate_selection", "rrf")
    if (
        not isinstance(candidate_selection, str)
        or candidate_selection not in {"rrf", "quota_union"}
    ):
        raise ValueError("pipeline1.candidate_selection must be rrf or quota_union")
    raw_quotas = config.get("candidate_quotas")
    if candidate_selection == "quota_union":
        if not dense_enabled or not reranker_enabled:
            raise ValueError(
                "pipeline1.quota_union requires Dense retrieval and reranking"
            )
        if (
            not isinstance(raw_quotas, Mapping)
            or set(raw_quotas) != {"bm25", "dense"}
        ):
            raise ValueError(
                "pipeline1.candidate_quotas must specify bm25 and dense"
            )
        quotas = {
            method: _require_positive_int(
                raw_quotas[method], f"pipeline1.candidate_quotas.{method}"
            )
            for method in ("bm25", "dense")
        }
        if sum(quotas.values()) > rerank_depth:
            raise ValueError(
                "pipeline1.candidate_quotas must fit within rerank_depth"
            )
    else:
        if raw_quotas is not None:
            raise ValueError(
                "pipeline1.candidate_quotas requires candidate_selection=quota_union"
            )
        quotas = None
    raw_evidence_budget = config.get("evidence_budget_per_source")
    evidence_budget = (
        None
        if raw_evidence_budget is None
        else _require_positive_int(
            raw_evidence_budget, "pipeline1.evidence_budget_per_source"
        )
    )
    thresholds = config.get("classification", {})
    if not isinstance(thresholds, Mapping):
        raise ValueError("pipeline1.classification must be an object")
    return {
        "candidate_depth": candidate_depth,
        "rerank_depth": rerank_depth,
        "top_k": top_k,
        "bm25_k1": float(config.get("bm25_k1", 1.2)),
        "bm25_b": float(config.get("bm25_b", 0.75)),
        "rrf_k": _require_positive_int(config.get("rrf_k", 60), "pipeline1.rrf_k"),
        "dense_enabled": dense_enabled,
        "reranker_enabled": reranker_enabled,
        "candidate_selection": candidate_selection,
        "candidate_quotas": quotas,
        "evidence_budget_per_source": evidence_budget,
        "classification": {
            "verbatim_query_coverage": _probability(
                thresholds.get("verbatim_query_coverage", 0.72),
                "pipeline1.classification.verbatim_query_coverage",
            ),
            "verbatim_exact_char_ratio": _probability(
                thresholds.get("verbatim_exact_char_ratio", 0.45),
                "pipeline1.classification.verbatim_exact_char_ratio",
            ),
            "semantic_similarity": _probability(
                thresholds.get("semantic_similarity", 0.72),
                "pipeline1.classification.semantic_similarity",
            ),
            "semantic_min_lexical": _probability(
                thresholds.get("semantic_min_lexical", 0.05),
                "pipeline1.classification.semantic_min_lexical",
            ),
            "cross_encoder_min_score": _finite_number(
                thresholds.get("cross_encoder_min_score", 0.0),
                "pipeline1.classification.cross_encoder_min_score",
            ),
            "lexical_paraphrase_coverage": _probability(
                thresholds.get("lexical_paraphrase_coverage", 0.32),
                "pipeline1.classification.lexical_paraphrase_coverage",
            ),
            "summary_length_ratio": _probability(
                # Accepted for old configs, but never used to infer a summary.
                thresholds.get("summary_length_ratio", 0.65),
                "pipeline1.classification.summary_length_ratio",
            ),
            "minimum_alignment_chars": _require_positive_int(
                thresholds.get("minimum_alignment_chars", 24),
                "pipeline1.classification.minimum_alignment_chars",
            ),
        },
    }


def _select_candidate_pool(
    rankings: Mapping[str, list[dict[str, Any]]],
    methods: Mapping[str, Mapping[str, list[dict[str, Any]]]],
    *,
    candidate_depth: int,
    rerank_depth: int,
    candidate_selection: str,
    candidate_quotas: Mapping[str, int] | None,
    evidence_budget_per_source: int | None,
) -> dict[str, list[dict[str, Any]]]:
    """Reserve lexical/semantic evidence before filling by global RRF rank.

    The optional source budget limits *candidate passages per query*, not the
    number of report chunks or the final similarity percentage. A source can
    therefore contribute several distinct passages without monopolising the
    Cross-Encoder input. Quota overlaps count for both methods; all ties use
    the existing RRF order (score, then chunk ID).
    """

    output: dict[str, list[dict[str, Any]]] = {}
    for query_id in sorted(rankings):
        fused = rankings[query_id]
        by_id = {str(candidate["chunk_id"]): candidate for candidate in fused}
        selected: list[str] = []
        selected_set: set[str] = set()
        source_counts: Counter[str] = Counter()
        quota_methods: dict[str, set[str]] = defaultdict(set)

        def add(candidate_id: str) -> bool:
            if candidate_id in selected_set:
                return True
            candidate = by_id.get(candidate_id)
            if candidate is None:
                return False
            source_id = str(candidate["document_id"])
            if (
                evidence_budget_per_source is not None
                and source_counts[source_id] >= evidence_budget_per_source
            ):
                return False
            selected.append(candidate_id)
            selected_set.add(candidate_id)
            source_counts[source_id] += 1
            return True

        if candidate_selection == "quota_union":
            assert candidate_quotas is not None
            for method in ("bm25", "dense"):
                satisfied = 0
                for candidate in methods[method].get(query_id, []):
                    candidate_id = str(candidate["chunk_id"])
                    if add(candidate_id):
                        quota_methods[candidate_id].add(method)
                        satisfied += 1
                    if satisfied >= candidate_quotas[method]:
                        break
            # Quota reservation changes membership, not the RRF ordering of
            # the reserved passages within the reranker head.
            selected.sort(key=lambda candidate_id: int(by_id[candidate_id]["rank"]))

        for candidate in fused:
            if len(selected) >= rerank_depth:
                break
            add(str(candidate["chunk_id"]))
        for candidate in fused:
            if len(selected) >= candidate_depth:
                break
            add(str(candidate["chunk_id"]))

        chosen: list[dict[str, Any]] = []
        for rank, candidate_id in enumerate(selected, 1):
            record = deepcopy(by_id[candidate_id])
            record["global_preselection_rank"] = int(record["rank"])
            if record.get("score_type") == "rrf":
                record["global_rrf_rank"] = record["global_preselection_rank"]
            record["rank"] = rank
            record["candidate_selection_reasons"] = (
                [f"{method}_quota" for method in sorted(quota_methods[candidate_id])]
                if quota_methods[candidate_id]
                else ["rrf_fill"]
            )
            chosen.append(record)
        output[query_id] = chosen
    return output


def _normalise_for_character_match(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def _character_ngrams(text: str, size: int = 5) -> set[str]:
    compact = _normalise_for_character_match(text)
    if len(compact) < size:
        return {compact} if compact else set()
    return {compact[index : index + size] for index in range(len(compact) - size + 1)}


def _similarity_features(query_text: str, source_text: str) -> dict[str, Any]:
    query_tokens = tokenize(query_text)
    source_tokens = tokenize(source_text)
    query_counts = Counter(query_tokens)
    source_counts = Counter(source_tokens)
    shared = query_counts & source_counts
    shared_count = sum(shared.values())
    query_coverage = shared_count / len(query_tokens) if query_tokens else 0.0
    source_coverage = shared_count / len(source_tokens) if source_tokens else 0.0
    query_set = set(query_tokens)
    source_set = set(source_tokens)
    union = query_set | source_set
    token_jaccard = len(query_set & source_set) / len(union) if union else 0.0
    query_ngrams = _character_ngrams(query_text)
    source_ngrams = _character_ngrams(source_text)
    ngram_union = query_ngrams | source_ngrams
    char_ngram_jaccard = (
        len(query_ngrams & source_ngrams) / len(ngram_union)
        if ngram_union
        else 0.0
    )
    query_normalised = _normalise_for_character_match(query_text)
    source_normalised = _normalise_for_character_match(source_text)
    longest = SequenceMatcher(
        None,
        query_normalised,
        source_normalised,
        autojunk=False,
    ).find_longest_match()
    exact_query_ratio = (
        longest.size / len(query_normalised) if query_normalised else 0.0
    )
    return {
        "query_token_count": len(query_tokens),
        "source_token_count": len(source_tokens),
        "shared_token_count": shared_count,
        "query_token_coverage": query_coverage,
        "source_token_coverage": source_coverage,
        "token_jaccard": token_jaccard,
        "char_5gram_jaccard": char_ngram_jaccard,
        "longest_exact_match_chars": longest.size,
        "longest_exact_query_ratio": exact_query_ratio,
        "length_ratio_query_to_source": (
            len(query_tokens) / len(source_tokens) if source_tokens else 0.0
        ),
    }


def _dense_support_score(candidate: Mapping[str, Any]) -> float | None:
    supports = candidate.get("supports_by_method")
    if not isinstance(supports, Mapping):
        return None
    dense = supports.get("dense")
    if not isinstance(dense, Mapping):
        return None
    value = dense.get("score")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _classify(
    features: Mapping[str, Any],
    *,
    alignment: Mapping[str, Any],
    evidence_backed_exact_span: bool,
    dense_score: float | None,
    cross_encoder_score: float | None,
    thresholds: Mapping[str, Any],
) -> tuple[str | None, float, list[str]]:
    """Identify exact overlap or retrieval candidates, never infer semantic reuse.

    A null label means the relation was not assessed, not a negative label.
    Retrieval relevance and relative passage length cannot distinguish shared
    subject matter from paraphrasing or summarization.
    """

    query_coverage = float(features["query_token_coverage"])
    exact_ratio = float(features["longest_exact_query_ratio"])
    lexical_signal = max(
        query_coverage,
        float(features["token_jaccard"]),
        float(features["char_5gram_jaccard"]),
    )
    reasons: list[str] = []
    if evidence_backed_exact_span:
        exact_chars = int(alignment["exact_match_chars"])
        exact_tokens = int(alignment["exact_match_token_count"])
        # This is only a ranking heuristic, not a calibrated probability.
        span_score = (
            exact_chars / (exact_chars + _VERBATIM_MIN_EXACT_CHARS)
            + exact_tokens / (exact_tokens + _VERBATIM_MIN_EXACT_TOKENS)
        ) / 2
        return (
            "VERBATIM",
            span_score,
            ["substantial_exact_substring", "distinct_complete_word_run"],
        )
    if (
        query_coverage >= thresholds["verbatim_query_coverage"]
        and exact_ratio >= thresholds["verbatim_exact_char_ratio"]
    ):
        reasons.extend(["high_query_token_coverage", "long_exact_character_run"])
        reasons.append("exact_span_below_automatic_evidence_floor")
        return "VERBATIM", min(1.0, (query_coverage + exact_ratio) / 2), reasons

    reranker_pass = (
        cross_encoder_score is None
        or cross_encoder_score >= thresholds["cross_encoder_min_score"]
    )
    semantic_pass = (
        dense_score is not None
        and dense_score >= thresholds["semantic_similarity"]
        and lexical_signal >= thresholds["semantic_min_lexical"]
        and reranker_pass
    )
    if semantic_pass:
        reasons.extend(
            [
                "dense_similarity_above_threshold",
                "nonzero_lexical_anchor",
                "cross_encoder_above_conservative_gate",
            ]
        )
        cross_encoder_signal = (
            0.5
            if cross_encoder_score is None
            else 1.0 / (1.0 + math.exp(-cross_encoder_score))
        )
        heuristic_score = min(
            1.0,
            (dense_score + lexical_signal + cross_encoder_signal) / 3,
        )
        reasons.append("semantic_relation_not_verified")
        return None, heuristic_score, reasons

    if (
        query_coverage >= thresholds["lexical_paraphrase_coverage"]
        and reranker_pass
    ):
        reasons.extend(
            ["moderate_lexical_coverage", "cross_encoder_above_conservative_gate",
             "semantic_relation_not_verified"]
        )
        return None, query_coverage, reasons
    if not reranker_pass:
        reasons.append("cross_encoder_below_conservative_gate")
    reasons.append("insufficient_similarity_signal")
    return "NONE", max(0.0, lexical_signal), reasons


def _resolve_normalized_range(
    chunk: Mapping[str, Any],
    start: int,
    end: int,
) -> dict[str, Any]:
    text = str(chunk.get("normalized_text", chunk.get("text", "")))
    if not 0 <= start < end <= len(text):
        raise ValueError("Alignment range is outside chunk normalized text")
    mapping = chunk.get("normalization_map")
    char_map = (
        mapping.get("normalized_char_to_raw_span")
        if isinstance(mapping, Mapping)
        else None
    )
    if not isinstance(char_map, Sequence) or len(char_map) != len(text):
        raw_start, raw_end = start, end
    else:
        raw_start = min(int(char_map[index][0]) for index in range(start, end))
        raw_end = max(int(char_map[index][1]) for index in range(start, end))

    locators: list[dict[str, Any]] = []
    for source_span in chunk.get("source_spans", []):
        span_start = int(source_span.get("chunk_normalized_char_start", 0))
        span_end = int(source_span.get("chunk_normalized_char_end", len(text)))
        overlap_start = max(start, span_start)
        overlap_end = min(end, span_end)
        if overlap_start >= overlap_end:
            continue
        record = deepcopy(source_span)
        record["matched_chunk_normalized_start"] = overlap_start
        record["matched_chunk_normalized_end"] = overlap_end
        if isinstance(char_map, Sequence) and len(char_map) == len(text):
            matched_raw_start = min(
                int(char_map[index][0])
                for index in range(overlap_start, overlap_end)
            )
            matched_raw_end = max(
                int(char_map[index][1])
                for index in range(overlap_start, overlap_end)
            )
            record["matched_chunk_raw_start"] = matched_raw_start
            record["matched_chunk_raw_end"] = matched_raw_end
            chunk_raw_start = int(source_span.get("chunk_raw_char_start", 0))
            element_raw_start = int(source_span.get("element_raw_char_start", 0))
            record["matched_element_raw_start"] = element_raw_start + max(
                0, matched_raw_start - chunk_raw_start
            )
            record["matched_element_raw_end"] = element_raw_start + max(
                0, matched_raw_end - chunk_raw_start
            )
        locators.append(record)
    return {
        "chunk_id": chunk["chunk_id"],
        "document_id": chunk["document_id"],
        "normalized_start": start,
        "normalized_end": end,
        "raw_start": raw_start,
        "raw_end": raw_end,
        "text": text[start:end],
        "source_spans": locators,
    }


def _document_token_keys(chunk: Mapping[str, Any]) -> list[tuple[int, int, tuple[Any, ...]]]:
    """Map tokens to immutable element coordinates, deduplicating chunk overlap."""
    text = str(chunk.get("normalized_text", chunk.get("text", "")))
    result = []
    for left, right in token_spans(text):
        key: tuple[Any, ...] | None = None
        for span in chunk.get("source_spans", []):
            start, end = span.get("chunk_normalized_char_start"), span.get("chunk_normalized_char_end")
            element_start = span.get("element_normalized_char_start")
            version = span.get("document_version_id", chunk.get("document_version_id"))
            if (all(isinstance(value, int) and not isinstance(value, bool)
                    for value in (start, end, element_start))
                    and start <= left < right <= end
                    and version and span.get("element_key")):
                key = ("element", str(version), str(span["element_key"]),
                       element_start + left - start, element_start + right - start)
                break
        if key is None:
            # Older test/research inputs lack authoritative element coordinates.
            # Keep the old chunk-local interpretation and disclose the fallback.
            key = ("chunk", str(chunk["chunk_id"]), left, right)
        result.append((left, right, key))
    return result


def _alignment(
    query: Mapping[str, Any],
    source: Mapping[str, Any],
    *,
    minimum_chars: int,
) -> dict[str, Any]:
    query_text = str(query.get("normalized_text", query.get("text", "")))
    source_text = str(source.get("normalized_text", source.get("text", "")))
    # Use the exact normalised strings so SequenceMatcher offsets remain valid
    # for provenance.  Unicode case-folding can change string length for some
    # scripts and would make returned offsets unsafe.
    block = SequenceMatcher(
        None,
        query_text,
        source_text,
        autojunk=False,
    ).find_longest_match()
    matched_tokens: list[str] = []
    if block.size >= minimum_chars:
        query_start, query_end = block.a, block.a + block.size
        source_start, source_end = block.b, block.b + block.size
        kind = "EXACT_SUBSTRING"
        # The character matcher can start in the middle of a word. Keep only
        # tokens that are complete words on both sides of the alignment.
        query_token_spans = token_spans(query_text)
        source_token_spans = set(token_spans(source_text))
        complete_query_spans = [
            (left, right)
            for left, right in query_token_spans
            if query_start <= left
            and right <= query_end
            and (
                source_start + left - query_start,
                source_start + right - query_start,
            )
            in source_token_spans
        ]
        if complete_query_spans:
            start_cuts_word = any(
                left < query_start < right for left, right in query_token_spans
            ) or any(left < source_start < right for left, right in source_token_spans)
            end_cuts_word = any(
                left < query_end < right for left, right in query_token_spans
            ) or any(left < source_end < right for left, right in source_token_spans)
            trimmed_start = (
                complete_query_spans[0][0] if start_cuts_word else query_start
            )
            trimmed_end = complete_query_spans[-1][1] if end_cuts_word else query_end
            if trimmed_end - trimmed_start >= minimum_chars:
                source_start += trimmed_start - query_start
                source_end -= query_end - trimmed_end
                query_start, query_end = trimmed_start, trimmed_end
            matched_tokens = [
                unicodedata.normalize("NFKC", query_text[left:right]).casefold()
                for left, right in complete_query_spans
                if query_start <= left and right <= query_end
            ]
    else:
        query_start, query_end = 0, len(query_text)
        source_start, source_end = 0, len(source_text)
        kind = "PASSAGE_LEVEL"
    distinct_tokens = set(matched_tokens)
    return {
        "kind": kind,
        "exact_match_chars": query_end - query_start if kind == "EXACT_SUBSTRING" else block.size,
        "exact_match_token_count": len(matched_tokens),
        "exact_match_distinct_token_count": len(distinct_tokens),
        "exact_match_long_distinct_token_count": sum(
            len(token) >= 5 for token in distinct_tokens
        ),
        "report": _resolve_normalized_range(query, query_start, query_end),
        "source": _resolve_normalized_range(source, source_start, source_end),
    }


def _is_evidence_backed_exact_span(
    alignment: Mapping[str, Any], *, minimum_alignment_chars: int
) -> bool:
    return (
        alignment["kind"] == "EXACT_SUBSTRING"
        and int(alignment["exact_match_chars"])
        >= max(minimum_alignment_chars, _VERBATIM_MIN_EXACT_CHARS)
        and int(alignment["exact_match_token_count"]) >= _VERBATIM_MIN_EXACT_TOKENS
        and int(alignment["exact_match_distinct_token_count"])
        >= _VERBATIM_MIN_DISTINCT_TOKENS
        and int(alignment["exact_match_long_distinct_token_count"])
        >= _VERBATIM_MIN_LONG_DISTINCT_TOKENS
    )


def _evidence_status(label: str | None, *, evidence_backed_exact_span: bool) -> str:
    """Keep retrieval relevance separate from evidence-backed similarity.

    Dense and Cross-Encoder scores establish topical relevance, not that a
    passage was reused.  Until the semantic classifier has labelled
    validation, only the conservative verbatim path may contribute to
    document coverage; unverified candidates stay visible for review with no
    inferred PARAPHRASE/SUMMARY label.
    """

    if label == "NONE":
        return "NO_SIMILARITY_HYPOTHESIS"
    if label == "VERBATIM" and evidence_backed_exact_span:
        return "EVIDENCE_BACKED_EXACT_MATCH"
    return "PROVISIONAL_REVIEW_REQUIRED"


def _group_review_candidates(matches: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group the review queue without deleting pairs or modifying exact matches.

    Repeated source retrieval is a diagnostic, not a reason to suppress valid
    reuse or a substitute for verifying each report/source pair.
    """
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for match in matches:
        if match["selected_for_manual_review"]:
            grouped[(str(match["source_document_id"]), str(match["source_chunk_id"]))].append(match)
    groups = []
    for (document_id, chunk_id), values in sorted(grouped.items()):
        group_id = "review-source-" + chunk_id
        report_ids = sorted({str(value["report_chunk_id"]) for value in values})
        for value in values:
            value["review_group_id"] = group_id
        groups.append({
            "group_id": group_id,
            "source_document_id": document_id,
            "source_chunk_id": chunk_id,
            "source_name": values[0]["source_name"],
            "report_chunk_ids": report_ids,
            "report_chunk_count": len(report_ids),
            "classification_status": "PROVISIONAL_REVIEW_REQUIRED",
            "warning": (
                "REPEATED_SOURCE_CHUNK_NOT_INDEPENDENT_EVIDENCE"
                if len(report_ids) > 1 else None
            ),
        })
    return sorted(groups, key=lambda group: (-group["report_chunk_count"], group["group_id"]))


def _rerank_chunks(
    rankings: Mapping[str, list[dict[str, Any]]],
    queries: Sequence[dict[str, Any]],
    source_map: Mapping[str, dict[str, Any]],
    *,
    scorer: PairScorer,
    rerank_depth: int,
) -> dict[str, list[dict[str, Any]]]:
    query_map = {str(query["query_id"]): query for query in queries}
    pairs: list[tuple[str, str]] = []
    references: list[tuple[str, int, str]] = []
    for query_id in sorted(rankings):
        query_text = str(query_map[query_id]["text"])
        for candidate_index, candidate in enumerate(rankings[query_id][:rerank_depth]):
            chunk_id = str(candidate["chunk_id"])
            source = source_map[chunk_id]
            pairs.append((query_text, str(source["text"])))
            references.append((query_id, candidate_index, chunk_id))
    scores = score_pairs(pairs, scorer=scorer)
    diagnostics = pair_diagnostics(pairs, scorer=scorer)
    updates: dict[tuple[str, int], tuple[float, dict[str, Any]]] = {}
    for reference, score, diagnostic in zip(references, scores, diagnostics):
        query_id, candidate_index, _chunk_id = reference
        updates[(query_id, candidate_index)] = (score, diagnostic)

    output: dict[str, list[dict[str, Any]]] = {}
    for query_id in sorted(rankings):
        head: list[dict[str, Any]] = []
        tail: list[dict[str, Any]] = []
        for index, candidate in enumerate(rankings[query_id]):
            record = deepcopy(candidate)
            record["pre_rerank_rank"] = int(candidate["rank"])
            record["rrf_score"] = candidate.get("score")
            if index < rerank_depth:
                score, diagnostic = updates[(query_id, index)]
                record["cross_encoder_score"] = score
                record["cross_encoder_input"] = diagnostic
                record["score"] = score
                record["score_type"] = "cross_encoder_raw_logit"
                record["reranked"] = True
                head.append(record)
            else:
                record["cross_encoder_score"] = None
                record["score_type"] = "rrf_tail_not_reranked"
                record["reranked"] = False
                tail.append(record)
        head.sort(
            key=lambda item: (
                -float(item["cross_encoder_score"]),
                int(item["pre_rerank_rank"]),
                str(item["chunk_id"]),
            )
        )
        ordered = head + tail
        for rank, candidate in enumerate(ordered, 1):
            candidate["rank"] = rank
        output[query_id] = ordered
    return output


def run_similarity_pipeline(
    report_chunks: Sequence[dict[str, Any]],
    source_chunks: Sequence[dict[str, Any]],
    *,
    config: Mapping[str, Any],
    encoder: Encoder | None,
    reranker: PairScorer | None,
) -> dict[str, Any]:
    """Run the complete offline Pipeline 1 feasibility baseline."""

    resolved = validate_similarity_config(config)
    if not report_chunks:
        raise ValueError("Pipeline 1 requires at least one report chunk")
    if not source_chunks:
        raise ValueError("Pipeline 1 requires at least one source chunk")
    if resolved["dense_enabled"] and encoder is None:
        raise ValueError("Dense retrieval is enabled but no encoder was provided")
    if resolved["reranker_enabled"] and reranker is None:
        raise ValueError("Reranking is enabled but no Cross-Encoder was provided")

    queries = [
        {
            "query_id": str(chunk["chunk_id"]),
            "text": str(chunk.get("text_with_context", chunk["text"])),
            "report_chunk_id": str(chunk["chunk_id"]),
        }
        for chunk in report_chunks
    ]
    query_map = {str(chunk["chunk_id"]): chunk for chunk in report_chunks}
    source_map = {str(chunk["chunk_id"]): chunk for chunk in source_chunks}
    if len(source_map) != len(source_chunks):
        raise ValueError("Source chunk IDs must be unique")

    # A per-source cap may discard a method's first several passages. Fetch
    # the full ranked source list in that opt-in mode so another document can
    # refill the bounded candidate pool; the default path keeps its old depth.
    retrieval_depth = (
        len(source_chunks)
        if resolved["evidence_budget_per_source"] is not None
        else resolved["candidate_depth"]
    )
    bm25 = rank_bm25(
        source_chunks,
        queries,
        top_k=retrieval_depth,
        k1=resolved["bm25_k1"],
        b=resolved["bm25_b"],
    )
    methods: dict[str, dict[str, list[dict[str, Any]]]] = {"bm25": bm25}
    if resolved["dense_enabled"]:
        assert encoder is not None
        methods["dense"] = rank_dense(
            source_chunks,
            queries,
            encoder=encoder,
            top_k=retrieval_depth,
        )
    if len(methods) == 1:
        candidates = deepcopy(bm25)
        for values in candidates.values():
            for candidate in values:
                candidate["score_type"] = "bm25"
    else:
        candidates = fuse_rrf(
            methods,
            rrf_k=resolved["rrf_k"],
            top_k=(
                len(source_chunks)
                if resolved["candidate_selection"] == "quota_union"
                or resolved["evidence_budget_per_source"] is not None
                else resolved["candidate_depth"]
            ),
        )
        for values in candidates.values():
            for candidate in values:
                candidate["score_type"] = "rrf"
    if (
        resolved["candidate_selection"] == "quota_union"
        or resolved["evidence_budget_per_source"] is not None
    ):
        candidates = _select_candidate_pool(
            candidates,
            methods,
            candidate_depth=resolved["candidate_depth"],
            rerank_depth=(
                resolved["rerank_depth"]
                if resolved["reranker_enabled"]
                else resolved["top_k"]
            ),
            candidate_selection=resolved["candidate_selection"],
            candidate_quotas=resolved["candidate_quotas"],
            evidence_budget_per_source=resolved["evidence_budget_per_source"],
        )
    if resolved["reranker_enabled"]:
        assert reranker is not None
        candidates = _rerank_chunks(
            candidates,
            queries,
            source_map,
            scorer=reranker,
            rerank_depth=resolved["rerank_depth"],
        )

    matches: list[dict[str, Any]] = []
    flagged_query_ids: set[str] = set()
    review_query_ids: set[str] = set()
    exact_selected_ranges: dict[str, list[tuple[int, int]]] = defaultdict(list)
    selected_source_documents: Counter[str] = Counter()
    selected_by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    label_counts: Counter[str] = Counter()
    for query in queries:
        query_id = str(query["query_id"])
        report_chunk = query_map[query_id]
        query_matches: list[dict[str, Any]] = []
        for candidate in candidates.get(query_id, [])[: resolved["top_k"]]:
            source_chunk = source_map[str(candidate["chunk_id"])]
            features = _similarity_features(
                str(report_chunk["text"]),
                str(source_chunk["text"]),
            )
            alignment = _alignment(
                report_chunk,
                source_chunk,
                minimum_chars=resolved["classification"]["minimum_alignment_chars"],
            )
            evidence_backed_exact_span = _is_evidence_backed_exact_span(
                alignment,
                minimum_alignment_chars=resolved["classification"]["minimum_alignment_chars"],
            )
            dense_score = _dense_support_score(candidate)
            cross_encoder_score = candidate.get("cross_encoder_score")
            label, heuristic_score, reasons = _classify(
                features,
                alignment=alignment,
                evidence_backed_exact_span=evidence_backed_exact_span,
                dense_score=dense_score,
                cross_encoder_score=(
                    float(cross_encoder_score)
                    if isinstance(cross_encoder_score, (int, float))
                    and not isinstance(cross_encoder_score, bool)
                    else None
                ),
                thresholds=resolved["classification"],
            )
            if label is not None and label not in SIMILARITY_TYPES:
                raise AssertionError(f"Unexpected similarity label: {label}")
            evidence_status = _evidence_status(
                label, evidence_backed_exact_span=evidence_backed_exact_span
            )
            record = {
                "query_id": query_id,
                "report_chunk_id": report_chunk["chunk_id"],
                "source_document_id": source_chunk["document_id"],
                "source_name": source_chunk.get("source_name"),
                "source_chunk_id": source_chunk["chunk_id"],
                "rank": int(candidate["rank"]),
                "retrieval_score": candidate.get("score"),
                "retrieval_score_type": candidate.get("score_type"),
                "rrf_score": candidate.get("rrf_score", candidate.get("score") if candidate.get("score_type") == "rrf" else None),
                "cross_encoder_score": candidate.get("cross_encoder_score"),
                "dense_score": dense_score,
                "similarity_type": (
                    None
                    if evidence_status == "PROVISIONAL_REVIEW_REQUIRED"
                    else label
                ),
                "provisional_similarity_type": (
                    label
                    if evidence_status == "PROVISIONAL_REVIEW_REQUIRED"
                    else None
                ),
                "classification_status": evidence_status,
                "semantic_verification_status": (
                    "NOT_RUN" if label is None else "NOT_APPLICABLE"
                ),
                "heuristic_score": heuristic_score,
                "score_calibration_status": "UNCALIBRATED",
                "classification_reasons": reasons,
                "features": features,
                "alignment": alignment,
                "selected_for_document_coverage": False,
                "selected_for_manual_review": False,
            }
            if "global_preselection_rank" in candidate:
                record["global_preselection_rank"] = candidate[
                    "global_preselection_rank"
                ]
                record["candidate_selection_reasons"] = candidate[
                    "candidate_selection_reasons"
                ]
                if "global_rrf_rank" in candidate:
                    record["global_rrf_rank"] = candidate["global_rrf_rank"]
            query_matches.append(record)
        # One report chunk may contain distinct copied spans from different
        # sources.  Selecting only the first exact candidate silently lost the
        # later spans and their provenance.  Keep every exact candidate that
        # adds at least one previously uncovered report token, while still
        # suppressing duplicate sources for the very same span.
        report_text = str(
            report_chunk.get("normalized_text", report_chunk.get("text", ""))
        )
        report_token_ranges = token_spans(report_text)
        query_exact_ranges: list[tuple[int, int]] = []
        selected_exact_matches: list[dict[str, Any]] = []
        for match in query_matches:
            if match["classification_status"] != "EVIDENCE_BACKED_EXACT_MATCH":
                continue
            report_range = match["alignment"]["report"]
            candidate_range = (
                int(report_range["normalized_start"]),
                int(report_range["normalized_end"]),
            )
            adds_new_token = any(
                candidate_range[0] <= token_start
                and token_end <= candidate_range[1]
                and not any(
                    selected_start <= token_start and token_end <= selected_end
                    for selected_start, selected_end in query_exact_ranges
                )
                for token_start, token_end in report_token_ranges
            )
            if not adds_new_token:
                match["selection_exclusion_reason"] = (
                    "DUPLICATE_REPORT_TOKEN_COVERAGE"
                )
                continue
            match["selected_for_document_coverage"] = True
            query_exact_ranges.append(candidate_range)
            selected_exact_matches.append(match)

        if selected_exact_matches:
            flagged_query_ids.add(query_id)
            exact_selected_ranges[query_id].extend(query_exact_ranges)
            for selected in selected_exact_matches:
                selected_source_documents[str(selected["source_document_id"])] += 1
                selected_by_source[str(selected["source_document_id"])].append(
                    selected
                )
                label_counts[str(selected["similarity_type"])] += 1
        else:
            provisional = next(
                (
                    match
                    for match in query_matches
                    if match["classification_status"] == "PROVISIONAL_REVIEW_REQUIRED"
                ),
                None,
            )
            if provisional is not None:
                provisional["selected_for_manual_review"] = True
                review_query_ids.add(query_id)
        matches.extend(query_matches)

    review_source_groups = _group_review_candidates(matches)
    keys_by_query = {
        query_id: _document_token_keys(chunk) for query_id, chunk in query_map.items()
    }
    all_token_keys = {key for tokens in keys_by_query.values() for _, _, key in tokens}
    flagged_token_keys = {
        key for query_id in flagged_query_ids for _, _, key in keys_by_query[query_id]
    }
    exact_token_keys = {
        key for query_id, ranges in exact_selected_ranges.items()
        for left, right, key in keys_by_query[query_id]
        if any(start <= left and right <= end for start, end in ranges)
    }
    total_report_tokens = len(all_token_keys)
    flagged_report_tokens = len(flagged_token_keys)
    exact_matched_report_tokens = len(exact_token_keys)
    flagged_passage_coverage = (
        100.0 * flagged_report_tokens / total_report_tokens
        if total_report_tokens
        else 0.0
    )
    provisional_review_tokens = len({
        key for query_id in review_query_ids for _, _, key in keys_by_query[query_id]
    })
    provisional_review_coverage = (
        100.0 * provisional_review_tokens / total_report_tokens
        if total_report_tokens
        else 0.0
    )
    exact_match_coverage = (
        100.0 * exact_matched_report_tokens / total_report_tokens
        if total_report_tokens
        else 0.0
    )
    exact_keys_by_source: dict[str, set[tuple[Any, ...]]] = {}
    for document_id, values in selected_by_source.items():
        source_keys: set[tuple[Any, ...]] = set()
        for value in values:
            location = value["alignment"]["report"]
            source_keys.update(
                key for left, right, key in keys_by_query[str(value["query_id"])]
                if location["normalized_start"] <= left and right <= location["normalized_end"]
            )
        exact_keys_by_source[document_id] = source_keys
    source_summary: list[dict[str, Any]] = []
    for source_rank, (document_id, count) in enumerate(
        sorted(
            selected_source_documents.items(),
            key=lambda item: (-len(exact_keys_by_source[item[0]]), item[0]),
        ),
        1,
    ):
        values = selected_by_source[document_id]
        scores = [float(value["heuristic_score"]) for value in values]
        source_query_ids = {str(value["query_id"]) for value in values}
        source_flagged_tokens = len({
            key for query_id in source_query_ids for _, _, key in keys_by_query[query_id]
        })
        source_exact_tokens = len(exact_keys_by_source[document_id])
        source_summary.append(
            {
                "rank": source_rank,
                "source_document_id": document_id,
                "source_name": next(
                    (
                        chunk.get("source_name")
                        for chunk in source_chunks
                        if chunk["document_id"] == document_id
                    ),
                    None,
                ),
                "selected_report_passages": count,
                "selected_label_counts": dict(
                    sorted(Counter(value["similarity_type"] for value in values).items())
                ),
                "max_uncalibrated_heuristic_score": max(scores),
                "mean_uncalibrated_heuristic_score": sum(scores) / len(scores),
                "flagged_report_tokens": source_flagged_tokens,
                "exact_matched_report_tokens": source_exact_tokens,
                "exact_token_coverage_weight": (
                    round(source_exact_tokens / total_report_tokens, 8)
                    if total_report_tokens else 0.0
                ),
                "flagged_report_token_coverage_percentage": round(
                    100.0 * source_flagged_tokens / total_report_tokens,
                    4,
                )
                if total_report_tokens
                else 0.0,
            }
        )
    return {
        "schema_version": 1,
        "pipeline": "similarity-core-mvp-v0",
        "research_status": "FEASIBILITY_BASELINE_NOT_FINAL_CLASSIFIER",
        "classification_policy": CLASSIFICATION_POLICY,
        "semantic_classifier_available": False,
        "deprecated_unused_thresholds": ["summary_length_ratio"],
        "configuration": resolved,
        "retrieval_methods": sorted(methods),
        "report_chunk_count": len(report_chunks),
        "source_chunk_count": len(source_chunks),
        "total_report_tokens": total_report_tokens,
        "flagged_report_tokens_unique_by_report_chunk": flagged_report_tokens,
        "exact_matched_report_tokens": exact_matched_report_tokens,
        "flagged_passage_coverage_percentage": round(flagged_passage_coverage, 4),
        "provisional_review_report_chunks": len(review_query_ids),
        "provisional_review_passage_coverage_percentage": round(
            provisional_review_coverage, 4
        ),
        "exact_match_coverage_percentage": round(exact_match_coverage, 4),
        "calibrated_similarity_percentage": None,
        "calibrated_similarity_status": "UNAVAILABLE_WITHOUT_LABELLED_CALIBRATION",
        "label_counts_for_selected_matches": dict(sorted(label_counts.items())),
        "source_summary": source_summary,
        "review_source_groups": review_source_groups,
        "coverage_definitions": {
            "version": "document-element-token-union-v2",
            "scope": (
                "DOCUMENT_VERSION_ELEMENT_COORDINATES"
                if all(key[0] == "element" for key in all_token_keys)
                else "CHUNK_LOCAL_FALLBACK_PRESENT"
            ),
            "exact": {
                "unit": "unique_report_token",
                "definition": "Union of exact aligned report tokens divided by the union of all report tokens, keyed by document version, parser element and normalized offsets. Overlapping chunks count once.",
            },
            "source_aggregation": {
                "formula": "source exact-token union / report token union",
                "ranking": "descending exact token coverage weight, then source_document_id",
                "is_calibrated_probability": False,
            },
            "provisional_review": {
                "is_similarity_percentage": False,
                "unit": "unique_report_token",
                "definition": "Union of tokens in selected unverified report chunks divided by all report tokens. Measures review workload, not matched spans or confirmed similarity; legacy inputs without element coordinates fall back to chunk-local counting.",
            },
        },
        "matches": matches,
        "disclaimer": (
            "Similarity is not a plagiarism verdict. The classifier in this MVP is "
            "a transparent heuristic feasibility baseline. Retrieval relevance "
            "does not establish paraphrase or summary: both semantic labels remain "
            "null until an independently evaluated semantic validator exists. "
            "Review groups retain all selected pairs; repeated source retrieval "
            "is not independent evidence. Review coverage measures chunk-token "
            "workload, not similarity. "
            "Lecturer review is required before academic use."
        ),
    }
