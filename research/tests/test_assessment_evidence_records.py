"""Source spans and whole-text absence must remain different evidence types."""
from copy import deepcopy
import hashlib

import pytest

from research.gold_annotation.assessment_evidence import (
    compare_evidence,
    span_identifier,
    summarize_comparisons,
    validate_evidence_record,
)


def context(*paragraphs):
    text = "\n\n".join(paragraphs)
    result = {"report_id": "report-test", "report_version": "source-v1",
              "body_sha256": hashlib.sha256(text.encode()).hexdigest(),
              "report_text": text, "paragraphs": []}
    offset = 0
    for index, paragraph in enumerate(paragraphs, 1):
        result["paragraphs"].append({"paragraph_id": f"P{index:04d}",
                                     "start": offset, "end": offset + len(paragraph), "text": paragraph})
        offset += len(paragraph) + 2
    return result


def record(ctx, kind, **fields):
    return {"schema_version": 1, "kind": kind,
            **{key: ctx[key] for key in ("report_id", "report_version", "body_sha256")}, **fields}


def spans(scope, *ranges):
    return record(scope, "SPAN_SET", spans=[
        {"start": start, "end": end, "quote": scope["report_text"][start:end]}
        for start, end in ranges])


def absence(ctx, **changes):
    data = record(ctx, "DOCUMENT_ABSENCE", scope="ENTIRE_CAPTURED_TEXT", reviewed_whole_text=True,
                  paragraph_ids=[p["paragraph_id"] for p in ctx["paragraphs"]],
                  rationale="Reviewed the complete captured text; the required element is absent.")
    return {**data, **changes}


def test_unicode_span_is_exact_in_code_points_and_fills_source_bound_id():
    scope = context("🌱 Mẹ kể chuyện.", "Other text.")
    source = spans(scope, (2, 5))
    result = validate_evidence_record(source, scope)
    assert result["spans"] == [{"span_id": span_identifier(scope, 2, 5), "start": 2, "end": 5,
                                "quote": "Mẹ ", "paragraph_id": "P0001"}]
    assert "span_id" not in source["spans"][0]  # Never mutate submitted evidence.


def test_same_quote_in_different_paragraphs_has_distinct_explicit_range_ids():
    scope = context("Same words.", "Same words.")
    first, second = scope["paragraphs"]
    result = validate_evidence_record(spans(scope, (first["start"], first["end"]),
                                           (second["start"], second["end"])), scope)
    assert result["spans"][0]["quote"] == result["spans"][1]["quote"]
    assert result["spans"][0]["span_id"] != result["spans"][1]["span_id"]


@pytest.mark.parametrize("field,value", [("report_id", "other-report"),
                                         ("report_version", "other-version"),
                                         ("body_sha256", "a" * 64)])
def test_cross_report_version_or_body_identity_rejected(field, value):
    scope = context("An actual observation.")
    data = spans(scope, (0, 2))
    data[field] = value
    with pytest.raises(ValueError, match="identity conflict"):
        validate_evidence_record(data, scope)


@pytest.mark.parametrize("change", [
    {"quote": "not in source"}, {"start": True}, {"end": 9999},
    {"paragraph_id": "P9999"}, {"span_id": "fabricated"}, {"grade": 100},
])
def test_forged_span_geometry_quote_or_fields_rejected(change):
    scope = context("An actual observation.")
    data = spans(scope, (0, 2))
    data["spans"][0].update(change)
    with pytest.raises(ValueError):
        validate_evidence_record(data, scope)


def test_cross_paragraph_quote_is_not_silently_assigned_to_one_paragraph():
    scope = context("First.", "Second.")
    with pytest.raises(ValueError, match="paragraph"):
        validate_evidence_record(spans(scope, (0, len(scope["report_text"]))), scope)


def test_duplicate_identical_span_rejected_but_overlap_allowed_for_union_metrics():
    scope = context("abcdefghij")
    with pytest.raises(ValueError, match="duplicate"):
        validate_evidence_record(spans(scope, (0, 5), (0, 5)), scope)
    result = compare_evidence(spans(scope, (0, 8), (4, 10)), spans(scope, (0, 10)), scope)
    metrics = result["span_evidence"]["metrics"]
    assert metrics["predicted_chars"] == metrics["reference_chars"] == metrics["overlap_chars"] == 10
    assert metrics["precision"] == metrics["recall"] == metrics["f1"] == 1.0


def test_real_whole_text_absence_record_has_no_fake_span_and_canonical_coverage():
    scope = context("A topic is mentioned.", "The discussion ends.")
    result = validate_evidence_record(absence(scope, paragraph_ids=["P0002", "P0001"]), scope)
    assert result["paragraph_ids"] == ["P0001", "P0002"]
    assert result["scope"] == "ENTIRE_CAPTURED_TEXT"
    assert "spans" not in result
    assert result["reviewed_whole_text"] is True


@pytest.mark.parametrize("change", [
    {"reviewed_whole_text": False}, {"reviewed_whole_text": "True"}, {"reviewed_whole_text": 1},
    {"paragraph_ids": ["P0001"]}, {"paragraph_ids": ["P0001", "P0001"]},
    {"paragraph_ids": ["P0001", "invented"]}, {"scope": "ORIGINAL_PDF"},
    {"rationale": "  "}, {"spans": []},
])
def test_absence_cannot_be_claimed_from_incomplete_or_unattested_scope(change):
    scope = context("A topic is mentioned.", "The discussion ends.")
    with pytest.raises(ValueError):
        validate_evidence_record(absence(scope, **change), scope)


def test_context_omitting_a_real_paragraph_cannot_authorize_absence():
    scope = context("First.", "Omitted but present text.")
    scope["paragraphs"] = scope["paragraphs"][:1]
    with pytest.raises(ValueError, match="omit captured text"):
        validate_evidence_record(absence(scope), scope)


