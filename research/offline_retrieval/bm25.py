"""Small deterministic Okapi BM25 baseline with no service dependency."""

from __future__ import annotations

from collections import Counter, defaultdict
import math
from typing import Any, Iterable

from .common import tokenize


def rank_bm25(
    corpus: Iterable[dict[str, Any]],
    queries: Iterable[dict[str, Any]],
    *,
    top_k: int,
    k1: float = 1.2,
    b: float = 0.75,
) -> dict[str, list[dict[str, Any]]]:
    if top_k <= 0:
        raise ValueError("top_k must be positive")
    if k1 <= 0 or not 0 <= b <= 1:
        raise ValueError("BM25 requires k1 > 0 and b in [0, 1]")

    items = list(corpus)
    if not items:
        return {str(query["query_id"]): [] for query in queries}

    tokenized: list[list[str]] = []
    term_frequencies: list[Counter[str]] = []
    document_frequency: dict[str, int] = defaultdict(int)
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
        tokenized.append(tokens)
        term_frequencies.append(counts)
        for term in counts:
            document_frequency[term] += 1

    average_length = sum(len(tokens) for tokens in tokenized) / len(items)
    average_length = average_length or 1.0
    corpus_size = len(items)
    idf = {
        term: math.log(1 + (corpus_size - frequency + 0.5) / (frequency + 0.5))
        for term, frequency in document_frequency.items()
    }

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
        scored: list[tuple[float, str, dict[str, Any]]] = []
        for item, tokens, frequencies in zip(items, tokenized, term_frequencies):
            document_length = len(tokens)
            score = 0.0
            for term, query_frequency in query_terms.items():
                frequency = frequencies.get(term, 0)
                if not frequency:
                    continue
                denominator = frequency + k1 * (
                    1 - b + b * document_length / average_length
                )
                score += query_frequency * idf.get(term, 0.0) * (
                    frequency * (k1 + 1) / denominator
                )
            scored.append((score, item["chunk_id"], item))

        scored.sort(key=lambda row: (-row[0], row[1]))
        results[query_id] = [
            {
                "chunk_id": chunk_id,
                "document_id": item["document_id"],
                "score": score,
                "rank": rank,
                "source_spans": item.get("source_spans", []),
            }
            for rank, (score, chunk_id, item) in enumerate(scored[:top_k], 1)
        ]
    return results
