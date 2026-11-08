"""Context regressions on synthetic reports, independent of the demo rubric."""

from __future__ import annotations

import pytest

from research.core_mvp.assessment import run_assessment_pipeline


def _run(
    text: str, phrase: str, *, contradiction: str | None = None,
    statement: str | None = None,
) -> dict:
    checklist = {
        "checklist_id": "C1.1",
        "statement": statement or f"The report demonstrates completed work concerning {phrase}.",
        "mode": "LOCAL",
        "importance": "REQUIRED",
        "requirements": [{"requirement_id": "work-evidence", "any_of": [phrase]}],
        "contradiction_patterns": [contradiction] if contradiction else [],
    }
    rubric = {
        "schema_version": 1,
        "rubric_id": "synthetic-context-regression",
        "version": "1",
        "max_score": 10.0,
        "criteria": [{
            "criterion_id": "C1", "title": "Implementation evidence", "weight": 10.0,
            "checklists": [checklist],
        }],
    }
    chunk = {
        "chunk_id": "synthetic-report-1", "document_id": "synthetic-report",
        "normalized_text": text, "text": text,
    }
    return run_assessment_pipeline(
        [chunk], rubric,
        config={"candidate_depth": 1, "rerank_depth": 1, "top_k": 1,
                "dense_enabled": False, "reranker_enabled": False},
        encoder=None, reranker=None,
    )


@pytest.mark.parametrize("text, phrase", [
    ("The worker consumes tasks from a Redis queue without a separate broker.",
     "Redis queue"),
    ("The contamination audit found no overlap between the reserved splits.",
     "contamination audit"),
])
def test_later_negative_auxiliary_does_not_cancel_affirmed_work(text, phrase):
    result = _run(text, phrase)
    [item] = result["checklist_results"]
    assert item["checklist_outcome"] == "MET"
    assert item["requirement_results"][0]["hits"]
    assert item["negated_evidence_spans"] == []


@pytest.mark.parametrize("text, phrase", [
    ("We will perform a throughput evaluation next month.", "throughput evaluation"),
    ("We plan to perform a throughput evaluation next month.", "throughput evaluation"),
    ("Independent calibration remains pending.", "Independent calibration"),
    ("We await independent calibration before drawing conclusions.", "independent calibration"),
    ("A throughput evaluation is planned for the next release.", "throughput evaluation"),
    ("Dự kiến thực hiện đánh giá thông lượng trong giai đoạn tiếp theo.", "đánh giá thông lượng"),
    ("Đánh giá thông lượng sẽ được thực hiện trong giai đoạn tiếp theo.", "Đánh giá thông lượng"),
])
def test_prospective_or_pending_mentions_do_not_prove_completed_work(text, phrase):
    result = _run(text, phrase)
    [item] = result["checklist_results"]
    assert item["checklist_outcome"] == "CANNOT_ASSESS"
    assert item["requirements_satisfied"] == 0
    assert item["requirement_results"][0]["hits"] == []
    assert result["proposed_total_score"] is None


@pytest.mark.parametrize("text", [
    "If the fault injection test succeeds, the deployment can proceed.",
    "Nếu thử nghiệm lỗi thành công thì có thể triển khai hệ thống.",
])
def test_conditional_mention_does_not_prove_the_condition_happened(text):
    phrase = "fault injection test" if text.startswith("If") else "thử nghiệm lỗi"
    result = _run(text, phrase)
    assert result["checklist_results"][0]["checklist_outcome"] == "CANNOT_ASSESS"
    assert result["proposed_total_score"] is None


def test_hypothetical_authored_contradiction_is_not_an_actual_failure():
    result = _run(
        "If calibration is incomplete, a further trial will be scheduled.",
        "calibration", contradiction="calibration is incomplete",
    )
    [item] = result["checklist_results"]
    assert item["checklist_outcome"] == "CANNOT_ASSESS"
    assert item["contradiction_hits"] == []
    assert result["proposed_total_score"] is None


