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
        contributions: dict[str, dict[str, int]] = {}
        supporting_ids: dict[str, dict[str, str]] = {}
        for method in methods:
            for candidate in rankings[method].get(query_id, []):
                if key_field not in candidate:
                    raise ValueError(f"RRF candidate requires {key_field}")
                candidate_id = str(candidate[key_field])
                rank = int(candidate["rank"])
                scores[candidate_id] = scores.get(candidate_id, 0.0) + 1.0 / (
                    rrf_k + rank
                )
                payloads.setdefault(candidate_id, deepcopy(candidate))
                contributions.setdefault(candidate_id, {})[method] = rank
                support_id = candidate.get(
                    "supporting_chunk_id", candidate.get("chunk_id")
                )
                if support_id is not None:
                    supporting_ids.setdefault(candidate_id, {})[method] = str(
                        support_id
                    )
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
            fused[query_id].append(candidate)
    return fused
