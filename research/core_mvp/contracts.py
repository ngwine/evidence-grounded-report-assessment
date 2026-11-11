"""Runtime contract checks for the two inspectable core-MVP reports.

The JSON Schemas under ``research/schemas`` document the wire format.  These
checks enforce the safety-critical invariants without adding a runtime schema
library to the offline runner.
"""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be an object")
    return value


def _array(value: Any, field: str) -> Sequence[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError(f"{field} must be an array")
    return value


def _string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _non_negative_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return value


def _percentage_or_none(value: Any, field: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be numeric or null")
    number = float(value)
    if not math.isfinite(number) or not 0.0 <= number <= 100.0:
        raise ValueError(f"{field} must be in [0, 100]")
    return number


def validate_similarity_report(report: Mapping[str, Any]) -> None:
    value = _mapping(report, "similarity_report")
    if value.get("schema_version") != 1:
        raise ValueError("similarity_report.schema_version must equal 1")
    _string(value.get("pipeline"), "similarity_report.pipeline")
    _string(value.get("classification_policy"), "similarity_report.classification_policy")
    if not isinstance(value.get("semantic_classifier_available"), bool):
        raise ValueError("semantic_classifier_available must be boolean")
    for field in ("report_chunk_count", "source_chunk_count", "total_report_tokens"):
        _non_negative_int(value.get(field), f"similarity_report.{field}")
    for field in (
        "flagged_passage_coverage_percentage",
        "provisional_review_passage_coverage_percentage",
        "exact_match_coverage_percentage",
        "calibrated_similarity_percentage",
    ):
        _percentage_or_none(value.get(field), f"similarity_report.{field}")

    for index, raw_match in enumerate(_array(value.get("matches"), "similarity_report.matches")):
        match = _mapping(raw_match, f"similarity_report.matches[{index}]")
        for field in ("report_chunk_id", "source_chunk_id", "source_document_id"):
            _string(match.get(field), f"similarity_report.matches[{index}].{field}")
        for field in ("selected_for_manual_review", "selected_for_document_coverage"):
            if not isinstance(match.get(field), bool):
                raise ValueError(f"similarity_report.matches[{index}].{field} must be boolean")
        if match["selected_for_document_coverage"]:
            if match.get("similarity_type") != "VERBATIM":
                raise ValueError("Only evidence-backed VERBATIM matches may contribute to coverage")
            alignment = _mapping(match.get("alignment"), f"similarity_report.matches[{index}].alignment")
            if alignment.get("kind") != "EXACT_SUBSTRING":
                raise ValueError("Coverage match must carry an EXACT_SUBSTRING alignment")
            for side in ("report", "source"):
                span = _mapping(alignment.get(side), f"alignment.{side}")
                if not _array(span.get("source_spans"), f"alignment.{side}.source_spans"):
                    raise ValueError(f"alignment.{side}.source_spans must be non-empty")


def validate_assessment_report(report: Mapping[str, Any]) -> None:
    value = _mapping(report, "assessment_report")
    if value.get("schema_version") != 1:
        raise ValueError("assessment_report.schema_version must equal 1")
    _string(value.get("pipeline"), "assessment_report.pipeline")
    if not isinstance(value.get("requires_lecturer_review"), bool):
        raise ValueError("assessment_report.requires_lecturer_review must be boolean")
    if value["requires_lecturer_review"] and value.get("proposed_total_score") is not None:
        raise ValueError("A report requiring lecturer review must not propose a total score")

    relation_to_outcome = {
        "SUPPORTED": "MET",
        "CONTRADICTED": "UNMET",
        "INSUFFICIENT": "CANNOT_ASSESS",
    }
    results = _array(value.get("checklist_results"), "assessment_report.checklist_results")
    for index, raw_result in enumerate(results):
        result = _mapping(raw_result, f"assessment_report.checklist_results[{index}]")
        _string(result.get("checklist_id"), f"checklist_results[{index}].checklist_id")
        relation = result.get("verification_relation")
        outcome = result.get("checklist_outcome")
        if relation not in relation_to_outcome:
            raise ValueError(f"Invalid verification relation: {relation!r}")
        if outcome != relation_to_outcome[relation]:
            raise ValueError(f"Inconsistent relation/outcome: {relation!r}/{outcome!r}")
        _string(result.get("reason_code"), f"checklist_results[{index}].reason_code")
        _string(result.get("rationale"), f"checklist_results[{index}].rationale")
        for evidence_index, raw_evidence in enumerate(
            _array(result.get("evidence_pack"), f"checklist_results[{index}].evidence_pack")
        ):
            evidence = _mapping(raw_evidence, f"evidence_pack[{evidence_index}]")
            for field in ("evidence_id", "chunk_id", "document_id"):
                _string(evidence.get(field), f"evidence_pack[{evidence_index}].{field}")
            if not _array(evidence.get("source_spans"), f"evidence_pack[{evidence_index}].source_spans"):
                raise ValueError("Evidence Pack entries must retain at least one source span")
