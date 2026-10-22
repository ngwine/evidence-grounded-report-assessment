"""Exercise the declared output schemas against an actual synthetic MVP run."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from research.core_mvp.contracts import validate_assessment_report
from research.core_mvp.runner import run_core_mvp
from research.schema_validation import OutputSchemaError, validate_json_schema


FIXTURES = Path(__file__).parent / "fixtures" / "core_mvp"
SCHEMAS = Path(__file__).parents[1] / "schemas"


@pytest.fixture(scope="module")
def generated_reports(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    output_dir = tmp_path_factory.mktemp("json-schema-mvp")
    run_core_mvp(
        report_path=FIXTURES / "report.txt",
        source_paths=[FIXTURES / "source-overlap.txt", FIXTURES / "source-unrelated.txt"],
        rubric_path=FIXTURES / "rubric.json",
        config_path=FIXTURES / "config-bm25-only.json",
        output_dir=output_dir,
        pipeline="both",
    )
    return {
        "similarity": json.loads((output_dir / "similarity-report.json").read_text(encoding="utf-8")),
        "assessment": json.loads((output_dir / "assessment-report.json").read_text(encoding="utf-8")),
    }


def _first_evidence(assessment: dict) -> dict:
    return next(
        entry
        for checklist in assessment["checklist_results"]
        for entry in checklist["evidence_pack"]
    )


def test_checked_in_schemas_use_valid_draft_2020_12() -> None:
    for path in SCHEMAS.glob("*.schema.json"):
        schema = json.loads(path.read_text(encoding="utf-8"))
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        Draft202012Validator.check_schema(schema)


def test_generated_similarity_assessment_and_nested_evidence_validate(generated_reports: dict) -> None:
    for kind in ("similarity", "assessment"):
        validate_json_schema(generated_reports[kind], kind=kind)
    assessment = generated_reports["assessment"]
    evidence_items = [
        item
        for checklist in assessment["checklist_results"]
        for item in checklist["evidence_pack"]
    ]
    assert evidence_items, "The generated fixture must exercise the Evidence Pack $ref"
    for item in evidence_items:
        validate_json_schema(item, kind="evidence")


@pytest.mark.parametrize("kind", ["similarity", "assessment"])
def test_report_schema_rejects_wrong_version(generated_reports: dict, kind: str) -> None:
    report = deepcopy(generated_reports[kind])
    report["schema_version"] = 2
    with pytest.raises(OutputSchemaError, match=r"schema_version.*const"):
        validate_json_schema(report, kind=kind)


@pytest.mark.parametrize(
    ("kind", "wrong_kind"),
    [("similarity", "assessment"), ("assessment", "similarity")],
)
def test_report_schema_rejects_cross_type_output(
    generated_reports: dict, kind: str, wrong_kind: str
) -> None:
    with pytest.raises(OutputSchemaError):
        validate_json_schema(generated_reports[wrong_kind], kind=kind)


def test_similarity_schema_rejects_missing_field_and_wrong_boolean(generated_reports: dict) -> None:
    similarity = deepcopy(generated_reports["similarity"])
    del similarity["matches"]
    with pytest.raises(OutputSchemaError, match=r"required constraint"):
        validate_json_schema(similarity, kind="similarity")

    similarity = deepcopy(generated_reports["similarity"])
    assert similarity["matches"]
    similarity["matches"][0]["selected_for_document_coverage"] = "false"
    with pytest.raises(OutputSchemaError, match=r"selected_for_document_coverage.*type"):
        validate_json_schema(similarity, kind="similarity")


def test_nested_ref_rejects_invalid_evidence_and_standalone_matches(generated_reports: dict) -> None:
    assessment = deepcopy(generated_reports["assessment"])
    target = next(
        item
        for checklist in assessment["checklist_results"]
        for item in checklist["evidence_pack"]
    )
    target["rank"] = 0
    with pytest.raises(OutputSchemaError, match=r"rank.*minimum"):
        validate_json_schema(assessment, kind="assessment")
    with pytest.raises(OutputSchemaError, match=r"rank.*minimum"):
        validate_json_schema(target, kind="evidence")


def test_evidence_schema_rejects_missing_source_spans_without_leaking_input(generated_reports: dict) -> None:
    evidence = deepcopy(_first_evidence(generated_reports["assessment"]))
    del evidence["source_spans"]
    with pytest.raises(OutputSchemaError, match=r"required constraint"):
        validate_json_schema(evidence, kind="evidence")

    evidence = deepcopy(_first_evidence(generated_reports["assessment"]))
    evidence["rank"] = "PRIVATE_REPORT_TEXT_DO_NOT_LOG"
    with pytest.raises(OutputSchemaError) as exc_info:
        validate_json_schema(evidence, kind="evidence")
    assert "PRIVATE_REPORT_TEXT_DO_NOT_LOG" not in str(exc_info.value)


def test_evidence_schema_requires_version_and_parser_source_coordinates(generated_reports: dict) -> None:
    evidence = deepcopy(_first_evidence(generated_reports["assessment"]))
    evidence["document_version_id"] = None
    with pytest.raises(OutputSchemaError, match=r"document_version_id.*type"):
        validate_json_schema(evidence, kind="evidence")

    evidence = deepcopy(_first_evidence(generated_reports["assessment"]))
    evidence["source_spans"] = [{}]
    with pytest.raises(OutputSchemaError, match=r"source_spans\[0\].*required"):
        validate_json_schema(evidence, kind="evidence")

    evidence = deepcopy(_first_evidence(generated_reports["assessment"]))
    evidence["source_spans"][0]["locator"] = {}
    with pytest.raises(OutputSchemaError, match=r"locator.*minProperties"):
        validate_json_schema(evidence, kind="evidence")


def test_structural_schema_does_not_replace_runtime_semantic_checks(generated_reports: dict) -> None:
    assessment = deepcopy(generated_reports["assessment"])
    item = assessment["checklist_results"][0]
    item["verification_relation"] = "CONTRADICTED"
    item["checklist_outcome"] = "MET"
    validate_json_schema(assessment, kind="assessment")
    with pytest.raises(ValueError, match="Inconsistent relation/outcome"):
        validate_assessment_report(assessment)


def test_unknown_schema_kind_fails_closed() -> None:
    with pytest.raises(ValueError, match="Unknown output schema kind"):
        validate_json_schema({}, kind="rubric")
