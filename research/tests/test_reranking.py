from __future__ import annotations

import pytest

from research.offline_retrieval.reranking import rerank_documents


class InjectedScorer:
    metadata = {"backend": "injected_test"}

    def __init__(self, scores):
        self.scores = scores
        self.pairs = None

    def score_pairs(self, pairs):
        self.pairs = list(pairs)
        return self.scores


def _passage(passage_id, document_id, text, start):
    return {
        "chunk_id": passage_id,
        "document_id": document_id,
        "text": text,
        "source_spans": [
            {"document_id": document_id, "raw_start": start, "raw_end": start + 5}
        ],
    }


def test_dense_reranking_preserves_tail_and_provenance():
    rankings = {
        "q": [
            {
                "document_id": "d1",
                "supporting_chunk_id": "c1",
                "score": 0.9,
                "rank": 1,
                "source_spans": [],
            },
            {
                "document_id": "d2",
                "supporting_chunk_id": "c2",
                "score": 0.8,
                "rank": 2,
                "source_spans": [],
            },
            {
                "document_id": "d3",
                "supporting_chunk_id": "c3",
                "score": 0.7,
                "rank": 3,
                "source_spans": [],
            },
        ]
    }
    passages = {
        "c1": _passage("c1", "d1", "first", 0),
        "c2": _passage("c2", "d2", "second", 5),
        "c3": _passage("c3", "d3", "tail", 10),
    }
    scorer = InjectedScorer([0.1, 0.9])

    result = rerank_documents(
        rankings,
        [{"query_id": "q", "text": "question"}],
        passages,
        scorer=scorer,
        rerank_depth=2,
        top_k=3,
        support_methods=("structure_dense",),
        default_support_method="structure_dense",
    )["q"]

    assert scorer.pairs == [("question", "first"), ("question", "second")]
    assert [item["document_id"] for item in result] == ["d2", "d1", "d3"]
    assert [item["rank"] for item in result] == [1, 2, 3]
    assert result[0]["pre_rerank_rank"] == 2
    assert result[0]["candidate_score"] == 0.8
    assert result[0]["cross_encoder_score"] == 0.9
    assert result[0]["source_spans"] == passages["c2"]["source_spans"]
    assert result[0]["cross_encoder_input"]["truncated"] is None
    assert result[0]["model_visible_source_spans"] is None
    assert "candidate_passage_origin" in result[0]["source_spans_semantics"]
    assert result[2]["score"] is None
    assert result[2]["candidate_score"] == 0.7
    assert result[2]["reranked"] is False


def test_multiview_uses_max_passage_score_and_keeps_winning_method():
    rankings = {
        "q": [
            {
                "document_id": "d1",
                "supporting_chunk_id": "b1",
                "score": 0.03,
                "rank": 1,
                "source_spans": [],
                "supports_by_method": {
                    "fixed_window_bm25": {
                        "supporting_chunk_id": "b1",
                        "source_spans": [{"document_id": "d1", "raw_start": 0, "raw_end": 5}],
                    },
                    "structure_dense": {
                        "supporting_chunk_id": "s1",
                        "source_spans": [{"document_id": "d1", "raw_start": 5, "raw_end": 10}],
                    },
                },
            },
            {
                "document_id": "d2",
                "supporting_chunk_id": "b2",
                "score": 0.02,
                "rank": 2,
                "source_spans": [],
                "supports_by_method": {
                    "fixed_window_bm25": {
                        "supporting_chunk_id": "b2",
                        "source_spans": [{"document_id": "d2", "raw_start": 0, "raw_end": 5}],
                    },
                    "structure_dense": {
                        "supporting_chunk_id": "s2",
                        "source_spans": [{"document_id": "d2", "raw_start": 5, "raw_end": 10}],
                    },
                },
            },
        ]
    }
    passages = {
        "b1": _passage("b1", "d1", "d1 lexical", 0),
        "s1": _passage("s1", "d1", "d1 semantic", 5),
        "b2": _passage("b2", "d2", "d2 lexical", 0),
        "s2": _passage("s2", "d2", "d2 semantic", 5),
    }
    # d1 wins through Dense (0.8); d2 wins through BM25 (0.7).
    scorer = InjectedScorer([0.1, 0.8, 0.7, 0.2])

    result = rerank_documents(
        rankings,
        [{"query_id": "q", "text": "query"}],
        passages,
        scorer=scorer,
        rerank_depth=2,
        top_k=2,
        support_methods=("fixed_window_bm25", "structure_dense"),
        default_support_method="multiview_hybrid_rrf",
    )["q"]

    assert [item["document_id"] for item in result] == ["d1", "d2"]
    assert result[0]["cross_encoder_support_method"] == "structure_dense"
    assert result[0]["supporting_chunk_id"] == "s1"
    assert result[1]["cross_encoder_support_method"] == "fixed_window_bm25"
    assert result[1]["supporting_chunk_id"] == "b2"
    assert len(result[0]["cross_encoder_scores_by_support"]) == 2


def test_equal_cross_encoder_scores_preserve_upstream_rank_before_ids():
    rankings = {
        "q": [
            {
                "document_id": "z-document",
                "supporting_chunk_id": "z-support",
                "score": 0.9,
                "rank": 1,
                "source_spans": [],
            },
            {
                "document_id": "a-document",
                "supporting_chunk_id": "a-support",
                "score": 0.8,
                "rank": 2,
                "source_spans": [],
            },
        ]
    }
    passages = {
        "z-support": _passage("z-support", "z-document", "first", 0),
        "a-support": _passage("a-support", "a-document", "second", 5),
    }

    result = rerank_documents(
        rankings,
        [{"query_id": "q", "text": "query"}],
        passages,
        scorer=InjectedScorer([0.5, 0.5]),
        rerank_depth=2,
        top_k=2,
        support_methods=("structure_dense",),
        default_support_method="structure_dense",
    )["q"]

    assert [item["document_id"] for item in result] == [
        "z-document",
        "a-document",
    ]
    assert [item["pre_rerank_rank"] for item in result] == [1, 2]


def test_reranking_rejects_missing_or_mismatched_support():
    rankings = {
        "q": [
            {
                "document_id": "d1",
                "supporting_chunk_id": "c1",
                "score": 1.0,
                "rank": 1,
                "source_spans": [],
            }
        ]
    }
    kwargs = {
        "candidate_rankings": rankings,
        "queries": [{"query_id": "q", "text": "query"}],
        "scorer": InjectedScorer([1.0]),
        "rerank_depth": 1,
        "top_k": 1,
        "support_methods": ("structure_dense",),
        "default_support_method": "structure_dense",
    }

    with pytest.raises(ValueError, match="Unknown support passage"):
        rerank_documents(passages={}, **kwargs)

    with pytest.raises(ValueError, match="belongs to d2"):
        rerank_documents(
            passages={"c1": _passage("c1", "d2", "wrong", 0)}, **kwargs
        )