def test_explicit_current_authored_contradiction_remains_unmet():
    result = _run(
        "Calibration is incomplete and the current release has no results.",
        "completed calibration", contradiction="Calibration is incomplete",
    )
    [item] = result["checklist_results"]
    assert item["checklist_outcome"] == "UNMET"
    assert item["contradiction_hits"]


@pytest.mark.parametrize("text", [
    "The service runs without request encryption.",
    "Request encryption was not implemented for the current release.",
    "Không triển khai request encryption trong phiên bản hiện tại.",
])
def test_negation_of_the_requested_work_still_withholds_support(text):
    result = _run(text, "request encryption")
    [item] = result["checklist_results"]
    assert item["checklist_outcome"] == "CANNOT_ASSESS"
    assert item["requirement_results"][0]["hits"] == []
    assert item["negated_evidence_spans"]
    assert result["proposed_total_score"] is None


def test_real_positive_and_negative_conflict_still_requires_review():
    result = _run(
        "The capacity assessment was completed. "
        "The capacity assessment was not performed for this release.",
        "capacity assessment",
    )
    [item] = result["checklist_results"]
    assert item["checklist_outcome"] == "CANNOT_ASSESS"
    assert item["reason_code"] == "CONFLICTING_REPORT_EVIDENCE"
    assert item["requirement_results"][0]["hits"]
    assert item["negated_evidence_spans"]


def test_unrelated_future_sentence_does_not_cancel_completed_evidence():
    result = _run(
        "We plan to repeat inspection next month. "
        "The initial inspection was completed yesterday.",
        "initial inspection",
    )
    assert result["checklist_results"][0]["checklist_outcome"] == "MET"


def test_missing_required_evidence_remains_unknown():
    result = _run("The report describes the interface layout.", "capacity assessment")
    assert result["checklist_results"][0]["checklist_outcome"] == "CANNOT_ASSESS"
    assert result["proposed_total_score"] is None


@pytest.mark.parametrize("text, phrase, statement", [
    ("We will perform load trials in the next release.", "load trials",
     "The report describes a plan for load trials."),
    ("Chúng tôi dự kiến thực hiện kiểm thử tải vào tháng tới.", "kiểm thử tải",
     "Báo cáo trình bày kế hoạch kiểm thử tải."),
])
def test_a_plan_requirement_accepts_evidence_of_a_plan(text, phrase, statement):
    result = _run(text, phrase, statement=statement)
    [item] = result["checklist_results"]
    assert item["checklist_outcome"] == "MET"
    assert item["non_asserted_evidence_spans"] == []


def test_completion_wording_takes_precedence_over_mention_of_a_plan():
    result = _run(
        "We plan to perform load trials next month.", "load trials",
        statement="The report provides a plan and demonstrates completed load trials.",
    )
    [item] = result["checklist_results"]
    assert item["checklist_outcome"] == "CANNOT_ASSESS"
    assert item["requirement_results"][0]["hits"] == []


def test_later_future_sentence_does_not_cancel_completed_occurrence():
    result = _run(
        "A capacity assessment was completed yesterday. "
        "A capacity assessment will be repeated next month.",
        "capacity assessment",
    )
    [item] = result["checklist_results"]
    assert item["checklist_outcome"] == "MET"
    assert len(item["requirement_results"][0]["hits"]) == 1
    assert len(item["non_asserted_evidence_spans"]) == 1
    assert item["negated_evidence_spans"] == []


def test_later_actual_contradiction_is_not_hidden_by_first_hypothetical_match():
    text = (
        "If calibration is incomplete, a further trial will be scheduled. "
        "Calibration is incomplete in the current release."
    )
    result = _run(text, "completed calibration", contradiction="calibration is incomplete")
    [item] = result["checklist_results"]
    assert item["checklist_outcome"] == "UNMET"
    [actual] = item["contradiction_hits"]
    assert actual["span"]["normalized_start"] > text.index(".")
    assert actual["span"]["text"] == "Calibration is incomplete"
    [hypothetical] = item["withheld_contradiction_spans"]
    assert hypothetical["context_reason"] == "CONDITIONAL_MENTION"
    assert hypothetical["span"]["text"] in text


