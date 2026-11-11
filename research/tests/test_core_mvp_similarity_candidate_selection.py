"""Focused regressions for opt-in candidate diversity in Pipeline 1."""

from __future__ import annotations

from copy import deepcopy

import pytest

from research.core_mvp import similarity
from research.offline_retrieval.rrf import fuse_rrf


SOURCE_IDS = {
    "a1": "source-a",
    "a2": "source-a",
    "a3": "source-a",
    "b1": "source-b",
    "c1": "source-c",
    "d1": "source-d",
}


def _ranking(chunk_ids: list[str]) -> list[dict]:
    return [
        {
            "chunk_id": chunk_id,
            "document_id": SOURCE_IDS[chunk_id],
            "rank": rank,
            "score": float(len(chunk_ids) - rank + 1),
            "source_spans": [],
        }
        for rank, chunk_id in enumerate(chunk_ids, 1)
    ]


def _methods() -> dict:
    # c1 is Dense's best candidate but falls below the RRF top three because
    # the three source-a chunks have support from both retrieval methods.
    return {
        "bm25": {"q": _ranking(["a1", "a2", "a3", "b1"])},
        "dense": {"q": _ranking(["c1", "a1", "a2", "a3"])},
    }


def test_quota_union_rescues_dense_only_passage_and_keeps_two_from_one_source():
    methods = _methods()
    original = deepcopy(methods)
    fused = fuse_rrf(methods, rrf_k=60, top_k=len(SOURCE_IDS))
    assert [item["chunk_id"] for item in fused["q"][:3]] == ["a1", "a2", "a3"]

    selected = similarity._select_candidate_pool(
        fused,
        methods,
        candidate_depth=4,
        rerank_depth=3,
        candidate_selection="quota_union",
        candidate_quotas={"bm25": 2, "dense": 1},
        evidence_budget_per_source=2,
    )

    assert [item["chunk_id"] for item in selected["q"]] == [
        "a1", "a2", "c1", "b1"
    ]
    assert selected["q"][2]["global_preselection_rank"] == 4
    assert selected["q"][2]["candidate_selection_reasons"] == ["dense_quota"]
    assert [item["document_id"] for item in selected["q"][:3]].count(
        "source-a"
    ) == 2
    assert methods == original  # Selection cannot mutate retrieval evidence.
    assert selected == similarity._select_candidate_pool(
        fused,
        methods,
        candidate_depth=4,
        rerank_depth=3,
        candidate_selection="quota_union",
        candidate_quotas={"bm25": 2, "dense": 1},
        evidence_budget_per_source=2,
    )


def test_source_budget_limits_candidate_monopoly_but_can_fill_from_other_source():
    methods = _methods()
    fused = fuse_rrf(methods, rrf_k=60, top_k=len(SOURCE_IDS))

    selected = similarity._select_candidate_pool(
        fused,
        methods,
        candidate_depth=4,
        rerank_depth=3,
        candidate_selection="quota_union",
        candidate_quotas={"bm25": 2, "dense": 1},
        evidence_budget_per_source=1,
    )["q"]

    assert [item["chunk_id"] for item in selected] == ["a1", "c1", "b1"]
    assert len({item["document_id"] for item in selected}) == len(selected)

    # A source budget can also be enabled without changing the legacy RRF
    # candidate-selection strategy.
    budget_only = similarity._select_candidate_pool(
        fused,
        methods,
        candidate_depth=4,
        rerank_depth=3,
        candidate_selection="rrf",
        candidate_quotas=None,
        evidence_budget_per_source=1,
    )["q"]
    assert [item["chunk_id"] for item in budget_only] == ["a1", "c1", "b1"]


def test_bm25_only_budget_refills_from_beyond_initial_candidate_depth():
    report_chunks = [
        {
            "chunk_id": "q",
            "document_id": "report",
            "text": "alpha beta gamma delta epsilon zeta",
        }
    ]
    source_chunks = [
        {
            "chunk_id": chunk_id,
            "document_id": "source-a",
            "text": "alpha beta gamma delta epsilon zeta",
        }
        for chunk_id in ("a1", "a2", "a3")
    ] + [
        {
            "chunk_id": "b1",
            "document_id": "source-b",
            "text": "alpha beta gamma",
        }
    ]
    result = similarity.run_similarity_pipeline(
        report_chunks,
        source_chunks,
        config={
            "candidate_depth": 3,
            "rerank_depth": 2,
            "top_k": 2,
            "dense_enabled": False,
            "reranker_enabled": False,
            "evidence_budget_per_source": 1,
        },
        encoder=None,
        reranker=None,
    )
    assert [item["source_chunk_id"] for item in result["matches"]] == [
        "a1", "b1"
    ]
    assert result["matches"][1]["global_preselection_rank"] == 4
    assert "global_rrf_rank" not in result["matches"][1]


