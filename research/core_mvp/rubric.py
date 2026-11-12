"""Deterministic compiler for the core-MVP rubric format.

The compiler deliberately does not ask a language model to invent checklist
items.  For the feasibility run the rubric author supplies atomic checklist
items and the compiler validates and canonicalises them.  Automatic rubric
decomposition can later be evaluated as a separate, labelled component.
"""

from __future__ import annotations

from copy import deepcopy
import math
import re
import unicodedata
from typing import Any, Mapping

from research.offline_retrieval.common import canonical_json, sha256_text


_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
_MODES = {"LOCAL", "GRAPH"}
_IMPORTANCE = {"CORE", "REQUIRED", "OPTIONAL"}


def _string(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    normalised = " ".join(unicodedata.normalize("NFKC", value).split())
    if not normalised:
        raise ValueError(f"{field} must be non-empty")
    return normalised


def _identifier(value: Any, field: str) -> str:
    identifier = _string(value, field)
    if _IDENTIFIER.fullmatch(identifier) is None:
        raise ValueError(
            f"{field} must match {_IDENTIFIER.pattern!r}; got {identifier!r}"
        )
    return identifier


def _number(value: Any, field: str, *, minimum: float = 0.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be numeric")
    number = float(value)
    if not math.isfinite(number) or number < minimum:
        raise ValueError(f"{field} must be finite and >= {minimum}")
    return number


def _positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field} must be a positive integer")
    return value


def _compile_requirements(value: Any, field: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{field} must be a non-empty array")
    compiled: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        item_field = f"{field}[{index}]"
        if not isinstance(item, Mapping):
            raise ValueError(f"{item_field} must be an object")
        requirement_id = _identifier(
            item.get("requirement_id"), f"{item_field}.requirement_id"
        )
        if requirement_id in seen:
            raise ValueError(f"Duplicate requirement_id: {requirement_id}")
        seen.add(requirement_id)
        alternatives = item.get("any_of")
        if not isinstance(alternatives, list) or not alternatives:
            raise ValueError(f"{item_field}.any_of must be a non-empty array")
        canonical_alternatives: list[str] = []
        for alternative_index, alternative in enumerate(alternatives):
            phrase = _string(
                alternative,
                f"{item_field}.any_of[{alternative_index}]",
            )
            if phrase.casefold() not in {
                existing.casefold() for existing in canonical_alternatives
            }:
                canonical_alternatives.append(phrase)
        compiled.append(
            {
                "requirement_id": requirement_id,
                "description": _string(
                    item.get("description", requirement_id),
                    f"{item_field}.description",
                ),
                "any_of": canonical_alternatives,
            }
        )
    return compiled


def _compile_checklist(
    value: Any,
    *,
    criterion_id: str,
    index: int,
) -> dict[str, Any]:
    field = f"criteria[{criterion_id}].checklists[{index}]"
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be an object")
    checklist_id = _identifier(value.get("checklist_id"), f"{field}.checklist_id")
    mode = _string(value.get("mode"), f"{field}.mode").upper()
    if mode not in _MODES:
        raise ValueError(f"{field}.mode must be one of {sorted(_MODES)}")
    importance = _string(
        value.get("importance", "REQUIRED"), f"{field}.importance"
    ).upper()
    if importance not in _IMPORTANCE:
        raise ValueError(
            f"{field}.importance must be one of {sorted(_IMPORTANCE)}"
        )
    statement = _string(value.get("statement"), f"{field}.statement")
    query = _string(value.get("query", statement), f"{field}.query")
    requirements = _compile_requirements(
        value.get("requirements"), f"{field}.requirements"
    )
    if mode == "GRAPH" and len(requirements) < 2:
        raise ValueError(
            f"{field}: GRAPH checklist requires at least two evidence requirements"
        )
    raw_patterns = value.get("contradiction_patterns", [])
    if not isinstance(raw_patterns, list):
        raise ValueError(f"{field}.contradiction_patterns must be an array")
    patterns = [
        _string(pattern, f"{field}.contradiction_patterns[{pattern_index}]")
        for pattern_index, pattern in enumerate(raw_patterns)
    ]
    return {
        "checklist_id": checklist_id,
        "criterion_id": criterion_id,
        "statement": statement,
        "mode": mode,
        "importance": importance,
        "query": query,
        "requirements": requirements,
        "contradiction_patterns": patterns,
    }


def compile_rubric(rubric: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and compile an authored rubric into byte-stable checklists."""

    if not isinstance(rubric, Mapping):
        raise ValueError("Rubric must be a JSON object")
    schema_version = rubric.get("schema_version")
    if schema_version != 1:
        raise ValueError("rubric.schema_version must equal 1")
    rubric_id = _identifier(rubric.get("rubric_id"), "rubric.rubric_id")
    rubric_version = _string(rubric.get("version"), "rubric.version")
    max_score = _number(rubric.get("max_score"), "rubric.max_score", minimum=0.1)
    criteria = rubric.get("criteria")
    if not isinstance(criteria, list) or not criteria:
        raise ValueError("rubric.criteria must be a non-empty array")

    compiled_criteria: list[dict[str, Any]] = []
    seen_criteria: set[str] = set()
    seen_checklists: set[str] = set()
    for criterion_index, criterion in enumerate(criteria):
        field = f"rubric.criteria[{criterion_index}]"
        if not isinstance(criterion, Mapping):
            raise ValueError(f"{field} must be an object")
        if "levels" in criterion:
            raise ValueError(
                f"{field}.levels is not supported by the authored-checklist compiler; "
                "authored score levels require an explicit supported rule mapping"
            )
        criterion_id = _identifier(
            criterion.get("criterion_id"), f"{field}.criterion_id"
        )
        if criterion_id in seen_criteria:
            raise ValueError(f"Duplicate criterion_id: {criterion_id}")
        seen_criteria.add(criterion_id)
        checklist_values = criterion.get("checklists")
        if not isinstance(checklist_values, list) or not checklist_values:
            raise ValueError(f"{field}.checklists must be a non-empty array")
        compiled_checklists = [
            _compile_checklist(
                checklist,
                criterion_id=criterion_id,
                index=checklist_index,
            )
            for checklist_index, checklist in enumerate(checklist_values)
        ]
        for checklist in compiled_checklists:
            checklist_id = checklist["checklist_id"]
            if checklist_id in seen_checklists:
                raise ValueError(f"Duplicate checklist_id: {checklist_id}")
            seen_checklists.add(checklist_id)
        compiled_criteria.append(
            {
                "criterion_id": criterion_id,
                "title": _string(criterion.get("title"), f"{field}.title"),
                "weight": _number(
                    criterion.get("weight"), f"{field}.weight", minimum=0.1
                ),
                "checklists": compiled_checklists,
            }
        )

    weight_total = sum(criterion["weight"] for criterion in compiled_criteria)
    if not math.isclose(weight_total, max_score, rel_tol=0.0, abs_tol=1e-6):
        raise ValueError(
            "Sum of criterion weights must equal rubric.max_score; "
            f"got {weight_total} versus {max_score}"
        )

    raw_rules = rubric.get("decision_rules", {})
    if not isinstance(raw_rules, Mapping):
        raise ValueError("rubric.decision_rules must be an object")
    unable_ratio = _number(
        raw_rules.get("cannot_assess_ratio_threshold", 0.4),
        "rubric.decision_rules.cannot_assess_ratio_threshold",
    )
    if unable_ratio > 1.0:
        raise ValueError("cannot_assess_ratio_threshold must be <= 1")
    decision_rules = {
        "rule_version": _string(
            raw_rules.get("rule_version", "core-mvp-proportional-v0"),
            "rubric.decision_rules.rule_version",
        ),
        "cannot_assess_count_threshold": _positive_int(
            raw_rules.get("cannot_assess_count_threshold", 2),
            "rubric.decision_rules.cannot_assess_count_threshold",
        ),
        "cannot_assess_ratio_threshold": unable_ratio,
        "required_unmet_score": _number(
            raw_rules.get("required_unmet_score", 0.0),
            "rubric.decision_rules.required_unmet_score",
        ),
    }

    canonical = {
        "schema_version": 1,
        "compiler": {
            "name": "atomic-template-rubric-compiler",
            "version": "0.1.0",
            "automatic_decomposition": False,
        },
        "rubric_id": rubric_id,
        "rubric_version": rubric_version,
        "title": _string(rubric.get("title", rubric_id), "rubric.title"),
        "max_score": max_score,
        "decision_rules": decision_rules,
        "criteria": compiled_criteria,
    }
    canonical["compiled_sha256"] = sha256_text(canonical_json(canonical))
    canonical["compiled_id"] = (
        f"compiled-{rubric_id}-{canonical['compiled_sha256'][:16]}"
    )
    return deepcopy(canonical)
