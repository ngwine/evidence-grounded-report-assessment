"""Contract tests for the deterministic Pipeline 2 graph baseline."""

from __future__ import annotations

import pytest

from research.core_mvp.graph import rank_graph, validate_graph_config


CONFIG = {
    "top_k": 3,
    "seed_depth": 3,
    "iterations": 20,
    "damping": 0.85,
    "minimum_shared_terms": 1,
    "maximum_term_degree": 10,
}


def _chunks() -> list[dict]:
    return [
        {
            "chunk_id": "report-v1-c1",
            "document_id": "report-v1",
            "document_version_id": "version-v1",
            "chunk_index": 0,
            "text": "The system uses BM25 retrieval for source passages.",
            "source_spans": [{"page": 1, "raw_start": 0, "raw_end": 58}],
        },
        {
            "chunk_id": "report-v1-c2",
            "document_id": "report-v1",
            "document_version_id": "version-v1",
            "chunk_index": 1,
            "text": "Retrieved passages preserve evidence provenance and page spans.",
            "source_spans": [{"page": 1, "raw_start": 59, "raw_end": 124}],
        },
        {
            "chunk_id": "report-v1-c3",
            "document_id": "report-v1",
            "document_version_id": "version-v1",
            "chunk_index": 2,
            "text": "The final result links each claim to its evidence source.",
            "source_spans": [{"page": 2, "raw_start": 0, "raw_end": 58}],
        },
    ]


def test_graph_ranking_is_deterministic_and_preserves_source_spans():
    kwargs = {
        "query_id": "TRACE.GRAPH.1",
        "query_text": "result evidence source",
        "config": CONFIG,
        "seed_queries": ["result claim", "evidence provenance"],
    }
    first, first_diagnostics = rank_graph(_chunks(), **kwargs)
    second, second_diagnostics = rank_graph(_chunks(), **kwargs)

    assert first == second
    assert first_diagnostics == second_diagnostics
    assert [item["rank"] for item in first] == [1, 2, 3]
    assert all(item["source_spans"] for item in first)
    assert first_diagnostics["baseline"] == "structure-term-graph-v0"
    assert first_diagnostics["not_full_hipporag"] is True
    assert first_diagnostics["seed_aspect_count"] == 2


def test_graph_rejects_duplicate_chunk_ids():
    chunks = _chunks()
    chunks[1]["chunk_id"] = chunks[0]["chunk_id"]

    with pytest.raises(ValueError, match="unique chunk_id"):
        rank_graph(
            chunks,
            query_id="q1",
            query_text="evidence",
            config=CONFIG,
        )


@pytest.mark.parametrize(
    "override",
    [
        {"top_k": 0},
        {"iterations": -1},
        {"damping": 1.1},
        {"damping": True},
        {"minimum_shared_terms": 0},
    ],
)
def test_graph_config_rejects_invalid_values(override):
    with pytest.raises(ValueError):
        validate_graph_config({**CONFIG, **override})
