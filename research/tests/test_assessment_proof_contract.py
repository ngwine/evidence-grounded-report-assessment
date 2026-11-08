"""Reject unsupported or detached assessment proof at the output boundary."""

from copy import deepcopy

import pytest

from research.core_mvp.assessment import run_assessment_pipeline
from research.core_mvp.contracts import validate_assessment_report
from research.core_mvp.documents import parse_document
from research.schema_validation import validate_json_schema


CONFIG = {
    "candidate_depth": 3, "rerank_depth": 3, "top_k": 3,
    "dense_enabled": False, "reranker_enabled": False,
}
RUBRIC = {
    "schema_version": 1, "rubric_id": "proof-contract-fixture", "version": "1",
    "max_score": 10,
    "criteria": [{
        "criterion_id": "C1", "title": "Method", "weight": 10,
        "checklists": [{
            "checklist_id": "C1.1", "statement": "The report uses BM25.",
            "mode": "LOCAL", "importance": "REQUIRED",
            "requirements": [{"requirement_id": "method", "any_of": ["BM25"]}],
            "contradiction_patterns": ["Retrieval was disabled"],
        }],
    }],
}


def _report(tmp_path, text="We used BM25 for retrieval."):
    path = tmp_path / "report.txt"
    path.write_text(text, encoding="utf-8")
    chunks = parse_document(path, role="student-report", min_tokens=1).chunks
    return run_assessment_pipeline(
        chunks, RUBRIC, config=CONFIG, encoder=None, reranker=None,
    )


@pytest.mark.parametrize(("text", "outcome"), [
    ("We used BM25 for retrieval.", "MET"),
    ("Retrieval was disabled in the final system.", "UNMET"),
    ("This report describes an unrelated gardening project.", "CANNOT_ASSESS"),
])
def test_actual_parser_proof_satisfies_both_contracts(tmp_path, text, outcome):
    report = _report(tmp_path, text)
    assert report["checklist_results"][0]["checklist_outcome"] == outcome
    validate_json_schema(report, kind="assessment")
    validate_assessment_report(report)


@pytest.mark.parametrize(("text", "field"), [
    ("We used BM25 for retrieval.", "matched_evidence_spans"),
    ("Retrieval was disabled in the final system.", "contradiction_hits"),
])
def test_conclusive_outcome_cannot_drop_its_proof(tmp_path, text, field):
    report = _report(tmp_path, text)
    report["checklist_results"][0][field] = []
    with pytest.raises(ValueError, match="requires nonempty"):
        validate_assessment_report(report)


def test_proof_cannot_survive_removal_of_its_evidence_pack(tmp_path):
    report = _report(tmp_path)
    report["checklist_results"][0]["evidence_pack"] = []
    # The wire schema alone does not enforce references or proof presence.
    validate_json_schema(report, kind="assessment")
    with pytest.raises(ValueError, match="outside its Evidence Pack"):
        validate_assessment_report(report)


@pytest.mark.parametrize(("field", "value"), [
    ("chunk_id", "foreign-chunk"),
    ("document_id", "foreign-report"),
    ("document_version_id", "foreign-version"),
    ("source_spans", []),
    ("normalized_end", 0),
    ("text", "a fabricated longer quotation"),
])
def test_support_proof_must_retain_its_identity_range_and_raw_locators(tmp_path, field, value):
    report = _report(tmp_path)
    report["checklist_results"][0]["matched_evidence_spans"][0]["span"][field] = value
    with pytest.raises(ValueError):
        validate_assessment_report(report)


@pytest.mark.parametrize("field", ["document_id", "document_version_id", "element_key"])
def test_proof_cannot_substitute_a_raw_source_locator(tmp_path, field):
    report = _report(tmp_path)
    proof = report["checklist_results"][0]["matched_evidence_spans"][0]
    proof["span"]["source_spans"][0][field] = "foreign-value"
    with pytest.raises(ValueError, match="source span differs"):
        validate_assessment_report(report)


def test_nested_requirement_proof_cannot_hide_behind_a_valid_flat_proof(tmp_path):
    report = _report(tmp_path)
    checklist = report["checklist_results"][0]
    nested = deepcopy(checklist["requirement_results"][0]["hits"])
    nested[0]["evidence_id"] = "missing-evidence"
    checklist["requirement_results"][0]["hits"] = nested
    with pytest.raises(ValueError, match="outside its Evidence Pack"):
        validate_assessment_report(report)


def test_proof_range_cannot_be_detached_from_an_unchanged_raw_locator(tmp_path):
    report = _report(tmp_path)
    span = report["checklist_results"][0]["matched_evidence_spans"][0]["span"]
    span["normalized_start"] += 10000
    span["normalized_end"] += 10000
    with pytest.raises(ValueError, match="does not overlap"):
        validate_assessment_report(report)


def test_optional_matched_locator_offsets_must_agree_with_the_proof(tmp_path):
    report = _report(tmp_path)
    proof = report["checklist_results"][0]["matched_evidence_spans"][0]
    proof["span"]["source_spans"][0]["matched_chunk_normalized_end"] = 999999
    with pytest.raises(ValueError, match="inconsistent matched source offsets"):
        validate_assessment_report(report)


def test_met_cannot_omit_support_for_a_listed_requirement(tmp_path):
    report = _report(tmp_path)
    report["checklist_results"][0]["requirement_results"][0]["hits"] = []
    with pytest.raises(ValueError, match="every listed requirement"):
        validate_assessment_report(report)


def test_evidence_pack_ids_are_unique(tmp_path):
    report = _report(tmp_path)
    pack = report["checklist_results"][0]["evidence_pack"]
    pack.append(deepcopy(pack[0]))
    with pytest.raises(ValueError, match="must be unique"):
        validate_assessment_report(report)


def test_evidence_pack_locator_must_match_its_document_version(tmp_path):
    report = _report(tmp_path)
    pack = report["checklist_results"][0]["evidence_pack"]
    pack[0]["source_spans"][0]["document_version_id"] = "foreign-version"
    with pytest.raises(ValueError, match="different document/version"):
        validate_assessment_report(report)


def test_cannot_assess_can_retain_no_evidence(tmp_path):
    report = _report(tmp_path, "This is an unrelated gardening report.")
    checklist = report["checklist_results"][0]
    assert checklist["checklist_outcome"] == "CANNOT_ASSESS"
    checklist["evidence_pack"] = []
    validate_assessment_report(report)


def test_proof_cannot_extend_factual_text_past_its_source_span(tmp_path):
    report = _report(tmp_path)
    proof = report["checklist_results"][0]["matched_evidence_spans"][0]["span"]
    source = proof["source_spans"][0]
    end = source["chunk_normalized_char_end"]
    proof["normalized_end"] = end + 10
    proof["text"] = "x" * (proof["normalized_end"] - proof["normalized_start"])
    source["matched_chunk_normalized_end"] = end
    with pytest.raises(ValueError, match="text outside its source spans"):
        validate_assessment_report(report)


def test_older_reports_do_not_require_new_context_diagnostic_fields(tmp_path):
    report = _report(tmp_path)
    checklist = report["checklist_results"][0]
    for field in (
        "negated_evidence_spans", "non_asserted_evidence_spans", "withheld_contradiction_spans",
    ):
        checklist.pop(field, None)
    for requirement in checklist["requirement_results"]:
        requirement.pop("negated_hits", None)
        requirement.pop("non_asserted_hits", None)
    validate_assessment_report(report)
