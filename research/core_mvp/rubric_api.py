"""Explicit OpenAPI RubricDefinition -> executable core-v0 compiler mapping.

This adapter does not implement rubric CRUD, version persistence or publish.
It prevents the draft API's authoring fields from being silently inferred or
dropped when an authorized caller eventually compiles a versioned draft.
"""

from __future__ import annotations

from typing import Any, Mapping

from .rubric import compile_rubric


_DEFINITION_FIELDS = frozenset({"max_score", "criteria", "decision_rules"})
_CRITERION_FIELDS = frozenset({
    "criterion_key", "title", "weight", "scoring_mode", "checklists", "levels",
})
_CHECKLIST_FIELDS = frozenset({
    "checklist_key", "statement", "requirement", "evidence_mode", "importance",
    "query", "requirements", "contradiction_patterns",
})
_REQUIREMENT_FIELDS = frozenset({"requirement_id", "description", "any_of"})
_RULE_FIELDS = frozenset({
    "rule_version", "cannot_assess_count_threshold",
    "cannot_assess_ratio_threshold", "required_unmet_score",
})


def _object(value: Any, path: str, *, allowed: frozenset[str], required: frozenset[str]) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{path} must be an object")
    unknown = set(value) - allowed
    if unknown:
        raise ValueError(f"{path}.{sorted(unknown)[0]} is not supported by the v1 compiler")
    missing = required - set(value)
    if missing:
        raise ValueError(f"{path}.{sorted(missing)[0]} is required")
    return value


def _array(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{path} must be a non-empty array")
    return value


def compile_api_rubric_definition(
    *, rubric_key: str, title: str, rubric_version: str,
    definition: Mapping[str, Any],
) -> dict[str, Any]:
    """Compile a versioned API definition; reject unsupported authored data.

    ``rubric_version`` must be supplied by the version lifecycle, never guessed
    from a request timestamp. The published version must store both the exact
    authoring definition and the returned compiled SHA/ID.
    """

    definition = _object(
        definition, "definition", allowed=_DEFINITION_FIELDS,
        required=frozenset({"max_score", "criteria"}),
    )
    criteria: list[dict[str, Any]] = []
    for criterion_index, raw_criterion in enumerate(_array(definition["criteria"], "definition.criteria")):
        path = f"definition.criteria[{criterion_index}]"
        criterion = _object(
            raw_criterion, path, allowed=_CRITERION_FIELDS,
            required=frozenset({"criterion_key", "title", "weight", "scoring_mode", "checklists"}),
        )
        if criterion["scoring_mode"] != "PROPORTIONAL_CHECKLIST_V0":
            raise ValueError(f"{path}.scoring_mode is not executable by the v1 compiler")
        if "levels" in criterion:
            levels = criterion["levels"]
            if not isinstance(levels, list):
                raise ValueError(f"{path}.levels must be an array")
            if levels:
                raise ValueError(f"{path}.levels are authoring-only; v1 cannot execute level scoring")

        checklists: list[dict[str, Any]] = []
        for checklist_index, raw_checklist in enumerate(_array(criterion["checklists"], f"{path}.checklists")):
            item_path = f"{path}.checklists[{checklist_index}]"
            checklist = _object(
                raw_checklist, item_path, allowed=_CHECKLIST_FIELDS,
                required=frozenset({"checklist_key", "statement", "evidence_mode", "requirements"}),
            )
            if "requirement" in checklist:
                raise ValueError(f"{item_path}.requirement is legacy free text; authored requirements are required")
            requirements: list[dict[str, Any]] = []
            for requirement_index, raw_requirement in enumerate(
                _array(checklist["requirements"], f"{item_path}.requirements")
            ):
                requirement_path = f"{item_path}.requirements[{requirement_index}]"
                authored = _object(
                    raw_requirement, requirement_path, allowed=_REQUIREMENT_FIELDS,
                    required=frozenset({"requirement_id", "any_of"}),
                )
                requirement = {
                    "requirement_id": authored["requirement_id"],
                    "any_of": authored["any_of"],
                }
                if "description" in authored:
                    requirement["description"] = authored["description"]
                requirements.append(requirement)
            compiled_checklist = {
                "checklist_id": checklist["checklist_key"],
                "statement": checklist["statement"],
                "mode": checklist["evidence_mode"],
                "requirements": requirements,
                # These documented defaults are explicit at this boundary.
                "importance": checklist.get("importance", "REQUIRED"),
                "query": checklist.get("query", checklist["statement"]),
                "contradiction_patterns": checklist.get("contradiction_patterns", []),
            }
            checklists.append(compiled_checklist)
        criteria.append({
            "criterion_id": criterion["criterion_key"],
            "title": criterion["title"],
            "weight": criterion["weight"],
            "checklists": checklists,
        })

    rules = _object(
        definition.get("decision_rules", {}), "definition.decision_rules",
        allowed=_RULE_FIELDS, required=frozenset(),
    )
    return compile_rubric({
        "schema_version": 1,
        "rubric_id": rubric_key,
        "version": rubric_version,
        "title": title,
        "max_score": definition["max_score"],
        "criteria": criteria,
        "decision_rules": dict(rules),
    })