def test_non_actual_evidence_preserves_exact_context_without_becoming_negation():
    text = "Introduction. We plan to measure response latency next month. Conclusion."
    result = _run(text, "response latency")
    [item] = result["checklist_results"]
    [hit] = item["non_asserted_evidence_spans"]
    span = hit["span"]
    assert span["text"] == text[span["normalized_start"]:span["normalized_end"]]
    assert "We plan to measure response latency next month" in span["text"]
    assert "Introduction" not in span["text"]
    assert "Conclusion" not in span["text"]
    assert item["requirement_results"][0]["non_asserted_hits"] == [hit]
    assert item["requirement_results"][0]["hits"] == []
    assert item["negated_evidence_spans"] == []


@pytest.mark.parametrize("text", [
    "Throughput evaluation is currently awaiting independent review.",
    "Throughput evaluation has been planned for the next release.",
    "Throughput evaluation was scheduled for next month.",
])
def test_postposed_pending_or_planned_status_cannot_prove_completion(text):
    result = _run(text, "Throughput evaluation")
    [item] = result["checklist_results"]
    assert item["checklist_outcome"] == "CANNOT_ASSESS"
    assert item["non_asserted_evidence_spans"]
    assert item["requirement_results"][0]["hits"] == []
    assert item["negated_evidence_spans"] == []


def test_independent_negative_mentions_do_not_cancel_an_authored_negative_claim():
    result = _run(
        "Calibration completed. No audit and no verified results.",
        "calibration completed", contradiction="no verified results",
    )
    [item] = result["checklist_results"]
    assert item["checklist_outcome"] == "CANNOT_ASSESS"
    assert item["reason_code"] == "CONFLICTING_REPORT_EVIDENCE"
    assert item["contradiction_hits"]
    assert item["requirement_results"][0]["hits"]


@pytest.mark.parametrize("text", [
    "We completed calibration. On May 12, calibration is incomplete.",
    "We completed calibration. It should be noted that calibration is incomplete.",
])
def test_calendar_month_or_discourse_marker_does_not_hide_actual_counterclaim(text):
    result = _run(text, "completed calibration", contradiction="calibration is incomplete")
    [item] = result["checklist_results"]
    assert item["checklist_outcome"] == "CANNOT_ASSESS"
    assert item["reason_code"] == "CONFLICTING_REPORT_EVIDENCE"
    [counterclaim] = item["contradiction_hits"]
    assert counterclaim["span"]["text"] == "calibration is incomplete"
    assert item["requirement_results"][0]["hits"]


@pytest.mark.parametrize("text", [
    "We could perform calibration after approval.",
    "We should perform calibration after approval.",
    "We may perform calibration after approval.",
])
def test_actual_modal_action_is_still_withheld_from_completed_evidence(text):
    result = _run(text, "calibration")
    [item] = result["checklist_results"]
    assert item["checklist_outcome"] == "CANNOT_ASSESS"
    assert item["requirement_results"][0]["hits"] == []
    assert item["non_asserted_evidence_spans"]


def test_external_denial_of_authored_counterclaim_does_not_assert_that_claim():
    result = _run(
        "It is not true that calibration is incomplete.",
        "completed calibration", contradiction="calibration is incomplete",
    )
    [item] = result["checklist_results"]
    assert item["checklist_outcome"] == "CANNOT_ASSESS"
    assert item["contradiction_hits"] == []
    [withheld] = item["withheld_contradiction_spans"]
    assert "not true that calibration is incomplete" in withheld["span"]["text"]


@pytest.mark.parametrize("counterclaim_sentence", [
    "We plan to repeat inspection because calibration is incomplete.",
    "We will repeat inspection, and calibration is incomplete.",
    "Even if review is delayed, calibration is incomplete.",
])
def test_uncertain_modal_scope_cannot_erase_a_conflicting_current_statement(
    counterclaim_sentence,
):
    result = _run(
        "We completed calibration. " + counterclaim_sentence,
        "completed calibration", contradiction="calibration is incomplete",
    )
    [item] = result["checklist_results"]
    assert item["checklist_outcome"] == "CANNOT_ASSESS"
    assert item["requirement_results"][0]["hits"]
    assert result["proposed_total_score"] is None
