"""Tests for the executable two-pipeline core MVP."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from research.core_mvp.assessment import run_assessment_pipeline
from research.core_mvp.documents import parse_document, parse_documents
from research.core_mvp.rubric import compile_rubric
from research.core_mvp.runner import run_core_mvp
from research.core_mvp.similarity import run_similarity_pipeline


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "core_mvp"


def _read(name: str):
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def test_text_ingestion_is_deterministic_and_keeps_raw_mapping():
    first = parse_document(
        FIXTURE_DIR / "report.txt", role="student-report", max_tokens=40, min_tokens=1
    )
    second = parse_document(
        FIXTURE_DIR / "report.txt", role="student-report", max_tokens=40, min_tokens=1
    )

    assert first == second
    assert len(first.chunks) >= 4
    assert len({chunk["chunk_id"] for chunk in first.chunks}) == len(first.chunks)
    for chunk in first.chunks:
        assert chunk["source_spans"]
        assert len(chunk["normalization_map"]["normalized_char_to_raw_span"]) == len(
            chunk["normalized_text"]
        )


def test_rubric_compiler_is_stable_and_rejects_non_atomic_graph_item():
    rubric = _read("rubric.json")
    assert compile_rubric(rubric) == compile_rubric(rubric)

    invalid = json.loads(json.dumps(rubric))
    invalid["criteria"][0]["checklists"][1]["requirements"] = [
        invalid["criteria"][0]["checklists"][1]["requirements"][0]
    ]
    with pytest.raises(ValueError, match="GRAPH checklist requires"):
        compile_rubric(invalid)


def test_pipeline1_finds_verbatim_match_and_exact_spans():
    report = parse_document(
        FIXTURE_DIR / "report.txt", role="student-report", max_tokens=40, min_tokens=1
    )
    sources = parse_documents(
        [FIXTURE_DIR / "source-overlap.txt", FIXTURE_DIR / "source-unrelated.txt"],
        role="comparison-source",
        max_tokens=40,
        min_tokens=1,
    )
    config = _read("config-bm25-only.json")["pipeline1"]

    result = run_similarity_pipeline(
        report.chunks,
        [chunk for source in sources for chunk in source.chunks],
        config=config,
        encoder=None,
        reranker=None,
    )

    selected = [item for item in result["matches"] if item["selected_for_document_coverage"]]
    assert any(item["similarity_type"] == "VERBATIM" for item in selected)
    verbatim = next(item for item in selected if item["similarity_type"] == "VERBATIM")
    assert verbatim["alignment"]["kind"] == "EXACT_SUBSTRING"
    assert verbatim["alignment"]["source"]["source_spans"]
    assert 0 < result["flagged_passage_coverage_percentage"] <= 100
    assert result["exact_match_coverage_percentage"] > 0
    assert result["calibrated_similarity_percentage"] is None


def _plain_chunk(chunk_id: str, document_id: str, text: str) -> dict:
    return {
        "chunk_id": chunk_id,
        "document_id": document_id,
        "text": text,
        "normalized_text": text,
    }


def test_pipeline1_keeps_topical_semantic_hits_for_review_without_flagging_coverage():
    class TopicalEncoder:
        metadata = {"test_double": True}

        def encode(self, texts):
            return [[1.0, 0.0] for _text in texts]

    class TopicalScorer:
        metadata = {"test_double": True}

        def score_pairs(self, pairs):
            return [5.0 for _pair in pairs]

    report = _plain_chunk(
        "report-sudoku",
        "report",
        "Sudoku is solved using Boolean variables and Glucose3 SAT clauses "
        "to encode exactly one digit in each cell.",
    )
    source = _plain_chunk(
        "source-sudoku",
        "source",
        "A Sudoku puzzle is a constraint satisfaction problem with 81 "
        "multi-valued variables and Alldiff constraints for rows and columns.",
    )
    config = _read("config-bm25-only.json")["pipeline1"]
    config.update(
        {
            "candidate_depth": 1,
            "rerank_depth": 1,
            "top_k": 1,
            "dense_enabled": True,
            "reranker_enabled": True,
        }
    )

    result = run_similarity_pipeline(
        [report],
        [source],
        config=config,
        encoder=TopicalEncoder(),
        reranker=TopicalScorer(),
    )

    match = result["matches"][0]
    assert match["similarity_type"] is None
    assert match["provisional_similarity_type"] is None
    assert match["semantic_verification_status"] == "NOT_RUN"
    assert match["classification_status"] == "PROVISIONAL_REVIEW_REQUIRED"
    assert match["selected_for_manual_review"] is True
    assert match["selected_for_document_coverage"] is False
    assert result["flagged_passage_coverage_percentage"] == 0.0
    assert result["provisional_review_report_chunks"] == 1
    assert result["provisional_review_passage_coverage_percentage"] == 100.0


def test_pipeline1_does_not_cap_genuine_reuse_of_the_same_source_chunk():
    copied = (
        "The exact and distinctive passage about the solver is repeated "
        "in two separate parts of this report."
    )
    reports = [
        _plain_chunk("report-1", "report", copied),
        _plain_chunk("report-2", "report", copied),
    ]
    source = _plain_chunk("source-1", "source", copied)
    result = run_similarity_pipeline(
        reports,
        [source],
        config=_read("config-bm25-only.json")["pipeline1"],
        encoder=None,
        reranker=None,
    )

    selected = [
        match for match in result["matches"] if match["selected_for_document_coverage"]
    ]
    assert len(selected) == 2
    assert {match["source_chunk_id"] for match in selected} == {"source-1"}
    assert result["source_summary"][0]["selected_report_passages"] == 2
    assert result["flagged_passage_coverage_percentage"] == 100.0


def test_pipeline2_separates_supported_contradicted_and_graph_evidence():
    report = parse_document(
        FIXTURE_DIR / "report.txt", role="student-report", max_tokens=40, min_tokens=1
    )
    result = run_assessment_pipeline(
        report.chunks,
        _read("rubric.json"),
        config=_read("config-bm25-only.json")["pipeline2"],
        encoder=None,
        reranker=None,
    )
    by_id = {item["checklist_id"]: item for item in result["checklist_results"]}

    assert by_id["C1.1"]["verification_relation"] == "SUPPORTED"
    assert by_id["C1.1"]["checklist_outcome"] == "MET"
    assert by_id["C1.2"]["mode"] == "GRAPH"
    assert by_id["C1.2"]["checklist_outcome"] == "MET"
    graph_evidence_ids = {
        hit["evidence_id"]
        for requirement in by_id["C1.2"]["requirement_results"]
        for hit in requirement["hits"]
    }
    assert len(graph_evidence_ids) >= 2
    assert (
        by_id["C1.2"]["retrieval"]["graph_diagnostics"]["seed_aspect_count"]
        == 3
    )
    assert by_id["C2.1"]["verification_relation"] == "CONTRADICTED"
    assert by_id["C2.1"]["checklist_outcome"] == "UNMET"
    assert by_id["C2.1"]["contradiction_hits"][0]["span"]["source_spans"]


def test_missing_evidence_abstains_instead_of_marking_unmet():
    report = parse_document(
        FIXTURE_DIR / "report.txt", role="student-report", max_tokens=40, min_tokens=1
    )
    rubric = _read("rubric.json")
    checklist = rubric["criteria"][1]["checklists"][0]
    checklist["requirements"][0]["any_of"] = ["quantum cryptography deployment"]
    checklist["contradiction_patterns"] = []

    result = run_assessment_pipeline(
        report.chunks,
        rubric,
        config=_read("config-bm25-only.json")["pipeline2"],
        encoder=None,
        reranker=None,
    )
    item = next(
        value for value in result["checklist_results"] if value["checklist_id"] == "C2.1"
    )
    assert item["verification_relation"] == "INSUFFICIENT"
    assert item["checklist_outcome"] == "CANNOT_ASSESS"


def test_two_pipeline_runner_writes_reports_and_reproducibility_manifest(tmp_path):
    result = run_core_mvp(
        report_path=FIXTURE_DIR / "report.txt",
        source_paths=[
            FIXTURE_DIR / "source-overlap.txt",
            FIXTURE_DIR / "source-unrelated.txt",
        ],
        rubric_path=FIXTURE_DIR / "rubric.json",
        config_path=FIXTURE_DIR / "config-bm25-only.json",
        output_dir=tmp_path,
        pipeline="both",
    )

    assert set(result["output_paths"]) == {
        "similarity_report",
        "assessment_report",
        "summary",
        "run_manifest",
    }
    for path in result["output_paths"].values():
        assert Path(path).is_file()
    manifest = json.loads((tmp_path / "run-manifest.json").read_text(encoding="utf-8"))
    assert manifest["classification"] == "FEASIBILITY_RUN_NOT_FINAL_RESEARCH_RESULT"
    assert manifest["inputs"]["report"]["source_name"] == "report.txt"
    assert manifest["inputs"]["governance"]["production_indexing_allowed"] is False
    assert (
        result["summary"]["pipeline1"]["flagged_passage_coverage_percentage"]
        > 0
    )
