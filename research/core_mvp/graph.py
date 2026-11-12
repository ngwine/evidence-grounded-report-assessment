"""Deterministic structure-and-term graph retrieval baseline.

This is intentionally a small feasibility baseline, not a claim that the MVP
implements the complete HippoRAG architecture.  It builds traceable edges
between adjacent report chunks and chunks sharing informative terms, then runs
personalised PageRank from lexical seed scores.
"""

from __future__ import annotations

from collections import Counter, defaultdict
import math
from typing import Any, Mapping, Sequence

from research.offline_retrieval.bm25 import rank_bm25
from research.offline_retrieval.common import tokenize


_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
    "in", "is", "it", "of", "on", "or", "that", "the", "this", "to",
    "was", "were", "with", "và", "các", "có", "của", "cho", "được",
    "là", "một", "những", "trong", "trên", "từ", "với", "này", "đó",
}


def _terms(text: str) -> set[str]:
    return {
        token
        for token in tokenize(text)
        if len(token) >= 3 and token not in _STOPWORDS
    }


def _positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field} must be a positive integer")
    return value


def _unit_interval(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be numeric")
    number = float(value)
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        raise ValueError(f"{field} must be in [0, 1]")
    return number


def validate_graph_config(config: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "top_k": _positive_int(config.get("top_k", 5), "graph.top_k"),
        "seed_depth": _positive_int(
            config.get("seed_depth", 8), "graph.seed_depth"
        ),
        "iterations": _positive_int(
            config.get("iterations", 20), "graph.iterations"
        ),
        "damping": _unit_interval(config.get("damping", 0.85), "graph.damping"),
        "minimum_shared_terms": _positive_int(
            config.get("minimum_shared_terms", 2),
            "graph.minimum_shared_terms",
        ),
        "maximum_term_degree": _positive_int(
            config.get("maximum_term_degree", 30),
            "graph.maximum_term_degree",
        ),
    }


def _build_graph(
    chunks: Sequence[dict[str, Any]],
    *,
    minimum_shared_terms: int,
    maximum_term_degree: int,
) -> tuple[dict[str, dict[str, float]], dict[str, Any]]:
    chunk_ids = [str(chunk["chunk_id"]) for chunk in chunks]
    if len(chunk_ids) != len(set(chunk_ids)):
        raise ValueError("Graph chunks require unique chunk_id values")
    terms_by_id = {
        str(chunk["chunk_id"]): _terms(str(chunk.get("text", "")))
        for chunk in chunks
    }
    postings: dict[str, list[str]] = defaultdict(list)
    for chunk_id, terms in terms_by_id.items():
        for term in sorted(terms):
            postings[term].append(chunk_id)

    shared_counts: Counter[tuple[str, str]] = Counter()
    ignored_high_degree_terms = 0
    for chunk_ids_for_term in postings.values():
        if len(chunk_ids_for_term) > maximum_term_degree:
            ignored_high_degree_terms += 1
            continue
        ordered = sorted(chunk_ids_for_term)
        for left_index, left in enumerate(ordered):
            for right in ordered[left_index + 1 :]:
                shared_counts[(left, right)] += 1

    adjacency: dict[str, dict[str, float]] = {chunk_id: {} for chunk_id in chunk_ids}
    term_edge_count = 0
    for (left, right), count in sorted(shared_counts.items()):
        if count < minimum_shared_terms:
            continue
        weight = float(count)
        adjacency[left][right] = adjacency[left].get(right, 0.0) + weight
        adjacency[right][left] = adjacency[right].get(left, 0.0) + weight
        term_edge_count += 1

    document_order: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for fallback_order, chunk in enumerate(chunks):
        document_id = str(chunk.get("document_id", "report"))
        order_value = chunk.get("chunk_index", chunk.get("order", fallback_order))
        try:
            order = int(order_value)
        except (TypeError, ValueError):
            order = fallback_order
        document_order[document_id].append((order, str(chunk["chunk_id"])))
    adjacency_edge_count = 0
    for values in document_order.values():
        ordered_ids = [chunk_id for _order, chunk_id in sorted(values)]
        for left, right in zip(ordered_ids, ordered_ids[1:]):
            adjacency[left][right] = adjacency[left].get(right, 0.0) + 1.0
            adjacency[right][left] = adjacency[right].get(left, 0.0) + 1.0
            adjacency_edge_count += 1

    return adjacency, {
        "node_count": len(chunk_ids),
        "term_edge_count": term_edge_count,
        "adjacency_edge_count": adjacency_edge_count,
        "ignored_high_degree_terms": ignored_high_degree_terms,
    }


def rank_graph(
    chunks: Sequence[dict[str, Any]],
    *,
    query_id: str,
    query_text: str,
    config: Mapping[str, Any],
    seed_queries: Sequence[str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Rank report chunks with BM25-seeded personalised PageRank."""

    resolved = validate_graph_config(config)
    if not chunks:
        return [], {"graph": {"node_count": 0}, "seed_count": 0}
    source_map = {str(chunk["chunk_id"]): chunk for chunk in chunks}
    adjacency, diagnostics = _build_graph(
        chunks,
        minimum_shared_terms=resolved["minimum_shared_terms"],
        maximum_term_degree=resolved["maximum_term_degree"],
    )
    aspects = [value.strip() for value in (seed_queries or [query_text]) if value.strip()]
    if not aspects:
        aspects = [query_text]
    aspect_records = [
        {"query_id": f"{query_id}:seed:{index}", "text": value}
        for index, value in enumerate(aspects)
    ]
    aspect_rankings = rank_bm25(
        chunks,
        aspect_records,
        top_k=resolved["seed_depth"],
    )
    # Give every evidence requirement equal initial mass so a long combined
    # query cannot hide a smaller but necessary aspect.  Within one aspect,
    # BM25 scores determine the distribution.
    seed_mass: Counter[str] = Counter()
    best_seed_record: dict[str, dict[str, Any]] = {}
    for aspect in aspect_records:
        aspect_seeds = aspect_rankings.get(str(aspect["query_id"]), [])
        total = sum(max(float(seed["score"]), 0.0) for seed in aspect_seeds)
        for seed in aspect_seeds:
            chunk_id = str(seed["chunk_id"])
            contribution = (
                max(float(seed["score"]), 0.0) / total
                if total > 0.0
                else (1.0 / len(aspect_seeds) if aspect_seeds else 0.0)
            )
            seed_mass[chunk_id] += contribution / len(aspect_records)
            previous = best_seed_record.get(chunk_id)
            if previous is None or int(seed["rank"]) < int(previous["rank"]):
                best_seed_record[chunk_id] = {
                    "rank": int(seed["rank"]),
                    "score": float(seed["score"]),
                }
    if seed_mass:
        mass_total = sum(seed_mass.values())
        personalization = {
            chunk_id: mass / mass_total for chunk_id, mass in seed_mass.items()
        }
    else:
        uniform = 1.0 / len(chunks)
        personalization = {str(chunk["chunk_id"]): uniform for chunk in chunks}

    ranks = dict(personalization)
    damping = resolved["damping"]
    for _iteration in range(resolved["iterations"]):
        next_ranks = {
            node: (1.0 - damping) * personalization.get(node, 0.0)
            for node in adjacency
        }
        dangling_mass = 0.0
        for node, score in ranks.items():
            neighbours = adjacency[node]
            total_weight = sum(neighbours.values())
            if total_weight <= 0.0:
                dangling_mass += score
                continue
            for neighbour, weight in neighbours.items():
                next_ranks[neighbour] += damping * score * weight / total_weight
        if dangling_mass:
            for node, probability in personalization.items():
                next_ranks[node] += damping * dangling_mass * probability
        ranks = next_ranks

    ordered = sorted(ranks, key=lambda node: (-ranks[node], node))
    results = []
    seed_lookup = best_seed_record
    for rank, chunk_id in enumerate(ordered[: resolved["top_k"]], 1):
        chunk = source_map[chunk_id]
        results.append(
            {
                "chunk_id": chunk_id,
                "document_id": chunk.get("document_id"),
                "rank": rank,
                "score": ranks[chunk_id],
                "score_type": "personalized_pagerank",
                "lexical_seed": seed_lookup.get(chunk_id),
                "source_spans": chunk.get("source_spans", []),
            }
        )
    return results, {
        "baseline": "structure-term-graph-v0",
        "not_full_hipporag": True,
        "configuration": resolved,
        "graph": diagnostics,
        "seed_aspect_count": len(aspect_records),
        "seed_count": len(seed_lookup),
        "seed_chunk_ids": sorted(seed_lookup),
    }
