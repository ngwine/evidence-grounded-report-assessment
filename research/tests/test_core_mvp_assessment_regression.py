"""Regressions for conservative phrase verification and score abstention."""

from __future__ import annotations

import pytest

from research.core_mvp.assessment import run_assessment_pipeline


CONFIG = {
    "candidate_depth": 3,
    "rerank_depth": 3,
    "top_k": 3,
    "dense_enabled": False,
    "reranker_enabled": False,
}


def _checklist(checklist_id: str, phrase: str, *, importance: str = "REQUIRED") -> dict:
    return {
        "checklist_id": checklist_id,
        "statement": f"Report uses {phrase}.",
        "mode": "LOCAL",
        "importance": importance,
        "requirements": [
            {"requirement_id": f"uses-{checklist_id}", "any_of": [phrase]}
        ],
        "contradiction_patterns": [],
    }


def _run(
    text: str,
    checklists: list[dict],
    *,
    unknown_ratio_threshold: float = 0.9,
    second_criterion_checklists: list[dict] | None = None,
) -> dict:
    criteria = [
        {
            "criterion_id": "C1",
            "title": "Methods",
            "weight": 5.0 if second_criterion_checklists else 10.0,
            "checklists": checklists,
        }
    ]
    if second_criterion_checklists:
        criteria.append(
            {
                "criterion_id": "C2",
                "title": "Other methods",
                "weight": 5.0,
                "checklists": second_criterion_checklists,
            }
        )
    rubric = {
        "schema_version": 1,
        "rubric_id": "assessment-regression",
        "version": "1",
        "max_score": 10.0,
        "decision_rules": {
            "cannot_assess_count_threshold": 2,
            "cannot_assess_ratio_threshold": unknown_ratio_threshold,
            "required_unmet_score": 0.0,
        },
        "criteria": criteria,
    }
    chunk = {
        "chunk_id": "report-1",
        "document_id": "report",
        "normalized_text": text,
        "text": text,
    }
    return run_assessment_pipeline(
        [chunk], rubric, config=CONFIG, encoder=None, reranker=None
    )


@pytest.mark.parametrize(
    "report_text",
    [
        "Glucose3 was not used in this experiment.",
        "We did not use Glucose3 in this experiment.",
        "Không sử dụng Glucose3 trong thí nghiệm này.",
        "Glucose3 chưa được sử dụng trong thí nghiệm này.",
    ],
)
def test_negated_requirement_abstains_and_preserves_context(report_text):
    result = _run(report_text, [_checklist("uses-glucose3", "Glucose3")])
    [item] = result["checklist_results"]

    assert item["verification_relation"] == "INSUFFICIENT"
    assert item["checklist_outcome"] == "CANNOT_ASSESS"
    assert item["reason_code"] == "NEGATED_REQUIRED_EVIDENCE"
    assert item["requirements_satisfied"] == 0
    assert item["requirement_results"][0]["hits"] == []
    [negated_hit] = item["requirement_results"][0]["negated_hits"]
    context = negated_hit["span"]["text"]
    assert "Glucose3" in context
    assert any(cue in context.casefold() for cue in ("not", "không", "chưa"))
    assert context in report_text
    assert item["negated_evidence_spans"] == [negated_hit]
    assert result["proposed_total_score"] is None
    assert result["requires_lecturer_review"] is True


def test_affirmative_requirement_remains_met():
    result = _run("We used Glucose3 in the experiment.", [_checklist("uses-glucose3", "Glucose3")])
    [item] = result["checklist_results"]

    assert item["checklist_outcome"] == "MET"
    assert item["requirement_results"][0]["hits"]
    assert item["requirement_results"][0]["negated_hits"] == []
    assert result["proposed_total_score"] == 10.0


def test_positive_and_negated_mentions_of_same_requirement_abstain():
    result = _run(
        "Glucose3 was not used initially. Glucose3 was used in the final run.",
        [_checklist("uses-glucose3", "Glucose3")],
    )
    [item] = result["checklist_results"]

    assert item["verification_relation"] == "INSUFFICIENT"
    assert item["checklist_outcome"] == "CANNOT_ASSESS"
    assert item["reason_code"] == "CONFLICTING_REPORT_EVIDENCE"
    assert item["requirement_results"][0]["hits"]
    assert item["requirement_results"][0]["negated_hits"]


def test_negation_in_another_clause_does_not_cancel_support():
    result = _run(
        "We did not use MiniSat; Glucose3 was used in the final run.",
        [_checklist("uses-glucose3", "Glucose3")],
    )
    assert result["checklist_results"][0]["checklist_outcome"] == "MET"


def test_phrase_inside_longer_identifier_does_not_satisfy_requirement():
    result = _run(
        "We used Glucose3Plus in the experiment.",
        [_checklist("uses-glucose3", "Glucose3")],
    )
    assert result["checklist_results"][0]["checklist_outcome"] == "CANNOT_ASSESS"


def test_required_cannot_assess_with_another_met_item_withholds_score():
    result = _run(
        "We used BM25 for retrieval.",
        [
            _checklist("uses-bm25", "BM25"),
            _checklist("uses-glucose3", "Glucose3"),
        ],
    )

    assert [item["checklist_outcome"] for item in result["checklist_results"]] == [
        "MET",
        "CANNOT_ASSESS",
    ]
    [criterion] = result["criterion_results"]
    assert criterion["proposed_score"] is None
    assert criterion["requires_lecturer_review"] is True
    assert result["proposed_total_score"] is None
    assert result["requires_lecturer_review"] is True


def test_optional_cannot_assess_also_withholds_score_instead_of_counting_as_unmet():
    result = _run(
        "We used BM25 for retrieval.",
        [
            _checklist("uses-bm25", "BM25"),
            _checklist("uses-glucose3", "Glucose3", importance="OPTIONAL"),
        ],
    )
    [criterion] = result["criterion_results"]
    assert criterion["proposed_score"] is None
    assert criterion["score_reason"] == "UNRESOLVED_CHECKLIST_EVIDENCE"
    assert criterion["requires_lecturer_review"] is True
    assert result["proposed_total_score"] is None
    assert result["requires_lecturer_review"] is True


def test_only_optional_cannot_assess_has_no_proposed_score():
    result = _run(
        "The report does not mention the requested method.",
        [_checklist("uses-glucose3", "Glucose3", importance="OPTIONAL")],
        unknown_ratio_threshold=1.0,
    )
    [criterion] = result["criterion_results"]
    assert criterion["proposed_score"] is None
    assert result["proposed_total_score"] is None
    assert result["requires_lecturer_review"] is True


def test_assessable_subtotal_is_diagnostic_when_another_criterion_abstains():
    result = _run(
        "We used BM25 for retrieval.",
        [_checklist("uses-bm25", "BM25")],
        second_criterion_checklists=[_checklist("uses-glucose3", "Glucose3")],
    )
    assert [item["proposed_score"] for item in result["criterion_results"]] == [
        5.0,
        None,
    ]
    assert result["assessable_subtotal"] == 5.0
    assert result["proposed_total_score"] is None
    assert result["requires_lecturer_review"] is True
