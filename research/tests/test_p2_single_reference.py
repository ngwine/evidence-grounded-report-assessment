"""Exploratory preparation uses actual-style synthetic sheets, never real labels."""
from copy import deepcopy
import json

import pytest

pytest.importorskip("openpyxl")

from research.gold_annotation.p2_workbook_intake import parse_workbook  # noqa: E402
from research.p2_comparison import single_reference as single  # noqa: E402
from test_p2_workbook_intake import edit, packet, returned  # noqa: E402,F401
from test_p2_comparison import factory_capture  # noqa: E402


@pytest.fixture
def preparation_inputs(packet, tmp_path, monkeypatch):
    monkeypatch.setattr(single.base, "VAR_ROOT", tmp_path)
    root, _ = packet
    workbook = returned(packet, tmp_path, role="YEN")
    edit(workbook, "THONG_TIN", "B4", "CO_AI_HO_TRO")
    edit(workbook, "THONG_TIN", "B10", "Synthetic assisted review declaration")
    reference = tmp_path / "reference.json"
    reference.write_text(json.dumps(parse_workbook(root, workbook, "YEN")))
    protocol = tmp_path / "protocol.json"
    protocol.write_text(json.dumps({"schema_version": 1, "design": single.DESIGN,
        "allow_actual_cohort": True, "methods": list(single.base.METHODS),
        "no_tuning_after_first_prediction": True, "approved_gold_claim": False,
        "independent_holdout_claim": False, "label_classes": ["MET", "UNMET", "CANNOT_ASSESS"]}))
    authorization = tmp_path / "authorization.json"
    authorization.write_text(json.dumps({"schema_version": 1, "scope": single.SCOPE,
        "allow_actual_cohort": True, "approved_gold_claim": False,
        "user_instruction": "Synthetic run authorization", "prior_single_annotator_instruction": "Use one sheet"}))
    rubric = tmp_path / "rubric.json"
    rubric.write_text(json.dumps({"schema_version": 1, "rubric_id": "synthetic-runtime-rubric",
        "version": "1", "max_score": 3,
        "criteria": [{"criterion_id": "C", "title": "Test checklist", "weight": 3,
            "checklists": [{"checklist_id": key, "mode": "LOCAL", "statement": "Describe completed work.",
                "requirements": [{"requirement_id": key + ".R", "description": "Completed work is described.",
                                  "any_of": ["baked bread"]}]} for key in ("CLM001", "EXP001", "QUO001")]}]}))
    return {"packet_dir": root, "workbook_path": workbook, "canonical_reference": reference,
            "rubric_path": rubric, "protocol_path": protocol, "authorization_path": authorization,
            "output_dir": tmp_path / "prepared"}


def test_prepare_locks_all_inputs_without_constructing_model(preparation_inputs, monkeypatch):
    monkeypatch.setattr(single.LlmAssessmentVerifier, "__init__", lambda *a, **kw: pytest.fail("Model constructed"))
    result = single.prepare_single_reference(**preparation_inputs)
    assert result["reports"] == 1 and result["items"] == 3
    root = preparation_inputs["output_dir"]
    manifest = json.loads((root / "preparation-manifest.json").read_text())
    assert manifest["approved_gold_claim"] is manifest["model_called"] is False
    assert manifest["reference_not_given_to_verifier"] is True
    assert "reference.json" in manifest["locked_files"]
    assert "cases/C2-01-IDX/common-evidence.json" in manifest["locked_files"]
    assert all((root / key).stat().st_mode & 0o222 == 0 for key in manifest["locked_files"])
    common = json.loads((root / "cases/C2-01-IDX/common-evidence.json").read_text())
    assert "label" not in common
    assert common["identity_alias_is_explicit"] is True
    assert len(common["items"]) == 3


def test_same_packs_both_methods_and_resume_never_calls_completed_requests(preparation_inputs, tmp_path):
    single.prepare_single_reference(**preparation_inputs)
    seen = {}
    out = tmp_path / "run"
    args = {"prepared_dir": preparation_inputs["output_dir"], "output_dir": out,
            "verifier_factory": factory_capture(seen)}
    result = single.run_single_reference(**args)
    assert result["status"] == "COMPLETE_EXPLORATORY_PREDICTIONS_NOT_APPROVED_GOLD"
    assert result["methods"]["one-step"]["accepted_labels"] == {"MET": 3}
    assert seen["one-step"] == seen["two-step"]
    previous = deepcopy(seen)
    single.run_single_reference(**args)
    assert seen == previous
    predictions = json.loads((out / "all-methods-predictions.json").read_text())
    assert predictions["methods"]["one-step"][0]["metadata"]["rubric_id"] == "rubric-x"
    for rows in predictions["methods"].values():
        assert len(rows) == 3
        assert all(r["accepted_label"] == "MET" for r in rows)


def test_timeout_is_null_technical_abstention_not_semantic_ca(preparation_inputs, tmp_path):
    single.prepare_single_reference(**preparation_inputs)
    result = single.run_single_reference(prepared_dir=preparation_inputs["output_dir"],
        output_dir=tmp_path / "technical", verifier_factory=factory_capture({}, technical=True))
    assert all(m["technical_abstentions"] == 3 for m in result["methods"].values())
    rows = json.loads((tmp_path / "technical/all-methods-predictions.json").read_text())["methods"]["one-step"]
    assert all(r["accepted_label"] is None and r["decision_status"] == "TECHNICAL_ABSTENTION" for r in rows)


def test_missing_authorization_does_not_create_preparation(preparation_inputs):
    path = preparation_inputs["authorization_path"]
    value = json.loads(path.read_text())
    value["allow_actual_cohort"] = False
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="authorization"):
        single.prepare_single_reference(**preparation_inputs)
    assert not preparation_inputs["output_dir"].exists()


def test_reference_change_does_not_create_preparation(preparation_inputs):
    path = preparation_inputs["canonical_reference"]
    value = json.loads(path.read_text())
    value["rows"][0]["label"] = "UNMET"
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="Canonical reference"):
        single.prepare_single_reference(**preparation_inputs)
    assert not preparation_inputs["output_dir"].exists()


def test_frozen_input_change_rejected_before_model(preparation_inputs, tmp_path):
    single.prepare_single_reference(**preparation_inputs)
    root = preparation_inputs["output_dir"]
    path = root / "cases/C2-01-IDX/body.txt"
    path.chmod(0o600)
    path.write_text(path.read_text() + " tampered")
    with pytest.raises(ValueError, match="frozen evaluation input"):
        single.run_single_reference(prepared_dir=root, output_dir=tmp_path / "rejected",
            verifier_factory=lambda *a: pytest.fail("Model constructed"))


def test_interrupted_started_request_is_never_retried(preparation_inputs, tmp_path):
    single.prepare_single_reference(**preparation_inputs)
    out = tmp_path / "interrupted"
    class Interrupted:
        metadata = {"source_unit_policy": {"max_citations_per_requirement": 3}}
        def verify(self, checklist, pack):
            raise KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt):
        single.run_single_reference(prepared_dir=preparation_inputs["output_dir"], output_dir=out,
            verifier_factory=lambda *a: Interrupted())
    with pytest.raises(ValueError, match="Interrupted call"):
        single.run_single_reference(prepared_dir=preparation_inputs["output_dir"], output_dir=out,
            verifier_factory=lambda *a: pytest.fail("Retried interrupted call"))


def test_actual_model_requires_explicit_execution_flag(preparation_inputs, tmp_path):
    with pytest.raises(ValueError, match="allow-real-model"):
        single.run_single_reference(prepared_dir=preparation_inputs["output_dir"], output_dir=tmp_path / "run")
