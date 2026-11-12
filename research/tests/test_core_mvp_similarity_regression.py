"""Regressions for exact evidence inside otherwise dissimilar report chunks."""

from __future__ import annotations

import pytest

from research.core_mvp.documents import parse_document, parse_documents
from research.core_mvp.similarity import run_similarity_pipeline
from research.offline_retrieval.common import tokenize


def _config() -> dict:
    return {
        "candidate_depth": 2,
        "rerank_depth": 1,
        "top_k": 2,
        "dense_enabled": False,
        "reranker_enabled": False,
        "classification": {"minimum_alignment_chars": 12},
    }


def test_long_chunk_with_substantial_copied_span_has_exact_evidence_and_span_coverage(
    tmp_path,
):
    copied = (
        "The archival checksum binds each extracted paragraph to its source page "
        "and preserves a stable offset for later evidence review."
    )
    report_text = (
        " ".join(f"leftterm{index}" for index in range(65))
        + " "
        + copied
        + " "
        + " ".join(f"rightterm{index}" for index in range(65))
    )
    report_path = tmp_path / "report.txt"
    first_source_path = tmp_path / "first-source.txt"
    second_source_path = tmp_path / "second-source.txt"
    report_path.write_text(report_text, encoding="utf-8")
    first_source_path.write_text(copied, encoding="utf-8")
    second_source_path.write_text(
        "An unrelated introduction. " + copied + " Additional unrelated notes.",
        encoding="utf-8",
    )
    report = parse_document(
        report_path, role="student-report", max_tokens=256, min_tokens=1
    )
    sources = parse_documents(
        [first_source_path, second_source_path],
        role="comparison-source",
        max_tokens=256,
        min_tokens=1,
    )
    assert len(report.chunks) == 1

    result = run_similarity_pipeline(
        report.chunks,
        [chunk for source in sources for chunk in source.chunks],
        config=_config(),
        encoder=None,
        reranker=None,
    )

    selected = [
        match for match in result["matches"] if match["selected_for_document_coverage"]
    ]
    assert len(selected) == 1  # Two sources cannot double-count one report span.
    match = selected[0]
    assert match["features"]["query_token_coverage"] < 0.3
    assert match["similarity_type"] == "VERBATIM"
    assert match["classification_status"] == "EVIDENCE_BACKED_EXACT_MATCH"
    assert match["alignment"]["kind"] == "EXACT_SUBSTRING"
    assert match["alignment"]["report"]["text"] == copied
    assert match["alignment"]["source"]["text"] == copied
    assert match["alignment"]["report"]["normalized_start"] == report_text.index(
        copied
    )
    for side in ("report", "source"):
        span = match["alignment"][side]
        assert span["source_spans"]
        assert span["source_spans"][0]["matched_chunk_normalized_start"] == span[
            "normalized_start"
        ]
        assert span["source_spans"][0]["matched_chunk_normalized_end"] == span[
            "normalized_end"
        ]
    assert result["flagged_report_tokens_unique_by_report_chunk"] == len(
        tokenize(report_text)
    )
    assert result["exact_matched_report_tokens"] == len(tokenize(copied))
    assert result["exact_match_coverage_percentage"] < result[
        "flagged_passage_coverage_percentage"
    ]
    assert sum(row["selected_report_passages"] for row in result["source_summary"]) == 1


def test_one_report_chunk_keeps_distinct_exact_spans_from_multiple_sources(tmp_path):
    first_copy = (
        "The provenance ledger binds every extracted paragraph to a stable "
        "source page and immutable document version."
    )
    second_copy = (
        "The evaluation protocol separates development tuning from the sealed "
        "test split to prevent experimental leakage."
    )
    report_text = (
        "Introductory material unique to the report. "
        + first_copy
        + " A separate section contains unrelated discussion. "
        + second_copy
        + " Closing material unique to the report."
    )
    report_path = tmp_path / "report.txt"
    first_source_path = tmp_path / "first-source.txt"
    second_source_path = tmp_path / "second-source.txt"
    report_path.write_text(report_text, encoding="utf-8")
    first_source_path.write_text(first_copy, encoding="utf-8")
    second_source_path.write_text(second_copy, encoding="utf-8")
    report = parse_document(
        report_path, role="student-report", max_tokens=256, min_tokens=1
    )
    sources = parse_documents(
        [first_source_path, second_source_path],
        role="comparison-source",
        max_tokens=256,
        min_tokens=1,
    )
    assert len(report.chunks) == 1

    result = run_similarity_pipeline(
        report.chunks,
        [chunk for source in sources for chunk in source.chunks],
        config=_config(),
        encoder=None,
        reranker=None,
    )

    selected = [
        match
        for match in result["matches"]
        if match["selected_for_document_coverage"]
    ]
    assert len(selected) == 2
    assert len({match["source_document_id"] for match in selected}) == 2
    assert {match["alignment"]["report"]["text"] for match in selected} == {
        first_copy,
        second_copy,
    }
    assert result["exact_matched_report_tokens"] == len(
        tokenize(first_copy)
    ) + len(tokenize(second_copy))
    assert sum(
        row["selected_report_passages"] for row in result["source_summary"]
    ) == 2


@pytest.mark.parametrize(
    "phrase",
    [
        "The results are shown in Table 1.",
        " ".join(["method"] * 20),
    ],
)
def test_generic_exact_phrase_needs_review_and_does_not_flag_coverage(
    tmp_path, phrase
):
    report_path = tmp_path / "report.txt"
    source_path = tmp_path / "source.txt"
    report_path.write_text(phrase, encoding="utf-8")
    source_path.write_text(phrase, encoding="utf-8")
    report = parse_document(
        report_path, role="student-report", max_tokens=256, min_tokens=1
    )
    source = parse_document(
        source_path, role="comparison-source", max_tokens=256, min_tokens=1
    )

    result = run_similarity_pipeline(
        report.chunks,
        source.chunks,
        config=_config(),
        encoder=None,
        reranker=None,
    )

    match = result["matches"][0]
    assert match["similarity_type"] is None
    assert match["provisional_similarity_type"] == "VERBATIM"
    assert match["classification_status"] == "PROVISIONAL_REVIEW_REQUIRED"
    assert match["selected_for_manual_review"] is True
    assert result["flagged_passage_coverage_percentage"] == 0.0
    assert result["exact_match_coverage_percentage"] == 0.0
