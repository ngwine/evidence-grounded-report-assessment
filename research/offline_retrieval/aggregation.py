"""Deterministic aggregation from chunk rankings to source-document rankings."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable, Mapping


ScoredItem = tuple[float, str, dict[str, Any]]


def render_ranked_candidates(
    scored: Iterable[ScoredItem],
    *,
    top_k: int,
    group_by_document: bool,
) -> list[dict[str, Any]]:
    """Render top chunks or aggregate every scored chunk to its best document.

    Aggregation happens before truncation. This prevents many chunks from one
    document crowding other source documents out of a top-k candidate list.
    """

    if top_k <= 0:
        raise ValueError("top_k must be positive")
    rows = list(scored)
    if group_by_document:
        best_by_document: dict[str, ScoredItem] = {}
        for score, chunk_id, item in rows:
            document_id = item.get("document_id")
            if not isinstance(document_id, str) or not document_id:
                raise ValueError("Every retrieval candidate requires document_id")
            previous = best_by_document.get(document_id)
            if previous is None or (-score, chunk_id) < (-previous[0], previous[1]):
                best_by_document[document_id] = (score, chunk_id, item)
        rows = sorted(
            best_by_document.values(),
            key=lambda row: (-row[0], str(row[2]["document_id"]), row[1]),
        )
        return [
            {
                "document_id": item["document_id"],
                "supporting_chunk_id": chunk_id,
                "score": score,
                "rank": rank,
                "source_spans": item.get("source_spans", []),
            }
            for rank, (score, chunk_id, item) in enumerate(rows[:top_k], 1)
        ]

    rows.sort(key=lambda row: (-row[0], row[1]))
    return [
        {
            "chunk_id": chunk_id,
            "document_id": item["document_id"],
            "score": score,
            "rank": rank,
            "source_spans": item.get("source_spans", []),
        }
        for rank, (score, chunk_id, item) in enumerate(rows[:top_k], 1)
    ]


def collapse_to_documents(
    rankings: Mapping[str, list[dict[str, Any]]],
    *,
    top_k: int,
) -> dict[str, list[dict[str, Any]]]:
    """Keep the best-ranked chunk per document and re-rank documents.

    Retrieval methods still operate over chunks. Source-retrieval metrics must
    not reward or penalize a document multiple times merely because it produced
    several high-scoring chunks, so the first (best) chunk is retained as
    provenance and every document appears at most once.
    """

    if top_k <= 0:
        raise ValueError("top_k must be positive")

    collapsed: dict[str, list[dict[str, Any]]] = {}
    for query_id, candidates in sorted(rankings.items()):
        seen_documents: set[str] = set()
        documents: list[dict[str, Any]] = []
        for candidate in candidates:
            document_id = candidate.get("document_id")
            if not isinstance(document_id, str) or not document_id:
                raise ValueError("Every retrieval candidate requires document_id")
            if document_id in seen_documents:
                continue
            seen_documents.add(document_id)
            record = deepcopy(candidate)
            record["supporting_chunk_id"] = record.pop("chunk_id")
            record["rank"] = len(documents) + 1
            documents.append(record)
            if len(documents) == top_k:
                break
        collapsed[query_id] = documents
    return collapsed
