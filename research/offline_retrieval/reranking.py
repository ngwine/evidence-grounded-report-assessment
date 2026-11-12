"""Deterministic document reranking with passage-level provenance."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .cross_encoder import PairScorer, pair_diagnostics, score_pairs


@dataclass(frozen=True)
class _PairReference:
    query_id: str
    document_id: str
    method: str
    support_id: str
    source_spans: list[dict[str, Any]]


def _require_text(record: Mapping[str, Any], field: str, label: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label}.{field} must be a non-empty string")
    return value


def _candidate_supports(
    candidate: Mapping[str, Any],
    *,
    methods: Sequence[str],
    default_method: str,
) -> list[tuple[str, str, list[dict[str, Any]]]]:
    """Return distinct ``(method, support_id, spans)`` in locked method order."""

    supports_by_method = candidate.get("supports_by_method")
    supports: list[tuple[str, str, list[dict[str, Any]]]] = []
    if isinstance(supports_by_method, Mapping):
        for method in methods:
            support = supports_by_method.get(method)
            if not isinstance(support, Mapping):
                continue
            support_id = support.get(
                "supporting_chunk_id", support.get("chunk_id", support.get("support_id"))
            )
            if not isinstance(support_id, str) or not support_id:
                raise ValueError(
                    f"Candidate support for method {method} requires a support id"
                )
            spans = support.get("source_spans", [])
            if not isinstance(spans, list):
                raise ValueError("Candidate support source_spans must be a list")
            supports.append((method, support_id, deepcopy(spans)))
    else:
        support_id = candidate.get("supporting_chunk_id", candidate.get("chunk_id"))
        if not isinstance(support_id, str) or not support_id:
            raise ValueError("Rerank candidate requires a supporting passage id")
        spans = candidate.get("source_spans", [])
        if not isinstance(spans, list):
            raise ValueError("Candidate source_spans must be a list")
        supports.append((default_method, support_id, deepcopy(spans)))

    # The two views may select the same passage. Score it once while preserving
    # the first method in the protocol-defined order as provenance.
    distinct: list[tuple[str, str, list[dict[str, Any]]]] = []
    seen_ids: set[str] = set()
    for support in supports:
        if support[1] in seen_ids:
            continue
        seen_ids.add(support[1])
        distinct.append(support)
    if not distinct:
        raise ValueError("No configured support passage is available for reranking")
    return distinct


def rerank_documents(
    candidate_rankings: Mapping[str, list[dict[str, Any]]],
    queries: Sequence[dict[str, Any]],
    passages: Mapping[str, dict[str, Any]],
    *,
    scorer: PairScorer,
    rerank_depth: int,
    top_k: int,
    support_methods: Sequence[str],
    default_support_method: str,
) -> dict[str, list[dict[str, Any]]]:
    """Rerank the head of a source-document list and retain its original tail.

    A multi-view candidate can expose one lexical and one semantic support
    passage. Both are scored and the maximum passage score becomes the source
    document score. The exact winning passage/span remains in the output.

    Candidates below ``rerank_depth`` are appended in their original order so
    Recall@100 continues to measure the frozen candidate pool. Their ``score``
    is ``None`` because a Cross-Encoder score was deliberately not computed;
    ``candidate_score`` retains the upstream retrieval/fusion score.
    """

    if rerank_depth <= 0 or top_k <= 0:
        raise ValueError("rerank_depth and top_k must be positive")
    if rerank_depth > top_k:
        raise ValueError("rerank_depth must not exceed top_k")
    if not support_methods:
        raise ValueError("support_methods must not be empty")

    query_map: dict[str, dict[str, Any]] = {}
    for query in queries:
        query_id = _require_text(query, "query_id", "query")
        _require_text(query, "text", f"query[{query_id}]")
        if query_id in query_map:
            raise ValueError(f"Duplicate query_id: {query_id}")
        query_map[query_id] = query
    if set(candidate_rankings) != set(query_map):
        raise ValueError("Candidate rankings and queries must contain identical query IDs")

    pair_values: list[tuple[str, str]] = []
    references: list[_PairReference] = []
    for query_id in sorted(query_map):
        query_text = str(query_map[query_id]["text"])
        candidates = candidate_rankings[query_id]
        document_ids = [
            _require_text(candidate, "document_id", f"candidate[{query_id}]")
            for candidate in candidates
        ]
        if len(document_ids) != len(set(document_ids)):
            raise ValueError(f"Duplicate document candidate for query {query_id}")
        for candidate in candidates[:rerank_depth]:
            document_id = str(candidate["document_id"])
            for method, support_id, source_spans in _candidate_supports(
                candidate,
                methods=support_methods,
                default_method=default_support_method,
            ):
                passage = passages.get(support_id)
                if passage is None:
                    raise ValueError(f"Unknown support passage id: {support_id}")
                passage_document_id = _require_text(
                    passage, "document_id", f"passage[{support_id}]"
                )
                if passage_document_id != document_id:
                    raise ValueError(
                        f"Support passage {support_id} belongs to {passage_document_id}, "
                        f"not candidate document {document_id}"
                    )
                passage_text = _require_text(passage, "text", f"passage[{support_id}]")
                passage_spans = passage.get("source_spans", source_spans)
                if not isinstance(passage_spans, list):
                    raise ValueError(
                        f"Passage {support_id} source_spans must be a list"
                    )
                pair_values.append((query_text, passage_text))
                references.append(
                    _PairReference(
                        query_id=query_id,
                        document_id=document_id,
                        method=method,
                        support_id=support_id,
                        source_spans=deepcopy(passage_spans),
                    )
                )

    scores = score_pairs(pair_values, scorer=scorer)
    input_diagnostics = pair_diagnostics(pair_values, scorer=scorer)

    scored_supports: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for reference, score, diagnostic in zip(
        references, scores, input_diagnostics
    ):
        scored_supports.setdefault(
            (reference.query_id, reference.document_id), []
        ).append(
            {
                "method": reference.method,
                "support_id": reference.support_id,
                "score": score,
                "source_spans": deepcopy(reference.source_spans),
                "cross_encoder_input": deepcopy(diagnostic),
                "model_visible_source_spans": (
                    deepcopy(reference.source_spans)
                    if diagnostic.get("truncated") is False
                    else None
                ),
            }
        )

    reranked: dict[str, list[dict[str, Any]]] = {}
    for query_id in sorted(query_map):
        candidates = candidate_rankings[query_id][:top_k]
        head: list[dict[str, Any]] = []
        for candidate in candidates[:rerank_depth]:
            document_id = str(candidate["document_id"])
            support_scores = scored_supports[(query_id, document_id)]
            # Method order is already deterministic. The support id resolves
            # the remaining tie without relying on input corpus order.
            method_order = {method: index for index, method in enumerate(support_methods)}
            winner = min(
                support_scores,
                key=lambda item: (
                    -float(item["score"]),
                    method_order.get(str(item["method"]), len(method_order)),
                    str(item["support_id"]),
                ),
            )
            record = deepcopy(candidate)
            record["candidate_score"] = record.get("score")
            record["pre_rerank_rank"] = int(record["rank"])
            record["score"] = float(winner["score"])
            record["score_type"] = "cross_encoder_raw_logit"
            record["cross_encoder_score"] = float(winner["score"])
            record["cross_encoder_support_id"] = str(winner["support_id"])
            record["cross_encoder_support_method"] = str(winner["method"])
            record["cross_encoder_scores_by_support"] = support_scores
            record["cross_encoder_input"] = deepcopy(
                winner["cross_encoder_input"]
            )
            record["model_visible_source_spans"] = deepcopy(
                winner["model_visible_source_spans"]
            )
            record["source_spans_semantics"] = (
                "candidate_passage_origin; consult cross_encoder_input.truncated "
                "before treating the full span as model-visible"
            )
            record["supporting_chunk_id"] = str(winner["support_id"])
            record["source_spans"] = deepcopy(winner["source_spans"])
            record["reranked"] = True
            head.append(record)

        head.sort(
            key=lambda item: (
                -float(item["cross_encoder_score"]),
                int(item["pre_rerank_rank"]),
                str(item["document_id"]),
                str(item["cross_encoder_support_id"]),
            )
        )
        tail: list[dict[str, Any]] = []
        for candidate in candidates[rerank_depth:]:
            record = deepcopy(candidate)
            record["candidate_score"] = record.get("score")
            record["pre_rerank_rank"] = int(record["rank"])
            record["score"] = None
            record["score_type"] = "not_reranked_tail"
            record["cross_encoder_score"] = None
            record["reranked"] = False
            tail.append(record)
        ordered = head + tail
        for rank, candidate in enumerate(ordered, 1):
            candidate["rank"] = rank
        reranked[query_id] = ordered
    return reranked
