"""Check that the challenge cannot pass an always-positive or failed verifier."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from scripts.smoke_p2_llm_v2 import CASES, assess_prediction, prepare_run


def _prediction(label, *, status="VALIDATED", proof=True, quote="brake cable"):
    return {
        "checklist_outcome": label,
        "llm_verification": {"status": status},
        "reason_code": "SYNTHETIC_TEST_RESPONSE",
        "matched_evidence_spans": [{"span": {"text": quote}}] if label == "MET" and proof else [],
        "contradiction_hits": [{"synthetic": True}] if label == "UNMET" and proof else [],
    }


def test_always_met_model_fails_every_negative_control():
    outcomes = [assess_prediction(case, _prediction("MET", quote=case.get("proof_relevance_any_of", ["irrelevant text"])[0]))
                for case in CASES]
    negative_results = [result for case, result in zip(CASES, outcomes)
                        if case["group"] == "negative_control"]
    assert len(negative_results) == 7
    assert all(not result["expectation_passed"] for result in negative_results)
    assert sum(result["expectation_passed"] for result in outcomes) == 3


@pytest.mark.parametrize("case_id", [
    "unnamed-specific-experience", "repeated-sentence-personal-example",
    "late-example-behind-topic-distractors",
])
def test_met_with_generic_or_title_only_citation_fails_positive_evidence_expectation(case_id):
    case = next(case for case in CASES if case["case_id"] == case_id)
    generic_quote = case["text"].split("\n\n")[0]
    result = assess_prediction(case, _prediction("MET", quote=generic_quote))
    assert result["label"] == "MET"
    assert result["proof_relevance_required"] is True
    assert result["proof_relevance_passed"] is False
    assert result["expectation_passed"] is False
    assert assess_prediction(case, _prediction("MET", quote=case["proof_relevance_any_of"][-1]))["expectation_passed"]


def test_runtime_abstention_is_not_a_successful_missing_evidence_judgment():
    case = next(case for case in CASES if case["case_id"] == "topic-facts-without-experience")
    assert assess_prediction(case, _prediction("CANNOT_ASSESS"))["expectation_passed"]
    assert not assess_prediction(case, _prediction("CANNOT_ASSESS", status="WITHHELD"))["expectation_passed"]


@pytest.mark.parametrize("case_id,label", [
    ("unnamed-specific-experience", "MET"),
    ("explicit-personal-evidence-denial", "UNMET"),
])
def test_conclusive_label_without_proof_fails(case_id, label):
    case = next(case for case in CASES if case["case_id"] == case_id)
    assert not assess_prediction(case, _prediction(label, proof=False))["expectation_passed"]
    assert assess_prediction(case, _prediction(label))["expectation_passed"]


def _config(path: Path):
    value = {
        "pipeline2": {"llm_verification": {"enabled": True, "citation_mode": "source_units"}},
        "models": {"assessment_verifier": {"digest": "sha256:" + "a" * 64}},
    }
    path.write_text(json.dumps(value), encoding="utf-8")
    return value


def test_preparation_is_inspectable_and_refuses_overwrite(tmp_path):
    config = tmp_path / "profile.json"
    _config(config)
    output = tmp_path / "run"
    prepare_run(config, output)
    frozen_before = (output / "frozen-inputs.json").read_bytes()
    expectation = json.loads((output / "inputs/synthetic-expectations.json").read_text())
    assert expectation["independent_human_gold"] is False
    assert expectation["source_dataset"] is None
    assert len(expectation["cases"]) == 10
    assert expectation["proof_relevance_anchors_sent_to_model"] is False
    assert not (output / "predictions").exists()
    with pytest.raises(ValueError, match="new output directory"):
        prepare_run(config, output)
    assert (output / "frozen-inputs.json").read_bytes() == frozen_before


def test_preparation_rejects_legacy_citation_profile_before_creating_output(tmp_path):
    config_path = tmp_path / "profile.json"
    config = _config(config_path)
    legacy = deepcopy(config)
    legacy["pipeline2"]["llm_verification"].pop("citation_mode")
    config_path.write_text(json.dumps(legacy), encoding="utf-8")
    with pytest.raises(ValueError, match="source_units"):
        prepare_run(config_path, tmp_path / "run")
    assert not (tmp_path / "run").exists()
