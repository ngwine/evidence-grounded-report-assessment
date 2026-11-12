"""Contract tests for the authored-rubric compiler used by Pipeline 2."""

from __future__ import annotations

from copy import deepcopy

import pytest

from research.core_mvp.rubric import compile_rubric


def _rubric() -> dict:
    return {
        "schema_version": 1,
        "rubric_id": "technical-report-v1",
        "version": "1.0.0",
        "title": "Technical report",
        "max_score": 10,
        "decision_rules": {
            "cannot_assess_count_threshold": 2,
            "cannot_assess_ratio_threshold": 0.4,
            "required_unmet_score": 0,
        },
        "criteria": [
            {
                "criterion_id": "METHOD",
                "title": "Method",
                "weight": 6,
                "checklists": [
                    {
                        "checklist_id": "METHOD.LOCAL.1",
                        "statement": "The method is identified.",
                        "mode": "local",
                        "importance": "required",
                        "requirements": [
                            {
                                "requirement_id": "method-name",
                                "description": "Named method",
                                "any_of": ["BM25", "BM25", "  dense retrieval  "],
                            }
                        ],
                    }
                ],
            },
            {
                "criterion_id": "TRACE",
                "title": "Traceability",
                "weight": 4,
                "checklists": [
                    {
                        "checklist_id": "TRACE.GRAPH.1",
                        "statement": "The result is linked to evidence.",
                        "mode": "GRAPH",
                        "importance": "CORE",
                        "query": "result evidence provenance",
                        "requirements": [
                            {
                                "requirement_id": "result",
                                "any_of": ["result"],
                            },
                            {
                                "requirement_id": "evidence",
                                "any_of": ["evidence", "source span"],
                            },
                        ],
                    }
                ],
            },
        ],
    }


def test_compiler_is_byte_stable_and_canonicalises_authored_values():
    first = compile_rubric(_rubric())
    second = compile_rubric(deepcopy(_rubric()))

    assert first == second
    assert first["compiled_id"].endswith(first["compiled_sha256"][:16])
    assert first["compiler"]["automatic_decomposition"] is False
    local = first["criteria"][0]["checklists"][0]
    assert local["mode"] == "LOCAL"
    assert local["importance"] == "REQUIRED"
    assert local["requirements"][0]["any_of"] == ["BM25", "dense retrieval"]


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda value: value["criteria"][1]["checklists"][0].update(
                {"mode": "REMOTE"}
            ),
            "mode must be one of",
        ),
        (
            lambda value: value["criteria"][1]["checklists"][0].update(
                {"requirements": [value["criteria"][1]["checklists"][0]["requirements"][0]]}
            ),
            "GRAPH checklist requires",
        ),
        (
            lambda value: value["criteria"][1].update({"criterion_id": "METHOD"}),
            "Duplicate criterion_id",
        ),
        (
            lambda value: value.update({"max_score": 9}),
            "Sum of criterion weights",
        ),
    ],
)
def test_compiler_rejects_ambiguous_or_inconsistent_rubrics(mutation, message):
    value = _rubric()
    mutation(value)
    with pytest.raises(ValueError, match=message):
        compile_rubric(value)


def test_compiler_rejects_duplicate_checklist_ids_across_criteria():
    value = _rubric()
    value["criteria"][1]["checklists"][0]["checklist_id"] = "METHOD.LOCAL.1"

    with pytest.raises(ValueError, match="Duplicate checklist_id"):
        compile_rubric(value)
