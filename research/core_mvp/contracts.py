"""Runtime contract checks for the two inspectable core-MVP reports.

The JSON Schemas under ``research/schemas`` document the wire format.  These
checks enforce the safety-critical invariants without adding a runtime schema
library to the offline runner.
"""

from __future__ import annotations

import math
import re
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
        if match.get("similarity_type") == "PARAPHRASE":
            if (not value["semantic_classifier_available"]
                    or match.get("classification_status") != "MODEL_SUPPORTED_SEMANTIC_MATCH"
                    or match.get("semantic_verification_status") != "PARAPHRASE_SUPPORTED"):
                raise ValueError("PARAPHRASE requires an explicit model-supported semantic decision")
            evidence = _array(match.get("semantic_evidence"), "semantic_evidence")
            if not evidence:
                raise ValueError("PARAPHRASE requires compared sentence evidence")
            for entry in evidence:
                for side in ("report", "source"):
                    span = _mapping(entry.get(side), f"semantic_evidence.{side}")
                    _string(span.get("text"), f"semantic_evidence.{side}.text")
                    start = _non_negative_int(span.get("normalized_start"), "semantic_start")
                    end = _non_negative_int(span.get("normalized_end"), "semantic_end")
                    if end <= start:
                        raise ValueError("Semantic evidence requires a nonempty range")
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


def _assessment_proof(
    raw_hit: Any, evidence_by_id: Mapping[str, Mapping[str, Any]], field: str,
) -> None:
    hit = _mapping(raw_hit, field)
    evidence_id = _string(hit.get("evidence_id"), f"{field}.evidence_id")
    if evidence_id not in evidence_by_id:
        raise ValueError(f"{field} references evidence outside its Evidence Pack")
    evidence = evidence_by_id[evidence_id]
    span = _mapping(hit.get("span"), f"{field}.span")
    if any(span.get(key) != evidence[key] for key in ("chunk_id", "document_id")):
        raise ValueError(f"{field} proof does not match its evidence chunk/document")
    for key in ("document_version", "document_version_id"):
        if key in span and span[key] != evidence["document_version_id"]:
            raise ValueError(f"{field} proof has a different document version")
    start = _non_negative_int(span.get("normalized_start"), f"{field}.normalized_start")
    end = _non_negative_int(span.get("normalized_end"), f"{field}.normalized_end")
    text = _string(span.get("text"), f"{field}.text")
    if end <= start or len(text) != end - start:
        raise ValueError(f"{field} proof requires a nonempty consistent text range")
    locators = _array(span.get("source_spans"), f"{field}.source_spans")
    if not locators:
        raise ValueError(f"{field} proof requires source spans")
    covered_ranges: list[tuple[int, int]] = []
    for raw_locator in locators:
        locator = _mapping(raw_locator, f"{field}.source_span")
        if not any(
            all(locator.get(key) == value for key, value in original.items())
            for original in evidence["source_spans"]
        ):
            raise ValueError(f"{field} proof source span differs from its Evidence Pack")
        source_start = _non_negative_int(locator.get("chunk_normalized_char_start"), f"{field}.source_start")
        source_end = _non_negative_int(locator.get("chunk_normalized_char_end"), f"{field}.source_end")
        if max(start, source_start) >= min(end, source_end):
            raise ValueError(f"{field} proof does not overlap its source span")
        covered_ranges.append((max(start, source_start), min(end, source_end)))
        for key, expected in (
            ("matched_chunk_normalized_start", max(start, source_start)),
            ("matched_chunk_normalized_end", min(end, source_end)),
        ):
            if key in locator and locator[key] != expected:
                raise ValueError(f"{field} proof has inconsistent matched source offsets")
    covered_end = start
    for left, right in sorted(covered_ranges):
        if text[covered_end - start:left - start].strip():
            raise ValueError(f"{field} proof contains text outside its source spans")
        covered_end = max(covered_end, right)
    if text[covered_end - start:].strip():
        raise ValueError(f"{field} proof contains text outside its source spans")


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
    llm_mode = value.get("verification_method") == "LOCAL_LLM_REQUIREMENT_VERIFIER_V1"
    if llm_mode:
        _validate_llm_provenance(value)
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
        evidence_by_id: dict[str, Mapping[str, Any]] = {}
        for evidence_index, raw_evidence in enumerate(
            _array(result.get("evidence_pack"), f"checklist_results[{index}].evidence_pack")
        ):
            evidence = _mapping(raw_evidence, f"evidence_pack[{evidence_index}]")
            for field in ("evidence_id", "chunk_id", "document_id", "document_version_id"):
                _string(evidence.get(field), f"evidence_pack[{evidence_index}].{field}")
            if evidence["evidence_id"] in evidence_by_id:
                raise ValueError("Evidence Pack evidence IDs must be unique")
            evidence_by_id[evidence["evidence_id"]] = evidence
            if not _array(evidence.get("source_spans"), f"evidence_pack[{evidence_index}].source_spans"):
                raise ValueError("Evidence Pack entries must retain at least one source span")
            for raw_span in evidence["source_spans"]:
                span = _mapping(raw_span, "evidence_pack.source_span")
                if any(span.get(key) != evidence[key] for key in ("document_id", "document_version_id")):
                    raise ValueError("Evidence Pack source span has a different document/version")

        required_proof = {"MET": "matched_evidence_spans", "UNMET": "contradiction_hits"}.get(outcome)
        if required_proof and not result.get(required_proof):
            raise ValueError(f"{outcome} requires nonempty {required_proof}")
        for field in (
            "matched_evidence_spans", "contradiction_hits", "negated_evidence_spans",
            "non_asserted_evidence_spans", "withheld_contradiction_spans",
        ):
            # Newer diagnostic collections are optional on historical reports.
            for hit in _array(result.get(field, []), field):
                _assessment_proof(hit, evidence_by_id, field)
        for requirement in _array(result.get("requirement_results", []), "requirement_results"):
            requirement = _mapping(requirement, "requirement_results.entry")
            if outcome == "MET" and not requirement.get("hits"):
                raise ValueError("MET requires supporting hits for every listed requirement")
            for field in ("hits", "negated_hits", "non_asserted_hits"):
                for hit in _array(requirement.get(field, []), f"requirement_results.{field}"):
                    _assessment_proof(hit, evidence_by_id, f"requirement_results.{field}")
    if llm_mode:
        _validate_llm_decisions(value, results)


