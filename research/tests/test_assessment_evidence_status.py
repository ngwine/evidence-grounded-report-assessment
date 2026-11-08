"""Status and predicate regressions for authored assessment requirements.

The cases use different tasks from the LIP development report and retain
genuine contradictory or missing evidence as unknown. They are software
regressions, not an independently human-labelled effectiveness benchmark.
"""

from __future__ import annotations

import pytest

from research.core_mvp.assessment import run_assessment_pipeline


def _run(text, phrase, *, statement=None, section=(), alternatives=(), contradiction=()):
    rubric = {
        "schema_version": 1, "rubric_id": "evidence-status-regression", "version": "1",
        "max_score": 10,
        "criteria": [{
            "criterion_id": "quality", "title": "Evidence", "weight": 10,
            "checklists": [{
                "checklist_id": "quality.evidence", "mode": "LOCAL", "importance": "REQUIRED",
                "statement": statement or f"Completed work concerning {phrase} is demonstrated.",
                "requirements": [{"requirement_id": "actual", "description": "Requested evidence",
                                  "any_of": [phrase, *alternatives]}],
                "contradiction_patterns": list(contradiction),
            }],
        }],
    }
    return run_assessment_pipeline(
        [{"chunk_id": "report-block", "document_id": "status-report", "text": text,
          "normalized_text": text, "section_path": list(section)}], rubric,
        config={"candidate_depth": 1, "rerank_depth": 1, "top_k": 1,
                "dense_enabled": False, "reranker_enabled": False},
        encoder=None, reranker=None,
    )


@pytest.mark.parametrize("text,phrase", [
    ("The services are to be compared using mean throughput and worst-case latency.", "mean throughput"),
    ("Next: gather independently verified task annotations.", "task annotations"),
    ("Tiếp theo: thu thập bản ghi đã xác minh để đánh giá.", "bản ghi đã xác minh"),
    ("Precision, sensitivity and throughput remain pending.", "Precision"),
    ("Precision, sensitivity and throughput remain pending.", "sensitivity"),
    ("Method Measure\nClassifier Precision, sensitivity (pending)", "Precision"),
    ("Chỉ số: độ nhạy và độ chính xác vẫn đang chờ xác minh.", "độ nhạy"),
])
def test_planned_or_coordinated_pending_metrics_do_not_prove_completed_results(text, phrase):
    report = _run(text, phrase)
    [item] = report["checklist_results"]
    assert item["checklist_outcome"] == "CANNOT_ASSESS"
    assert item["requirement_results"][0]["hits"] == []
    assert item["non_asserted_evidence_spans"]
    assert report["proposed_total_score"] is None


@pytest.mark.parametrize("section,text", [
    (["7. Remaining work"], "High priority: an independently checked reference dataset."),
    (["Kế hoạch tiếp theo"], "Cần có bộ nhãn đã kiểm chứng để đối chiếu."),
    ([], "Priority Item Evidence needed\nHigh Calibration A reference dataset."),
])
def test_future_work_table_or_section_is_not_actual_completion(section, text):
    phrase = "reference dataset" if "reference dataset" in text else "bộ nhãn đã kiểm chứng"
    [item] = _run(text, phrase, section=section)["checklist_results"]
    assert item["checklist_outcome"] == "CANNOT_ASSESS"
    assert item["non_asserted_evidence_spans"][0]["context_reason"] == "PLANNING_SECTION_MENTION"


@pytest.mark.parametrize("text,phrase", [
    ("There is a comparison tool for a manually annotated reference sample.", "manually annotated"),
    ("Có công cụ để đánh giá bản ghi tham chiếu của người dùng.", "bản ghi tham chiếu"),
])
def test_tool_availability_alone_does_not_prove_completed_measurement(text, phrase):
    [item] = _run(text, phrase)["checklist_results"]
    assert item["checklist_outcome"] == "CANNOT_ASSESS"
    assert item["non_asserted_evidence_spans"][0]["context_reason"] == "CAPABILITY_ONLY_MENTION"


@pytest.mark.parametrize("text,phrase,section", [
    ("We used the tool for a manually annotated sample and measured throughput.", "manually annotated", []),
    ("Throughput=0.85, sensitivity (pending).", "Throughput", []),
    ("Initial calibration was completed yesterday.", "Initial calibration", ["Remaining work"]),
    ("The baseline measurement was completed. Future work covers additional workloads.", "baseline measurement", []),
])
def test_actual_results_are_not_erased_by_tool_or_later_planning_status(text, phrase, section):
    [item] = _run(text, phrase, section=section)["checklist_results"]
    assert item["checklist_outcome"] == "MET"


