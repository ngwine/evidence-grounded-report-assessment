"""Reciprocal Rank Fusion with deterministic tie-breaking."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


def fuse_rrf(
    rankings: Mapping[str, Mapping[str, list[dict[str, Any]]]],
    *,
    rrf_k: int = 60,
    top_k: int,
    key_field: str = "chunk_id",
) -> dict[str, list[dict[str, Any]]]:
    if rrf_k <= 0 or top_k <= 0:
        raise ValueError("rrf_k and top_k must be positive")
    methods = sorted(rankings)
    query_ids = sorted(
        {query_id for method in methods for query_id in rankings[method]}
    )
    fused: dict[str, list[dict[str, Any]]] = {}
    for query_id in query_ids:
        scores: dict[str, float] = {}
        payloads: dict[str, dict[str, Any]] = {}
        representative_methods: dict[str, str] = {}
        contributions: dict[str, dict[str, int]] = {}
        supporting_ids: dict[str, dict[str, str]] = {}
        supports_by_method: dict[str, dict[str, dict[str, Any]]] = {}
        for method in methods:
            for candidate in rankings[method].get(query_id, []):
                if key_field not in candidate:
                    raise ValueError(f"RRF candidate requires {key_field}")
                candidate_id = str(candidate[key_field])
                rank = int(candidate["rank"])
                scores[candidate_id] = scores.get(candidate_id, 0.0) + 1.0 / (
                    rrf_k + rank
                )
                if candidate_id not in payloads:
                    payloads[candidate_id] = deepcopy(candidate)
                    representative_methods[candidate_id] = method
                contributions.setdefault(candidate_id, {})[method] = rank
                support_id = candidate.get(
                    "supporting_chunk_id", candidate.get("chunk_id")
                )
                if support_id is not None:
                    supporting_ids.setdefault(candidate_id, {})[method] = str(
                        support_id
                    )
                support = {
                    "support_id": str(support_id or candidate_id),
                    "rank": rank,
                    "score": deepcopy(candidate.get("score")),
                    "source_spans": deepcopy(candidate.get("source_spans", [])),
                }
                if candidate.get("chunk_id") is not None:
                    support["chunk_id"] = str(candidate["chunk_id"])
                if candidate.get("supporting_chunk_id") is not None:
                    support["supporting_chunk_id"] = str(
                        candidate["supporting_chunk_id"]
                    )
                supports_by_method.setdefault(candidate_id, {})[method] = support
        ordered = sorted(
            scores, key=lambda candidate_id: (-scores[candidate_id], candidate_id)
        )
        fused[query_id] = []
        for rank, candidate_id in enumerate(ordered[:top_k], 1):
            candidate = payloads[candidate_id]
            candidate["score"] = scores[candidate_id]
            candidate["rank"] = rank
            candidate["rrf_ranks"] = contributions[candidate_id]
            candidate["rrf_supporting_ids"] = supporting_ids.get(candidate_id, {})
            candidate["supports_by_method"] = supports_by_method[candidate_id]
            candidate["representative_support_method"] = representative_methods[
                candidate_id
            ]
            # Keep legacy representative fields for older consumers, but make
            # top-level source_spans the deterministic union of every method's
            # evidence instead of implying that one method supplied it all.
            merged_spans: list[dict[str, Any]] = []
            for method in methods:
                support = supports_by_method[candidate_id].get(method)
                if support is None:
                    continue
                for span in support["source_spans"]:
                    if span not in merged_spans:
                        merged_spans.append(deepcopy(span))
            candidate["source_spans"] = merged_spans
            fused[query_id].append(candidate)
    return fused
