"""Retrieval relevance cannot establish paraphrase or summary relations."""

from copy import deepcopy

import pytest

from research.core_mvp.similarity import run_similarity_pipeline


class TopicalEncoder:
    metadata = {"test_double": True}

    def encode(self, texts):
        return [[1.0, 0.0] for _ in texts]


class TopicalScorer:
    metadata = {"test_double": True}

    def score_pairs(self, pairs):
        return [8.0 for _ in pairs]


SOURCE = (
    "Sudoku can be represented as a constraint satisfaction problem. Each cell "
    "is a variable with a domain of nine digits. Rows and columns impose "
    "all-different constraints. A general solver propagates constraints to "
    "prune the domains before searching for an assignment. This representation "
    "does not prescribe the implementation language or the user interface."
)
CONFIG = {
    "candidate_depth": 1,
    "rerank_depth": 1,
    "top_k": 1,
    "dense_enabled": True,
    "reranker_enabled": True,
}


def chunk(identifier, document, text):
    return {
        "chunk_id": identifier,
        "document_id": document,
        "text": text,
        "normalized_text": text,
    }


def run(reports, config=None):
    return run_similarity_pipeline(
        reports,
        [chunk("source-cell-model", "textbook", SOURCE)],
        config=config or CONFIG,
        encoder=TopicalEncoder(),
        reranker=TopicalScorer(),
    )


@pytest.mark.parametrize("text", [
    "Sudoku illustration. Contributions: Lin built the interface; An wrote the report.",
    "Our Sudoku implementation uses Boolean literals and a SAT backend, not cell domains.",
    "Our Sudoku project offers an interactive interface. " * 8,
])
def test_high_relevance_never_assigns_a_semantic_relation(text):
    result = run([chunk("report-example", "report", text)])
    [match] = result["matches"]
    assert match["selected_for_manual_review"] is True
    assert match["similarity_type"] is None
    assert match["provisional_similarity_type"] is None
    assert match["semantic_verification_status"] == "NOT_RUN"
    assert "semantic_relation_not_verified" in match["classification_reasons"]
    assert result["flagged_passage_coverage_percentage"] == 0
    assert result["exact_match_coverage_percentage"] == 0
    assert result["calibrated_similarity_percentage"] is None


def test_length_threshold_cannot_turn_a_related_candidate_into_a_summary():
    reports = [chunk("report-example", "report", "Sudoku solver uses Boolean literals.")]
    for threshold in (0, 1):
        config = deepcopy(CONFIG)
        config["classification"] = {"summary_length_ratio": threshold}
        result = run(reports, config)
        assert result["matches"][0]["provisional_similarity_type"] is None


def test_repeated_source_candidates_are_grouped_without_dropping_pairs():
    reports = [
        chunk("report-b", "report", "Sudoku software uses Boolean literals and a SAT backend."),
        chunk("report-a", "report", "Sudoku illustration. Contributions: Lin built the interface."),
        chunk("report-c", "report", "The Sudoku display presents the computed solution to the user."),
    ]
    result = run(reports)
    selected = [m for m in result["matches"] if m["selected_for_manual_review"]]
    assert len(selected) == 3
    [group] = result["review_source_groups"]
    assert group["report_chunk_ids"] == ["report-a", "report-b", "report-c"]
    assert group["report_chunk_count"] == 3
    assert group["warning"] == "REPEATED_SOURCE_CHUNK_NOT_INDEPENDENT_EVIDENCE"
    assert {m["review_group_id"] for m in selected} == {group["group_id"]}
    assert result["provisional_review_report_chunks"] == 3
    assert result["provisional_review_passage_coverage_percentage"] == 100
    assert result["coverage_definitions"]["provisional_review"]["is_similarity_percentage"] is False
    assert result["review_source_groups"] == run(list(reversed(reports)))["review_source_groups"]


def test_exact_reuse_remains_confirmed_even_with_repeated_source():
    copied = "A distinctive experiment records solver latency and validates every original puzzle clue."
    result = run_similarity_pipeline(
        [chunk("a", "report", copied), chunk("b", "report", copied)],
        [chunk("source", "reference", copied)],
        config={**CONFIG, "dense_enabled": False, "reranker_enabled": False},
        encoder=None,
        reranker=None,
    )
    assert len([m for m in result["matches"] if m["selected_for_document_coverage"]]) == 2
    assert result["exact_match_coverage_percentage"] == 100
    assert result["review_source_groups"] == []
