"""Artifact and scoring checks for the authored output-quality diagnostic."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from research.output_quality.evaluation import evaluate_pack, summarize_cases, validate_pack
from research.output_quality.comparison import compare_evaluations


PACK = Path(__file__).resolve().parents[1] / "output_quality/fixtures/dev-v1.json"


def test_frozen_authored_pack_has_valid_exact_evidence_and_no_gold_claim():
    pack = json.loads(PACK.read_text())
    validate_pack(pack)
    assert pack["provenance"]["independent_human_gold"] is False
    assert {case["language"] for case in pack["cases"]} == {"en", "vi"}
    assert {case["expected"]["relation"] for case in pack["cases"] if case["task"] == "SIMILARITY"} == {"VERBATIM", "PARAPHRASE", "NONE"}


@pytest.mark.parametrize("mutation", ["quote", "range", "gold", "case_path", "source_path"])
def test_pack_rejects_unverifiable_evidence_or_unsafe_output_paths(mutation):
    pack = deepcopy(json.loads(PACK.read_text()))
    if mutation == "quote":
        pack["cases"][0]["expected"]["evidence"][0]["quote"] = "fabricated quote"
    elif mutation == "range":
        pack["cases"][0]["expected"]["evidence"][0]["end"] += 1
    elif mutation == "gold":
        pack["provenance"]["independent_human_gold"] = True
    elif mutation == "case_path":
        pack["cases"][0]["case_id"] = "../outside"
    else:
        pack["cases"][0]["sources"][0]["source_id"] = "../../outside"
    with pytest.raises(ValueError):
        validate_pack(pack)


def test_abstention_is_not_counted_as_correct_none_or_a_retrieval_failure():
    rows = [{"task": "SIMILARITY", "expected_relation": "NONE", "predicted_relation": None,
             "target_rank": 1, "expected_anchor_contained": False, "relation_correct": False,
             "exact_document_coverage": 0.0, "any_retrieved_reuse": True,
             "retrieved_reuse_count": 1, "non_target_reuse_count": 1},
            {"task": "SIMILARITY", "expected_relation": "PARAPHRASE", "predicted_relation": None,
             "target_rank": 1, "expected_anchor_contained": True, "relation_correct": False,
             "exact_document_coverage": 0.0, "any_retrieved_reuse": False,
             "retrieved_reuse_count": 0, "non_target_reuse_count": 0}]
    summary = summarize_cases(rows)["similarity"]
    assert summary["relation_correct"] == 0
    assert summary["abstained_or_missing"] == 2
    assert summary["positive_target_retrieved_at_1"] == 1
    assert summary["positive_full_anchor_in_alignment"] == 1
    assert summary["negative_false_reuse_labels"] == 0
    assert summary["negative_cases_any_source_false_reuse"] == 1
    assert summary["non_target_false_reuse_labels"] == 1


def test_rejects_changed_pack_before_creating_run_artifacts(tmp_path):
    output = tmp_path / "run"
    with pytest.raises(ValueError, match="checksum mismatch"):
        evaluate_pack(PACK, output, expected_sha256="0" * 64)
    assert not output.exists()


def test_actual_bm25_pipeline_produces_separate_quality_artifacts(tmp_path):
    output = tmp_path / "run"
    result = evaluate_pack(PACK, output, expected_sha256=hashlib.sha256(PACK.read_bytes()).hexdigest())
    assert result["summary"]["similarity"]["cases"] == 12
    assert result["summary"]["assessment"]["cases"] == 6
    assert result["summary"]["similarity"]["positive_target_retrieved_at_3"] == 4
    assert result["summary"]["similarity"]["negative_false_exact_document_coverage"] == 0
    assert result["summary"]["similarity"]["negative_cases_any_source_false_reuse"] == 0
    assert result["summary"]["similarity"]["non_target_false_reuse_labels"] == 0
    assert len(result["core_hashes"]["similarity"]) == 64
    assert (output / "evaluation.json").exists()
    assert len(list((output / "cases").glob("*/pipeline-result.json"))) == 18
    with pytest.raises(ValueError, match="new empty output"):
        evaluate_pack(PACK, output)


def test_comparison_rejects_changed_labels_packs_or_retrieval():
    row = {"case_id": "one", "task": "SIMILARITY", "language": "en", "category": "topic",
           "expected_relation": "NONE", "relation_correct": False}
    before = {"pack_sha256": "a" * 64, "pack_id": "authored", "split": "DEV", "profile": "bm25",
              "configuration": {"top_k": 3}, "cases": [row], "summary": {}}
    for field in ("pack_sha256", "configuration", "expected_relation"):
        after = deepcopy(before)
        if field == "pack_sha256":
            after[field] = "b" * 64
        elif field == "configuration":
            after[field]["top_k"] = 1
        else:
            after["cases"][0][field] = "PARAPHRASE"
        with pytest.raises(ValueError):
            compare_evaluations(before, after)