def test_empty_or_whitespace_captured_body_does_not_prove_required_content_absence():
    scope = context("   ")
    with pytest.raises(ValueError, match="absence"):
        validate_evidence_record(absence(scope), scope)


def test_changed_context_text_or_overlapping_paragraphs_is_rejected():
    scope = context("First.", "Second.")
    data = absence(scope)
    changed = deepcopy(scope)
    changed["report_text"] += "Not hashed"
    with pytest.raises(ValueError, match="text/hash"):
        validate_evidence_record(data, changed)
    changed = deepcopy(scope)
    changed["paragraphs"][1]["start"] = 0
    changed["paragraphs"][1]["end"] = 6
    changed["paragraphs"][1]["text"] = "First."
    with pytest.raises(ValueError, match="overlap"):
        validate_evidence_record(data, changed)


@pytest.mark.parametrize("kind", ["INSUFFICIENT_INPUT", "UNRESOLVED"])
def test_insufficient_and_unresolved_have_no_implicit_positive_evidence(kind):
    scope = context("Some text.")
    data = record(scope, kind, rationale="Requires clarification.")
    assert validate_evidence_record(data, scope)["kind"] == kind
    with pytest.raises(ValueError, match="unexpected"):
        validate_evidence_record({**data, "spans": []}, scope)


@pytest.mark.parametrize("data", [{}, {"schema_version": True}, {"schema_version": 1, "kind": []}])
def test_malformed_record_fails_with_safe_value_error(data):
    scope = context("Some text.")
    with pytest.raises(ValueError):
        validate_evidence_record(data, scope)


def test_span_overlap_counts_partial_match_without_calling_it_semantic_truth():
    scope = context("abcdefghijklmnopqrst")
    result = compare_evidence(spans(scope, (5, 15)), spans(scope, (0, 10)), scope)
    assert result["span_evidence"]["metrics"] == {
        "reference_chars": 10, "predicted_chars": 10, "overlap_chars": 5,
        "precision": 0.5, "recall": 0.5, "f1": 0.5,
    }
    assert result["semantic_support_verified"] is False


def test_absence_scope_match_is_separate_and_never_empty_span_perfection():
    scope = context("A title.", "A closing paragraph.")
    result = compare_evidence(absence(scope), absence(scope), scope)
    assert result["document_absence"]["matching_complete_scope_record"] is True
    assert result["document_absence"]["semantic_absence_verified"] is False
    assert result["span_evidence"] == {"applicable": False, "metrics": None}
    summary = summarize_comparisons([result])
    assert summary["span_geometry"]["f1"] is None
    assert summary["document_absence"]["matching_complete_scope_records"] == 1


def test_span_prediction_for_absence_is_not_converted_to_document_absence():
    scope = context("A closing paragraph.")
    result = compare_evidence(spans(scope, (0, 3)), absence(scope), scope)
    assert result["document_absence"]["matching_complete_scope_record"] is False
    assert result["document_absence"]["unexpected_span_chars"] == 3
    assert result["span_evidence"]["metrics"] is None


def test_empty_span_set_is_not_a_valid_absence_record():
    scope = context("Some complete captured text.")
    with pytest.raises(ValueError, match="nonempty"):
        compare_evidence(record(scope, "SPAN_SET", spans=[]), absence(scope), scope)


def test_missing_prediction_evidence_lowers_span_recall_not_inferred_ca_label():
    scope = context("An observation.")
    result = compare_evidence(None, spans(scope, (0, 5)), scope)
    assert result["prediction_evidence_missing"] is True
    assert result["span_evidence"]["metrics"]["recall"] == 0.0
    assert result["span_evidence"]["metrics"]["f1"] == 0.0
    assert "label" not in result and "technical_abstention" not in result


def test_semantic_insufficient_empty_evidence_never_gets_perfect_span_f1():
    scope = context("Text without a needed external resource.")
    evidence = record(scope, "INSUFFICIENT_INPUT", rationale="External source unavailable.")
    result = compare_evidence(evidence, evidence, scope)
    assert result["kind_match"] is True
    assert result["span_evidence"]["metrics"]["f1"] is None


def test_unresolved_references_remain_visible_and_excluded_from_metrics():
    scope = context("Text requiring a rule decision.")
    unresolved = record(scope, "UNRESOLVED", rationale="Counting convention unclear.")
    result = compare_evidence(spans(scope, (0, 4)), unresolved, scope)
    summary = summarize_comparisons([result])
    assert summary["unresolved_reference_items"] == 1
    assert summary["compared_items"] == 0
    assert summary["span_geometry"]["items"] == 0
    assert summary["span_geometry"]["predicted_chars"] == 0


def test_summary_micro_averages_span_intervals_and_keeps_absence_denominator_separate():
    scope = context("abcdefghijklmnopqrst")
    rows = [compare_evidence(spans(scope, (5, 15)), spans(scope, (0, 10)), scope),
            compare_evidence(None, spans(scope, (0, 5)), scope),
            compare_evidence(absence(scope), absence(scope), scope)]
    summary = summarize_comparisons(rows)
    assert summary["items"] == 3 and summary["span_geometry"]["items"] == 2
    assert summary["span_geometry"]["reference_chars"] == 15
    assert summary["span_geometry"]["predicted_chars"] == 10
    assert summary["span_geometry"]["overlap_chars"] == 5
    assert summary["span_geometry"]["precision"] == 0.5
    assert summary["span_geometry"]["recall"] == pytest.approx(1 / 3)
    assert summary["span_geometry"]["f1"] == 0.4
    assert summary["document_absence"]["reference_items"] == 1
