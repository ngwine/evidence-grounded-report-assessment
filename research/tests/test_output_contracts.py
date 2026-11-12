"""Tests for output contracts shared by runner, backend and UI."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from research.core_mvp.contracts import (
    validate_assessment_report,
    validate_similarity_report,
)
from research.core_mvp.runner import run_core_mvp


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "core_mvp"
SCHEMA_DIR = Path(__file__).parents[1] / "schemas"


def _reports(tmp_path: Path) -> tuple[dict, dict]:
    run_core_mvp(
        report_path=FIXTURE_DIR / "report.txt",
        source_paths=[
            FIXTURE_DIR / "source-overlap.txt",
            FIXTURE_DIR / "source-unrelated.txt",
        ],
        rubric_path=FIXTURE_DIR / "rubric.json",
        config_path=FIXTURE_DIR / "config-bm25-only.json",
        output_dir=tmp_path,
        pipeline="both",
    )
    similarity = json.loads((tmp_path / "similarity-report.json").read_text())
    assessment = json.loads((tmp_path / "assessment-report.json").read_text())
    return similarity, assessment


def test_committed_json_schemas_are_valid_json_documents():
    for path in sorted(SCHEMA_DIR.glob("*.schema.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        assert value["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert value["type"] == "object"


def test_runner_outputs_satisfy_runtime_contracts(tmp_path):
    similarity, assessment = _reports(tmp_path)
    validate_similarity_report(similarity)
    validate_assessment_report(assessment)


def test_similarity_contract_rejects_unverified_coverage(tmp_path):
    similarity, _assessment = _reports(tmp_path)
    corrupted = deepcopy(similarity)
    selected = next(
        item for item in corrupted["matches"] if item["selected_for_document_coverage"]
    )
    selected["similarity_type"] = None

    with pytest.raises(ValueError, match="VERBATIM"):
        validate_similarity_report(corrupted)


def test_assessment_contract_rejects_inconsistent_decision(tmp_path):
    _similarity, assessment = _reports(tmp_path)
    corrupted = deepcopy(assessment)
    corrupted["checklist_results"][0]["checklist_outcome"] = "UNMET"

    with pytest.raises(ValueError, match="Inconsistent relation/outcome"):
        validate_assessment_report(corrupted)
