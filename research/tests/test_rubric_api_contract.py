"""OpenAPI authoring contract must map losslessly to the v1 rubric compiler."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from jsonschema import Draft202012Validator
import pytest
import yaml

from research.core_mvp.rubric_api import compile_api_rubric_definition


OPENAPI = Path(__file__).parents[2] / "docs" / "api" / "openapi-v1.yaml"


def _request() -> dict:
    return {
        "rubric_key": "technical-report",
        "title": "Technical report",
        "definition": {
            "max_score": 10.0,
            "decision_rules": {
                "rule_version": "authored-v1",
                "cannot_assess_count_threshold": 2,
                "cannot_assess_ratio_threshold": 0.4,
                "required_unmet_score": 0.0,
            },
            "criteria": [{
                "criterion_key": "C1",
                "title": "Evidence quality",
                "weight": 10.0,
                "scoring_mode": "PROPORTIONAL_CHECKLIST_V0",
                "checklists": [{
                    "checklist_key": "C1.1",
                    "statement": "Report result is supported by a method and a source.",
                    "evidence_mode": "GRAPH",
                    "importance": "CORE",
                    "query": "method result source",
                    "requirements": [
                        {
                            "requirement_id": "method",
                            "description": "Method is named",
                            "any_of": ["BM25", "dense retrieval"],
                        },
                        {
                            "requirement_id": "source",
                            "description": "Source is identified",
                            "any_of": ["source document"],
                        },
                    ],
                    "contradiction_patterns": ["source unavailable"],
                }],
            }],
        },
    }


def _validator(component: str) -> Draft202012Validator:
    document = yaml.safe_load(OPENAPI.read_text(encoding="utf-8"))
    assert document["openapi"].startswith("3.1.")
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "components": document["components"],
        "$ref": f"#/components/schemas/{component}",
    }
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _compile(request: dict, version: str = "1") -> dict:
    return compile_api_rubric_definition(
        rubric_key=request["rubric_key"], title=request["title"],
        rubric_version=version, definition=request["definition"],
    )


def test_openapi_request_compiles_to_stable_versioned_rubric_without_field_loss() -> None:
    request = _request()
    _validator("CreateRubricRequest").validate(request)
    first = _compile(request)
    assert first == _compile(deepcopy(request))
    assert first["rubric_id"] == "technical-report"
    assert first["rubric_version"] == "1"
    assert first["compiled_id"].endswith(first["compiled_sha256"][:16])
    assert first["decision_rules"]["rule_version"] == "authored-v1"
    criterion = first["criteria"][0]
    assert criterion["criterion_id"] == "C1"
    checklist = criterion["checklists"][0]
    assert checklist["checklist_id"] == "C1.1"
    assert checklist["statement"] == request["definition"]["criteria"][0]["checklists"][0]["statement"]
    assert checklist["mode"] == "GRAPH"
    assert checklist["importance"] == "CORE"
    assert checklist["query"] == "method result source"
    assert checklist["requirements"][0]["any_of"] == ["BM25", "dense retrieval"]
    assert checklist["contradiction_patterns"] == ["source unavailable"]
    assert _compile(request, version="2")["compiled_sha256"] != first["compiled_sha256"]


def test_openapi_definition_can_be_used_for_draft_replace() -> None:
    _validator("RubricDefinition").validate(_request()["definition"])


def test_legacy_free_text_graph_request_is_rejected_not_inferred() -> None:
    request = _request()
    checklist = request["definition"]["criteria"][0]["checklists"][0]
    checklist["requirement"] = "Method and source are consistent."
    del checklist["requirements"]
    assert not _validator("CreateRubricRequest").is_valid(request)
    with pytest.raises(ValueError, match=r"checklists\[0\].requirements is required"):
        _compile(request)


def test_legacy_requirement_even_with_structured_items_is_not_silently_dropped() -> None:
    request = _request()
    request["definition"]["criteria"][0]["checklists"][0]["requirement"] = "Extra condition"
    assert _validator("CreateRubricRequest").is_valid(request)  # Draft authoring compatibility.
    with pytest.raises(ValueError, match=r"checklists\[0\].requirement is legacy free text"):
        _compile(request)


def test_graph_checklist_requires_two_authored_evidence_requirements() -> None:
    request = _request()
    request["definition"]["criteria"][0]["checklists"][0]["requirements"].pop()
    assert _validator("CreateRubricRequest").is_valid(request)
    with pytest.raises(ValueError, match="GRAPH checklist requires at least two"):
        _compile(request)


def test_nonempty_levels_are_authoring_only_and_rejected_before_execution() -> None:
    request = _request()
    request["definition"]["criteria"][0]["levels"] = [
        {"level_key": "GOOD", "score": 10, "rule": "All requirements met"}
    ]
    assert _validator("CreateRubricRequest").is_valid(request)
    with pytest.raises(ValueError, match=r"criteria\[0\].levels are authoring-only"):
        _compile(request)


def test_total_weight_and_unknown_fields_fail_with_field_specific_errors() -> None:
    request = _request()
    request["definition"]["max_score"] = 9
    with pytest.raises(ValueError, match="Sum of criterion weights"):
        _compile(request)

    request = _request()
    request["definition"]["criteria"][0]["checklists"][0]["hidden_rule"] = "ignore"
    assert not _validator("CreateRubricRequest").is_valid(request)
    with pytest.raises(ValueError, match=r"checklists\[0\].hidden_rule is not supported"):
        _compile(request)


def test_optional_defaults_are_explicit_and_deterministic() -> None:
    request = _request()
    checklist = request["definition"]["criteria"][0]["checklists"][0]
    del checklist["importance"]
    del checklist["query"]
    del checklist["contradiction_patterns"]
    compiled = _compile(request)["criteria"][0]["checklists"][0]
    assert compiled["importance"] == "REQUIRED"
    assert compiled["query"] == checklist["statement"]
    assert compiled["contradiction_patterns"] == []
