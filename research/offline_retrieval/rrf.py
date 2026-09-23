"""Reciprocal Rank Fusion with deterministic tie-breaking."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


def fuse_rrf(
    rankings: Mapping[str, Mapping[str, list[dict[str, Any]]]],
    *,
    rrf_k: int = 60,
    top_k: int,
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
        contributions: dict[str, dict[str, int]] = {}
        for method in methods:
            for candidate in rankings[method].get(query_id, []):
                chunk_id = str(candidate["chunk_id"])
                rank = int(candidate["rank"])
                scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (rrf_k + rank)
                payloads.setdefault(chunk_id, deepcopy(candidate))
                contributions.setdefault(chunk_id, {})[method] = rank
        ordered = sorted(scores, key=lambda chunk_id: (-scores[chunk_id], chunk_id))
        fused[query_id] = []
        for rank, chunk_id in enumerate(ordered[:top_k], 1):
            candidate = payloads[chunk_id]
            candidate["score"] = scores[chunk_id]
            candidate["rank"] = rank
            candidate["rrf_ranks"] = contributions[chunk_id]
            fused[query_id].append(candidate)
    return fused