def _validate_llm_provenance(report: Mapping[str, Any]) -> None:
    """New semantic outputs require model/prompt provenance; old reports stay valid."""
    metadata = _mapping(report.get("verification_metadata"), "verification_metadata")
    if metadata.get("backend") != "ollama":
        raise ValueError("LLM assessment requires local model provenance")
    _string(metadata.get("model"), "verification_metadata.model")
    if not isinstance(metadata.get("digest"), str) or not re.fullmatch(
        r"sha256:[0-9a-f]{64}", metadata["digest"]
    ):
        raise ValueError("LLM assessment requires an immutable model digest")
    for key in ("prompt_sha256", "output_schema_sha256", "policy_sha256"):
        if not isinstance(metadata.get(key), str) or not re.fullmatch(r"[0-9a-f]{64}", metadata[key]):
            raise ValueError(f"LLM assessment requires {key}")
    if (metadata.get("verification_method") != report["verification_method"]
            or metadata.get("automatic_fallback_to_phrase_verifier") is not False
            or report.get("human_review_required_before_publication") is not True):
        raise ValueError("LLM assessment verification and publication boundaries are inconsistent")


def _validate_llm_decisions(report: Mapping[str, Any], results: Sequence[Any]) -> None:
    """Bind every semantic relation to the authored requirements and code score."""
    compiled = _mapping(report.get("compiled_rubric"), "compiled_rubric")
    authored = {}
    for criterion in _array(compiled.get("criteria"), "compiled_rubric.criteria"):
        for checklist in _array(criterion.get("checklists"), "compiled_rubric.checklists"):
            identifier = _string(checklist.get("checklist_id"), "compiled_checklist.checklist_id")
            if identifier in authored:
                raise ValueError("LLM assessment compiled checklist IDs must be unique")
            authored[identifier] = checklist
    returned = [item["checklist_id"] for item in results]
    if len(set(returned)) != len(returned) or set(returned) != set(authored):
        raise ValueError("LLM assessment must retain every authored checklist exactly once")
    for item in results:
        checklist = authored[item["checklist_id"]]
        if item.get("criterion_id") != checklist.get("criterion_id"):
            raise ValueError("LLM assessment changed a checklist's criterion")
        requirements = {
            _string(r.get("requirement_id"), "compiled_requirement.requirement_id"): r
            for r in _array(checklist.get("requirements"), "compiled_checklist.requirements")
        }
        if not requirements:
            raise ValueError("LLM assessment requires nonempty authored requirements")
        decisions = _array(item.get("requirement_results"), "LLM requirement_results")
        ids = [_string(r.get("requirement_id"), "LLM requirement_id") for r in decisions]
        if len(ids) != len(set(ids)) or set(ids) != set(requirements):
            raise ValueError("LLM assessment must retain every authored requirement exactly once")
        relations = []
        flat_support = item.get("matched_evidence_spans", [])
        flat_contradictions = item.get("contradiction_hits", [])
        for decision in decisions:
            relation = decision.get("relation")
            if relation not in {"SUPPORTED", "CONTRADICTED", "INSUFFICIENT"}:
                raise ValueError("LLM requirement relation is missing or invalid")
            if (type(decision.get("satisfied")) is not bool
                    or decision["satisfied"] != (relation == "SUPPORTED")):
                raise ValueError("LLM requirement satisfaction disagrees with its relation")
            if relation == "SUPPORTED":
                if not decision.get("hits") or any(hit not in flat_support for hit in decision["hits"]):
                    raise ValueError("LLM supported requirement needs linked supporting proof")
            elif decision.get("hits"):
                raise ValueError("LLM unsupported requirement cannot retain supporting hits")
            if relation == "CONTRADICTED" and not any(
                hit.get("requirement_id") == decision["requirement_id"] for hit in flat_contradictions
            ):
                raise ValueError("LLM contradicted requirement needs linked contradiction proof")
            relations.append(relation)
        decision_map = {r["requirement_id"]: r["relation"] for r in decisions}
        for proof in flat_support:
            if decision_map.get(proof.get("requirement_id")) != "SUPPORTED":
                raise ValueError("LLM supporting proof is detached from its requirement relation")
        for proof in flat_contradictions:
            if decision_map.get(proof.get("requirement_id")) != "CONTRADICTED":
                raise ValueError("LLM contradiction proof is detached from its requirement relation")
        expected = (
            ("CONTRADICTED", "UNMET") if "CONTRADICTED" in relations
            else ("SUPPORTED", "MET") if all(r == "SUPPORTED" for r in relations)
            else ("INSUFFICIENT", "CANNOT_ASSESS")
        )
        if (item["verification_relation"], item["checklist_outcome"]) != expected:
            raise ValueError("LLM checklist decision disagrees with its requirement relations")
        if (type(item.get("requirements_total")) is not int
                or item["requirements_total"] != len(requirements)
                or type(item.get("requirements_satisfied")) is not int
                or item["requirements_satisfied"] != relations.count("SUPPORTED")):
            raise ValueError("LLM requirement counts are inconsistent")
    # A language-model answer never owns scores, even after serialization.
    from .assessment import _score_criteria

    criteria, total, subtotal = _score_criteria(compiled, results)
    if (report.get("criterion_results") != criteria
            or report.get("proposed_total_score") != total
            or report.get("assessable_subtotal") != subtotal
            or report.get("max_score") != compiled.get("max_score")
            or report.get("requires_lecturer_review") != (
                total is None or any(c["requires_lecturer_review"] for c in criteria)
            )):
        raise ValueError("LLM assessment scores must match deterministic rubric rules")