def test_quota_overlap_and_unmet_budget_never_overfill_reranker_head():
    methods = {
        "bm25": {"q": _ranking(["a1", "a2", "a3"])},
        "dense": {"q": _ranking(["a1", "a2", "c1", "d1", "b1"])},
    }
    fused = fuse_rrf(methods, rrf_k=60, top_k=len(SOURCE_IDS))
    expected = similarity._select_candidate_pool(
        fused,
        methods,
        candidate_depth=4,
        rerank_depth=3,
        candidate_selection="quota_union",
        candidate_quotas={"bm25": 2, "dense": 1},
        evidence_budget_per_source=1,
    )["q"]
    assert [item["chunk_id"] for item in expected] == ["a1", "c1", "d1", "b1"]
    assert expected[3]["rank"] == 4
    assert expected[3]["candidate_selection_reasons"] == ["rrf_fill"]
    # The bm25 quota is unfillable under this cap, but no reserved item leaks
    # into the tail past rerank_depth=3.
    assert all(
        item["rank"] <= 3
        for item in expected
        if item["candidate_selection_reasons"] != ["rrf_fill"]
    )
    assert expected == similarity._select_candidate_pool(
        fused,
        methods,
        candidate_depth=4,
        rerank_depth=3,
        candidate_selection="quota_union",
        candidate_quotas={"bm25": 2, "dense": 1},
        evidence_budget_per_source=1,
    )["q"]


class _UnusedEncoder:
    metadata = {"test_double": True}

    def encode(self, texts):  # pragma: no cover - rankings are injected below.
        raise AssertionError("rank_dense is patched for this focused test")


class _IdScorer:
    metadata = {"test_double": True}

    def score_pairs(self, pairs):
        scores = {"a1": 90.0, "a2": 80.0, "a3": 70.0, "b1": 50.0, "c1": 100.0}
        return [scores[passage] for _query, passage in pairs]


def test_pipeline_reports_multiple_passages_from_one_source_and_quota_diagnostics(
    monkeypatch,
):
    methods = _methods()
    monkeypatch.setattr(similarity, "rank_bm25", lambda *_args, **_kwargs: methods["bm25"])
    monkeypatch.setattr(similarity, "rank_dense", lambda *_args, **_kwargs: methods["dense"])
    report_chunks = [
        {"chunk_id": "q", "document_id": "report", "text": "Query passage for ranking"}
    ]
    source_chunks = [
        {"chunk_id": chunk_id, "document_id": document_id, "text": chunk_id}
        for chunk_id, document_id in SOURCE_IDS.items()
    ]
    base_config = {
        "candidate_depth": 4,
        "rerank_depth": 3,
        "top_k": 3,
        "dense_enabled": True,
        "reranker_enabled": True,
    }
    baseline = similarity.run_similarity_pipeline(
        report_chunks,
        source_chunks,
        config=base_config,
        encoder=_UnusedEncoder(),
        reranker=_IdScorer(),
    )
    assert "c1" not in [item["source_chunk_id"] for item in baseline["matches"]]

    result = similarity.run_similarity_pipeline(
        report_chunks,
        source_chunks,
        config={
            **base_config,
            "candidate_selection": "quota_union",
            "candidate_quotas": {"bm25": 2, "dense": 1},
            "evidence_budget_per_source": 2,
        },
        encoder=_UnusedEncoder(),
        reranker=_IdScorer(),
    )
    assert [item["source_chunk_id"] for item in result["matches"]] == [
        "c1", "a1", "a2"
    ]
    assert [item["source_document_id"] for item in result["matches"]].count(
        "source-a"
    ) == 2
    assert result["matches"][0]["global_rrf_rank"] == 4
    assert result["matches"][0]["candidate_selection_reasons"] == ["dense_quota"]
    # Candidate diversity never turns topical relevance into proven reuse.
    assert result["calibrated_similarity_percentage"] is None


@pytest.mark.parametrize(
    "override, expected",
    [
        ({"candidate_selection": "unknown"}, "candidate_selection"),
        ({"candidate_selection": []}, "candidate_selection"),
        ({"candidate_selection": "quota_union"}, "candidate_quotas"),
        (
            {"candidate_selection": "quota_union", "candidate_quotas": {"bm25": 2, "dense": 2}},
            "rerank_depth",
        ),
        (
            {
                "candidate_selection": "quota_union",
                "candidate_quotas": {"bm25": 1, "dense": 1},
                "reranker_enabled": False,
            },
            "requires Dense retrieval and reranking",
        ),
        ({"evidence_budget_per_source": 0}, "evidence_budget_per_source"),
        ({"evidence_budget_per_source": True}, "evidence_budget_per_source"),
        (
            {
                "candidate_selection": "quota_union",
                "candidate_quotas": {"bm25": True, "dense": 1},
            },
            "candidate_quotas.bm25",
        ),
    ],
)
def test_candidate_selection_rejects_invalid_configuration(override, expected):
    config = {"candidate_depth": 3, "rerank_depth": 3, "top_k": 2}
    with pytest.raises(ValueError, match=expected):
        similarity.validate_similarity_config({**config, **override})
