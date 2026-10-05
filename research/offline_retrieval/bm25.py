"""Small deterministic Okapi BM25 baseline with no service dependency."""

from __future__ import annotations

from collections import Counter, defaultdict
import math
from typing import Any, Iterable

from .aggregation import render_ranked_candidates
from .common import tokenize


def rank_bm25(
    corpus: Iterable[dict[str, Any]],
    queries: Iterable[dict[str, Any]],
    *,
    top_k: int,
    k1: float = 1.2,
    b: float = 0.75,
    group_by_document: bool = False,
) -> dict[str, list[dict[str, Any]]]:
    if top_k <= 0:
        raise ValueError("top_k must be positive")
    if k1 <= 0 or not 0 <= b <= 1:
        raise ValueError("BM25 requires k1 > 0 and b in [0, 1]")

    items = list(corpus)
    if not items:
        return {str(query["query_id"]): [] for query in queries}

    document_lengths: list[int] = []
    postings: dict[str, list[tuple[int, int]]] = defaultdict(list)
    seen_ids: set[str] = set()
    for item in items:
        chunk_id = item.get("chunk_id")
        text = item.get("text")
        if not isinstance(chunk_id, str) or not chunk_id:
            raise ValueError("Every corpus item requires a non-empty chunk_id")
        if chunk_id in seen_ids:
            raise ValueError(f"Duplicate chunk_id: {chunk_id}")
        seen_ids.add(chunk_id)
        if not isinstance(text, str):
            raise ValueError(f"Corpus item {chunk_id} requires string text")
        tokens = tokenize(text)
        counts = Counter(tokens)
        document_lengths.append(len(tokens))
        for term, frequency in counts.items():
            postings[term].append((len(document_lengths) - 1, frequency))

    average_length = sum(document_lengths) / len(items)
    average_length = average_length or 1.0
    corpus_size = len(items)

    results: dict[str, list[dict[str, Any]]] = {}
    seen_query_ids: set[str] = set()
    for query in queries:
        query_id = query.get("query_id")
        query_text = query.get("text")
        if not isinstance(query_id, str) or not query_id:
            raise ValueError("Every query requires a non-empty query_id")
        if query_id in seen_query_ids:
            raise ValueError(f"Duplicate query_id: {query_id}")
        seen_query_ids.add(query_id)
        if not isinstance(query_text, str):
            raise ValueError(f"Query {query_id} requires string text")

        query_terms = Counter(tokenize(query_text))
        scores: dict[int, float] = defaultdict(float)
        for term, query_frequency in query_terms.items():
            term_postings = postings.get(term)
            if not term_postings:
                continue
            document_frequency = len(term_postings)
            inverse_document_frequency = math.log(
                1
                + (corpus_size - document_frequency + 0.5)
                / (document_frequency + 0.5)
            )
            for item_index, frequency in term_postings:
                document_length = document_lengths[item_index]
                denominator = frequency + k1 * (
                    1 - b + b * document_length / average_length
                )
                scores[item_index] += query_frequency * inverse_document_frequency * (
                    frequency * (k1 + 1) / denominator
                )

        # A non-match has no retrieval evidence. Omitting zero-score chunks also
        # avoids arbitrary chunk-id tie breaks filling a requested top-k.
        scored = [
            (score, items[item_index]["chunk_id"], items[item_index])
            for item_index, score in scores.items()
            if score > 0.0
        ]

        results[query_id] = render_ranked_candidates(
            scored,
            top_k=top_k,
            group_by_document=group_by_document,
        )
    return results