@pytest.mark.parametrize("text,statement,phrase", [
    ("A replay attempt did not modify the archived payload.",
     "The archived payload is immutable and its integrity is protected.", "archived payload"),
    ("Thử ghi lại không thay đổi bản chụp dữ liệu.",
     "Báo cáo cho thấy bản chụp dữ liệu được bảo vệ và cố định.", "bản chụp dữ liệu"),
    ("The source collection is not representative of production traffic.",
     "The report discloses limitations of the source collection.", "source collection"),
    ("Thử nghiệm không đại diện cho lưu lượng thực tế.",
     "Báo cáo công khai hạn chế và tính đại diện của thử nghiệm.", "lưu lượng thực tế"),
])
def test_required_preservation_or_limitation_can_be_expressed_by_negative_predicate(text, statement, phrase):
    [item] = _run(text, phrase, statement=statement)["checklist_results"]
    assert item["checklist_outcome"] == "MET"
    assert item["negated_evidence_spans"] == []
    [hit] = item["requirement_results"][0]["hits"]
    assert hit["context_reason"] in {"PRESERVATION_NEGATIVE_PREDICATE", "REQUESTED_LIMITATION_STATEMENT"}
    assert hit["span"]["text"] in text


@pytest.mark.parametrize("text,phrase,statement", [
    ("The report did not mention limitations of the source collection.", "source collection",
     "The report discloses limitations of the source collection."),
    ("Báo cáo không nêu hạn chế của lưu lượng thực tế.", "lưu lượng thực tế",
     "Báo cáo nêu hạn chế và tính đại diện của lưu lượng thực tế."),
    ("The job did not complete the integrity inspection.", "integrity inspection",
     "The integrity inspection was completed and protects the archive."),
])
def test_denial_of_requested_reporting_or_completion_still_withholds_support(text, phrase, statement):
    report = _run(text, phrase, statement=statement)
    [item] = report["checklist_results"]
    assert item["checklist_outcome"] == "CANNOT_ASSESS"
    assert item["requirement_results"][0]["hits"] == []
    assert report["proposed_total_score"] is None


def test_factual_same_work_conflict_remains_unknown_after_status_rules():
    text = "Pressure validation was completed. Pressure validation was not performed."
    [item] = _run(text, "Pressure validation")["checklist_results"]
    assert item["checklist_outcome"] == "CANNOT_ASSESS"
    assert item["reason_code"] == "CONFLICTING_REPORT_EVIDENCE"
    assert item["matched_evidence_spans"] and item["negated_evidence_spans"]


def test_factual_negative_in_future_work_section_can_still_prove_authored_counterclaim():
    [item] = _run(
        "No independent calibration has been performed.", "completed calibration",
        section=["Remaining work"], contradiction=["No independent calibration"],
    )["checklist_results"]
    assert item["checklist_outcome"] == "UNMET"


def test_explicit_plan_request_can_use_future_work_table():
    [item] = _run(
        "Priority Item Evidence needed\nHigh Calibration A reference dataset.", "reference dataset",
        statement="The report describes a plan for collecting a reference dataset.",
    )["checklist_results"]
    assert item["checklist_outcome"] == "MET"


@pytest.mark.parametrize("text,phrase", [
    ("It is to be noted that initial calibration was completed yesterday.", "initial calibration"),
    ("The tool for pressure validation was executed and measured the result.", "pressure validation"),
])
def test_actual_assertion_is_not_hidden_by_a_discourse_marker_or_postposed_tool_action(text, phrase):
    [item] = _run(text, phrase)["checklist_results"]
    assert item["checklist_outcome"] == "MET"


@pytest.mark.parametrize("text,phrase,statement", [
    ("The throughput assessment was not performed.", "throughput assessment",
     "The throughput assessment was completed and its limitations are disclosed."),
    ("The technician did not modify the integrity inspection.", "integrity inspection",
     "The integrity inspection was completed and protects the archive."),
])
def test_completion_request_is_not_satisfied_by_an_unrelated_negative_property(text, phrase, statement):
    report = _run(text, phrase, statement=statement)
    assert report["checklist_results"][0]["checklist_outcome"] == "CANNOT_ASSESS"
    assert report["proposed_total_score"] is None
