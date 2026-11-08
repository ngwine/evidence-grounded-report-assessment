"""Retrieval location coverage is not semantic evidence correctness."""
from copy import deepcopy

import pytest

from research.gold_annotation.assessment_evidence import compare_evidence
from research.p2_comparison.retrieval_study_analysis import paired_report_interval, retrieved_location_record
from research.tests.test_assessment_evidence_records import absence, context, spans


def pack(scope, selections):
    source = []
    for paragraph_index, start, end in selections:
        paragraph = scope["paragraphs"][paragraph_index]
        source.append({"locator": {"document_raw_char_start": paragraph["start"]},
            "element_raw_char_start": start, "element_raw_char_end": end})
    return {"evidence_pack": [{"record": {"source_spans": deepcopy(source)},
                                "chunk": {"source_spans": source}}]}


def test_retrieved_context_preserves_unicode_source_offsets_and_deduplicates_ranges():
    scope = context("Tôi đã thử. 🌱", "Kết quả có bằng chứng.")
    item = pack(scope, [(0, 0, 3), (0, 0, 3), (1, 0, 7)])
    result = retrieved_location_record(item, scope)
    assert len(result["spans"]) == 2
    assert result["spans"][0]["quote"] == "Tôi"
    second = result["spans"][1]
    assert second["start"] == scope["paragraphs"][1]["start"]
    assert second["quote"] == "Kết quả"


def test_overlapping_retrieval_ranges_do_not_double_count_reference_chars():
    scope = context("ABCDEFGHIJ")
    result = retrieved_location_record(pack(scope, [(0, 0, 7), (0, 4, 10)]), scope)
    comparison = compare_evidence(result, spans(scope, (2, 5)), scope)
    assert comparison["span_evidence"]["metrics"]["predicted_chars"] == 10
    assert comparison["span_evidence"]["metrics"]["overlap_chars"] == 3
    assert comparison["span_evidence"]["metrics"]["recall"] == 1
    assert comparison["semantic_support_verified"] is False


def test_complete_retrieval_cannot_certify_document_absence_or_semantic_support():
    scope = context("The report omits a required item.")
    result = retrieved_location_record(pack(scope, [(0, 0, len(scope["report_text"]))]), scope)
    comparison = compare_evidence(result, absence(scope), scope)
    assert not comparison["span_evidence"]["applicable"]
    assert not comparison["document_absence"]["matching_complete_scope_record"]
    assert not comparison["document_absence"]["semantic_absence_verified"]


def test_cross_paragraph_or_changed_source_map_is_rejected():
    scope = context("First.", "Second.")
    with pytest.raises(ValueError, match="outside its captured paragraph"):
        retrieved_location_record(pack(scope, [(0, 0, len(scope["report_text"]))]), scope)
    item = pack(scope, [(0, 0, 3)])
    item["evidence_pack"][0]["record"]["source_spans"] = []
    with pytest.raises(ValueError, match="source map differs"):
        retrieved_location_record(item, scope)


def test_paired_bootstrap_uses_reports_not_independent_checklists_and_is_repeatable():
    references = [{"item_id": str(i), "case_id": "A" if i < 4 else "B", "label": "MET"} for i in range(5)]
    first = [{**r, "accepted_label": "CANNOT_ASSESS" if r["case_id"] == "A" else "MET"} for r in references]
    second = [{**r, "accepted_label": "MET" if r["case_id"] == "A" else None} for r in references]
    result = paired_report_interval(references, first, second, draws=100)
    assert result["reports"] == 2
    assert result["second_minus_first_report_mean_agreement"] == 0
    assert result["percentile_95_interval"] == [-1, 1]
    assert result == paired_report_interval(references, first, second, draws=100)
    assert result["confirmatory_significance_claim"] is False


def test_paired_bootstrap_rejects_missing_items_and_preserves_technical_failures():
    references = [{"item_id": "x", "case_id": "A", "label": "MET"}]
    first = [{**references[0], "accepted_label": None}]
    second = [{**references[0], "accepted_label": "MET"}]
    result = paired_report_interval(references, first, second, draws=20)
    assert result["second_minus_first_report_mean_agreement"] == 1
    assert result["percentile_95_interval"] == [1, 1]
    with pytest.raises(ValueError, match="all items once"):
        paired_report_interval(references, first, [])
