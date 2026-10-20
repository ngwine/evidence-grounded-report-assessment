"""Synthetic W10 regressions for conservative Pipeline 1 evidence handling."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from research.core_mvp.documents import parse_document
from research.core_mvp.similarity import run_similarity_pipeline


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "similarity_w10"
CASES = json.loads(
    (FIXTURE_DIR / "cases.json").read_text(
        encoding="utf-8"
    )
)["cases"]


def test_complete_synthetic_documents_keep_separate_retrieval_passages():
    report = parse_document(
        FIXTURE_DIR / "report.md", role="student-report", max_tokens=30, min_tokens=1
    )
    source_a = parse_document(
        FIXTURE_DIR / "source-operation.md",
        role="comparison-source",
        max_tokens=30,
        min_tokens=1,
    )
    source_b = parse_document(
        FIXTURE_DIR / "source-trials.md",
        role="comparison-source",
        max_tokens=30,
        min_tokens=1,
    )
    assert len(report.chunks) >= 5
    assert len(source_a.chunks) >= 3
    assert len(source_b.chunks) >= 2
    assert len({chunk["chunk_id"] for chunk in (*source_a.chunks, *source_b.chunks)}) == (
        len(source_a.chunks) + len(source_b.chunks)
    )


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_synthetic_case_only_counts_distinctive_exact_evidence(tmp_path, case):
    report_path = tmp_path / "report.txt"
    source_path = tmp_path / "source.txt"
    report_path.write_text(case["report"], encoding="utf-8")
    source_path.write_text(case["source"], encoding="utf-8")
    report = parse_document(
        report_path, role="student-report", max_tokens=256, min_tokens=1
    )
    source = parse_document(
        source_path, role="comparison-source", max_tokens=256, min_tokens=1
    )

    result = run_similarity_pipeline(
        report.chunks,
        source.chunks,
        config={
            "candidate_depth": 1,
            "rerank_depth": 1,
            "top_k": 1,
            "dense_enabled": False,
            "reranker_enabled": False,
        },
        encoder=None,
        reranker=None,
    )

    assert result["calibrated_similarity_percentage"] is None
    assert "plagiarism_verdict" not in result
    assert len(result["matches"]) == 1
    match = result["matches"][0]
    assert match["source_document_id"] == source.document["document_id"]
    assert match["selected_for_document_coverage"] is case[
        "expect_evidence_backed_verbatim"
    ]
    if case["expect_evidence_backed_verbatim"]:
        assert match["similarity_type"] == "VERBATIM"
        assert match["alignment"]["kind"] == "EXACT_SUBSTRING"
        assert result["exact_match_coverage_percentage"] > 0
    else:
        assert result["exact_match_coverage_percentage"] == 0
        assert result["flagged_passage_coverage_percentage"] == 0
        if match["classification_status"] == "PROVISIONAL_REVIEW_REQUIRED":
            assert match["similarity_type"] is None
