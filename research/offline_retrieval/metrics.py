"""Span-grounded retrieval metrics shared across chunking strategies."""

from __future__ import annotations

import math
from typing import Any, Iterable, Mapping


def _overlap_fraction(candidate: Mapping[str, Any], gold: Mapping[str, Any]) -> float:
    if candidate.get("document_id") != gold.get("document_id"):
        return 0.0
    start = max(int(candidate["raw_start"]), int(gold["raw_start"]))
    end = min(int(candidate["raw_end"]), int(gold["raw_end"]))
    overlap = max(0, end - start)
    gold_length = max(1, int(gold["raw_end"]) - int(gold["raw_start"]))
    return overlap / gold_length


def evaluate_rankings(
    rankings: Mapping[str, list[dict[str, Any]]],
    qrels: Iterable[dict[str, Any]],
    *,
    cutoffs: list[int],
    overlap_threshold: float = 0.5,
) -> dict[str, Any]:
    if not cutoffs or any(value <= 0 for value in cutoffs):
        raise ValueError("Metric cutoffs must contain positive integers")
    if not 0 < overlap_threshold <= 1:
        raise ValueError("overlap_threshold must be in (0, 1]")

    gold_by_query: dict[str, list[dict[str, Any]]] = {}
    for index, qrel in enumerate(qrels):
        query_id = str(qrel["query_id"])
        record = dict(qrel)
        record.setdefault("qrel_id", f"{query_id}:{index}")
        gold_by_query.setdefault(query_id, []).append(record)
    query_ids = sorted(gold_by_query)
    if not query_ids:
        raise ValueError("At least one qrel is required")

    per_query: dict[str, Any] = {}
    aggregates = {
        cutoff: {"recall": [], "reciprocal_rank": [], "ndcg": []}
        for cutoff in sorted(set(cutoffs))
    }
    for query_id in query_ids:
        gold = gold_by_query[query_id]
        candidates = rankings.get(query_id, [])
        per_query[query_id] = {}
        for cutoff in aggregates:
            selected = candidates[:cutoff]
            matched_gold: set[str] = set()
            relevance: list[int] = []
            first_relevant_rank = 0
            for rank, candidate in enumerate(selected, 1):
                candidate_matches: list[str] = []
                for qrel in gold:
                    qrel_id = str(qrel["qrel_id"])
                    if any(
                        _overlap_fraction(span, qrel) >= overlap_threshold
                        for span in candidate.get("source_spans", [])
                    ):
                        candidate_matches.append(qrel_id)
                new_matches = set(candidate_matches) - matched_gold
                matched_gold.update(new_matches)
                # Duplicate chunks covering the same gold span do not earn
                # relevance twice; otherwise nDCG could exceed 1.0.
                is_relevant = int(bool(new_matches))
                relevance.append(is_relevant)
                if is_relevant and not first_relevant_rank:
                    first_relevant_rank = rank

            recall = len(matched_gold) / len(gold)
            reciprocal_rank = 1.0 / first_relevant_rank if first_relevant_rank else 0.0
            dcg = sum(value / math.log2(rank + 1) for rank, value in enumerate(relevance, 1))
            ideal_count = min(len(gold), cutoff)
            ideal_dcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_count + 1))
            ndcg = dcg / ideal_dcg if ideal_dcg else 0.0
            values = {
                "recall": recall,
                "reciprocal_rank": reciprocal_rank,
                "ndcg": ndcg,
            }
            per_query[query_id][str(cutoff)] = values
            for name, value in values.items():
                aggregates[cutoff][name].append(value)

    macro = {
        str(cutoff): {
            "recall": sum(values["recall"]) / len(query_ids),
            "mrr": sum(values["reciprocal_rank"]) / len(query_ids),
            "ndcg": sum(values["ndcg"]) / len(query_ids),
        }
        for cutoff, values in aggregates.items()
    }
    return {
        "query_count": len(query_ids),
        "qrel_count": sum(len(values) for values in gold_by_query.values()),
        "overlap_threshold": overlap_threshold,
        "macro": macro,
        "per_query": per_query,
    }


def evaluate_document_rankings(
    rankings: Mapping[str, list[dict[str, Any]]],
    qrels: Iterable[dict[str, Any]],
    *,
    cutoffs: list[int],
) -> dict[str, Any]:
    """Evaluate unique source-document rankings for source retrieval."""

    if not cutoffs or any(value <= 0 for value in cutoffs):
        raise ValueError("Metric cutoffs must contain positive integers")

    gold_by_query: dict[str, set[str]] = {}
    qrel_count = 0
    for qrel in qrels:
        query_id = str(qrel["query_id"])
        document_id = str(qrel["document_id"])
        gold_by_query.setdefault(query_id, set()).add(document_id)
        qrel_count += 1
    query_ids = sorted(gold_by_query)
    if not query_ids:
        raise ValueError("At least one qrel is required")

    per_query: dict[str, Any] = {}
    aggregates = {
        cutoff: {"recall": [], "reciprocal_rank": [], "ndcg": []}
        for cutoff in sorted(set(cutoffs))
    }
    for query_id in query_ids:
        gold = gold_by_query[query_id]
        candidates = rankings.get(query_id, [])
        candidate_ids = [str(candidate["document_id"]) for candidate in candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError(
                f"Document ranking for {query_id} contains duplicate document_id"
            )
        per_query[query_id] = {}
        for cutoff in aggregates:
            selected = candidate_ids[:cutoff]
            relevance = [int(document_id in gold) for document_id in selected]
            matched = set(selected) & gold
            first_relevant_rank = next(
                (rank for rank, value in enumerate(relevance, 1) if value), 0
            )
            recall = len(matched) / len(gold)
            reciprocal_rank = 1.0 / first_relevant_rank if first_relevant_rank else 0.0
            dcg = sum(
                value / math.log2(rank + 1)
                for rank, value in enumerate(relevance, 1)
            )
            ideal_count = min(len(gold), cutoff)
            ideal_dcg = sum(
                1.0 / math.log2(rank + 1)
                for rank in range(1, ideal_count + 1)
            )
            ndcg = dcg / ideal_dcg if ideal_dcg else 0.0
            values = {
                "recall": recall,
                "reciprocal_rank": reciprocal_rank,
                "ndcg": ndcg,
            }
            per_query[query_id][str(cutoff)] = values
            for name, value in values.items():
                aggregates[cutoff][name].append(value)

    macro = {
        str(cutoff): {
            "recall": sum(values["recall"]) / len(query_ids),
            "mrr": sum(values["reciprocal_rank"]) / len(query_ids),
            "ndcg": sum(values["ndcg"]) / len(query_ids),
        }
        for cutoff, values in aggregates.items()
    }
    return {
        "target_scope": "document",
        "query_count": len(query_ids),
        "qrel_count": qrel_count,
        "macro": macro,
        "per_query": per_query,
    }
