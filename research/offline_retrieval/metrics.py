"""Span-grounded retrieval metrics shared across chunking strategies."""

from __future__ import annotations

import math
from typing import Any, Iterable, Mapping


def _union_coverage_fraction(
    candidates: Iterable[Mapping[str, Any]], gold: Mapping[str, Any]
) -> float:
    """Return coverage of one gold span by the union of retrieved spans.

    Coverage is clipped to the gold boundary before intervals are merged. This
    prevents overlapping chunks from counting the same characters twice while
    allowing several smaller chunks to jointly cover one long evidence span.
    """

    gold_document_id = gold.get("document_id")
    gold_start = int(gold["raw_start"])
    gold_end = int(gold["raw_end"])
    intervals: list[tuple[int, int]] = []
    for candidate in candidates:
        if candidate.get("document_id") != gold_document_id:
            continue
        start = max(int(candidate["raw_start"]), gold_start)
        end = min(int(candidate["raw_end"]), gold_end)
        if start < end:
            intervals.append((start, end))
    if not intervals:
        return 0.0

    intervals.sort()
    covered = 0
    merged_start, merged_end = intervals[0]
    for start, end in intervals[1:]:
        if start <= merged_end:
            merged_end = max(merged_end, end)
        else:
            covered += merged_end - merged_start
            merged_start, merged_end = start, end
    covered += merged_end - merged_start
    return covered / max(1, gold_end - gold_start)


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
            covered_spans: dict[str, list[Mapping[str, Any]]] = {
                str(qrel["qrel_id"]): [] for qrel in gold
            }
            relevance: list[int] = []
            first_relevant_rank = 0
            for rank, candidate in enumerate(selected, 1):
                candidate_spans = candidate.get("source_spans", [])
                for qrel in gold:
                    qrel_id = str(qrel["qrel_id"])
                    covered_spans[qrel_id].extend(candidate_spans)
                new_matches = {
                    str(qrel["qrel_id"])
                    for qrel in gold
                    if str(qrel["qrel_id"]) not in matched_gold
                    and _union_coverage_fraction(
                        covered_spans[str(qrel["qrel_id"])], qrel
                    )
                    >= overlap_threshold
                }
                matched_gold.update(new_matches)
                # A qrel earns relevance once, at the rank where cumulative
                # union coverage first crosses the configured threshold.
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
        "target_scope": "span",
        "coverage_mode": "cumulative_union",
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
    parent_by_query: dict[str, str] = {}
    parent_qrel_count = 0
    qrel_count = 0
    for qrel in qrels:
        query_id = str(qrel["query_id"])
        document_id = str(qrel["document_id"])
        gold_by_query.setdefault(query_id, set()).add(document_id)
        parent_annotation_id = qrel.get("parent_annotation_id")
        if parent_annotation_id is not None:
            if not isinstance(parent_annotation_id, str) or not parent_annotation_id:
                raise ValueError("parent_annotation_id must be a non-empty string")
            previous_parent = parent_by_query.setdefault(
                query_id, parent_annotation_id
            )
            if previous_parent != parent_annotation_id:
                raise ValueError(
                    f"Query {query_id} references multiple parent annotations"
                )
            parent_qrel_count += 1
        qrel_count += 1
    query_ids = sorted(gold_by_query)
    if not query_ids:
        raise ValueError("At least one qrel is required")
    if parent_qrel_count not in {0, qrel_count}:
        raise ValueError(
            "parent_annotation_id must be present on every qrel or none"
        )

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
    result = {
        "target_scope": "document",
        "query_count": len(query_ids),
        "qrel_count": qrel_count,
        "macro": macro,
        "per_query": per_query,
    }
    if parent_by_query:
        queries_by_parent: dict[str, list[str]] = {}
        for query_id in query_ids:
            parent_annotation_id = parent_by_query[query_id]
            queries_by_parent.setdefault(parent_annotation_id, []).append(query_id)

        parent_macro: dict[str, dict[str, float]] = {}
        for cutoff in sorted(set(cutoffs)):
            key = str(cutoff)
            parent_values = []
            for parent_query_ids in queries_by_parent.values():
                count = len(parent_query_ids)
                parent_values.append(
                    {
                        "recall": sum(
                            per_query[query_id][key]["recall"]
                            for query_id in parent_query_ids
                        )
                        / count,
                        "mrr": sum(
                            per_query[query_id][key]["reciprocal_rank"]
                            for query_id in parent_query_ids
                        )
                        / count,
                        "ndcg": sum(
                            per_query[query_id][key]["ndcg"]
                            for query_id in parent_query_ids
                        )
                        / count,
                    }
                )
            parent_macro[key] = {
                metric: sum(values[metric] for values in parent_values)
                / len(parent_values)
                for metric in ("recall", "mrr", "ndcg")
            }

        result.update(
            {
                "parent_annotation_count": len(queries_by_parent),
                "queries_per_parent": {
                    parent_annotation_id: len(parent_query_ids)
                    for parent_annotation_id, parent_query_ids in sorted(
                        queries_by_parent.items()
                    )
                },
                "parent_macro": parent_macro,
            }
        )
    return result
