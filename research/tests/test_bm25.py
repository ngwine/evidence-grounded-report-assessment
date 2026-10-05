"""Focused regression tests for the deterministic inverted-index BM25."""

from __future__ import annotations

import math

import pytest

from research.offline_retrieval.bm25 import rank_bm25


def _chunk(chunk_id: str, document_id: str, text: str) -> dict[str, object]:
    return {
        "chunk_id": chunk_id,
        "document_id": document_id,
        "text": text,
        "source_spans": [],
    }


def test_bm25_ranking_and_scores_follow_okapi_formula():
    corpus = [
        _chunk("c1", "d1", "alpha alpha beta"),
        _chunk("c2", "d2", "alpha gamma"),
        _chunk("c3", "d3", "delta"),
    ]

    ranking = rank_bm25(
        corpus,
        [{"query_id": "q", "text": "alpha alpha"}],
        top_k=3,
        k1=1.2,
        b=0.75,
    )["q"]

    # N=3, df(alpha)=2, average document length=2. Query term frequency is 2.
    idf = math.log(1 + (3 - 2 + 0.5) / (2 + 0.5))
    expected_c1 = 2 * idf * (2 * (1.2 + 1)) / (
        2 + 1.2 * (1 - 0.75 + 0.75 * 3 / 2)
    )
    expected_c2 = 2 * idf * (1 * (1.2 + 1)) / (
        1 + 1.2 * (1 - 0.75 + 0.75 * 2 / 2)
    )

    assert [candidate["chunk_id"] for candidate in ranking] == ["c1", "c2"]
    assert ranking[0]["score"] == pytest.approx(expected_c1)
    assert ranking[1]["score"] == pytest.approx(expected_c2)


def test_bm25_document_grouping_is_deterministic_across_corpus_order():
    corpus = [
        _chunk("d1-b", "d1", "alpha"),
        _chunk("d2-a", "d2", "alpha"),
        _chunk("d1-a", "d1", "alpha"),
    ]
    query = [{"query_id": "q", "text": "alpha"}]

    first = rank_bm25(corpus, query, top_k=2, group_by_document=True)["q"]
    second = rank_bm25(
        list(reversed(corpus)), query, top_k=2, group_by_document=True
    )["q"]

    assert first == second
    assert [candidate["document_id"] for candidate in first] == ["d1", "d2"]
    assert first[0]["supporting_chunk_id"] == "d1-a"


def test_bm25_omits_zero_match_candidates_instead_of_filling_top_k():
    corpus = [
        _chunk("matching", "d1", "alpha"),
        _chunk("unrelated-a", "d2", "beta"),
        _chunk("unrelated-b", "d3", "gamma"),
    ]
    queries = [
        {"query_id": "partial", "text": "alpha missing"},
        {"query_id": "none", "text": "missing"},
    ]

    rankings = rank_bm25(corpus, queries, top_k=10)

    assert [candidate["chunk_id"] for candidate in rankings["partial"]] == [
        "matching"
    ]
    assert rankings["none"] == []
