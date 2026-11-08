"""Synthetic math and integrity checks; never assign labels to the real essays."""
from copy import deepcopy
import csv
import hashlib
import json

import pytest

from research.p2_comparison import single_reference_metrics as metrics


def reference(labels=("MET", "UNMET", "MET", "UNMET")):
    return [{"item_id": f"case-{index}-CLM001", "case_id": f"case-{index}", "state": "VALID", "label": label,
             "metadata": {"report_id": f"report-{index}", "report_version": "v1", "body_sha256": "a" * 64,
                          "rubric_id": "rubric", "rubric_version": "v1", "checklist_id": "CLM001"}}
            for index, label in enumerate(labels)]


def predictions(rows, labels):
    return [{"item_id": row["item_id"], "case_id": row["case_id"], "metadata": deepcopy(row["metadata"]),
             "accepted_label": label,
             "decision_status": "SEMANTIC_DECISION" if label is not None else "TECHNICAL_ABSTENTION"}
            for row, label in zip(rows, labels)]


def test_label_denominator_coverage_confusion_and_macro_f1_include_technical_failures():
    rows = reference()
    result = metrics.summarize(rows, {"one-step": predictions(rows, ["MET", "MET", None, "UNMET"])}, expected_items=4)
    value = result["methods"]["one-step"]
    assert value["reference_label_agreement"] == {
        "matching": 2, "denominator": 4, "rate": 0.5, "technical_abstentions_count_as_mismatches": True}
    assert value["accepted_only_agreement"]["rate"] == pytest.approx(2 / 3)
    assert value["accepted_coverage"] == 0.75
    assert value["technical_abstentions"] == 1
    assert value["confusion_matrix"]["MET"]["TECHNICAL_ABSTENTION"] == 1
    assert value["confusion_matrix"]["UNMET"]["MET"] == 1
    assert value["per_class"]["MET"]["f1"] == 0.5
    assert value["per_class"]["UNMET"]["f1"] == pytest.approx(2 / 3)
    assert value["macro_f1_observed_reference_classes"] == pytest.approx((0.5 + 2 / 3) / 2)
    assert value["macro_f1_observed_labels"] == ["MET", "UNMET"]
    assert value["macro_f1_fixed_three_class"] is None
    assert value["unsupported_reference_classes"] == ["CANNOT_ASSESS"]
    assert value["per_class"]["CANNOT_ASSESS"]["recall"] is None
    assert result["always_met_baseline"]["reference_label_agreement"]["rate"] == 0.5
    assert result["gold_approval_asserted"] is result["evidence_semantic_support_evaluated"] is False
    assert result["inter_annotator_agreement"] is result["cohen_kappa"] is None


def test_semantic_ca_is_separate_from_technical_abstention():
    rows = reference(["MET", "UNMET", "CANNOT_ASSESS"])
    output = metrics.summarize(rows, {"method": predictions(rows, ["MET", None, "CANNOT_ASSESS"])})
    value = output["methods"]["method"]
    assert value["confusion_matrix"]["UNMET"]["TECHNICAL_ABSTENTION"] == 1
    assert value["confusion_matrix"]["CANNOT_ASSESS"]["CANNOT_ASSESS"] == 1
    assert value["technical_abstentions"] == 1
    assert value["macro_f1_fixed_three_class"] == pytest.approx(2 / 3)


def test_all_failures_do_not_become_semantic_ca_or_disappear():
    rows = reference()
    output = metrics.summarize(rows, {"method": predictions(rows, [None] * 4)})
    value = output["methods"]["method"]
    assert value["items"] == value["technical_abstentions"] == 4
    assert value["reference_label_agreement"]["rate"] == 0
    assert value["accepted_only_agreement"]["rate"] is None
    assert value["per_class"]["MET"]["precision"] is None
    assert value["per_class"]["MET"]["f1"] == 0
    assert value["macro_f1_observed_reference_classes"] == 0


def test_paired_methods_align_by_id_even_if_predictions_order_changes():
    rows = reference()
    first = predictions(rows, ["MET", "MET", None, "UNMET"])
    second = predictions(rows, [None, "UNMET", "MET", "UNMET"])
    result = metrics.summarize(rows, {"one-step": list(reversed(first)), "two-step": second})
    pair = result["paired_method_comparisons"]["one-step__vs__two-step"]
    assert pair["both_match_reference"] == 1
    assert pair["only_first_matches"] == 1
    assert pair["only_second_matches"] == 2
    assert pair["neither_matches"] == 0
    assert pair["agreement_rate_second_minus_first"] == 0.25
    assert pair["causal_or_significance_claim"] is False


def test_per_checklist_reports_single_class_support_without_three_class_claim():
    rows = reference(["MET", "MET"])
    rows[1]["metadata"]["checklist_id"] = "EXP001"
    result = metrics.summarize(rows, {"method": predictions(rows, ["MET", "MET"])})
    group = result["methods"]["method"]["per_checklist"]["EXP001"]
    assert group["reference_label_counts"] == {"MET": 1, "UNMET": 0, "CANNOT_ASSESS": 0}
    assert group["macro_f1_observed_labels"] == ["MET"]
    assert group["macro_f1_fixed_three_class"] is None
    assert "Checklist có toàn MET" in metrics.render_markdown(result)


@pytest.mark.parametrize("change", [
    lambda rows: rows.pop(),
    lambda rows: rows.append(deepcopy(rows[0])),
    lambda rows: rows[0].update(item_id="unknown-item"),
    lambda rows: rows[0].update(case_id="wrong-case"),
    lambda rows: rows[0]["metadata"].update(report_version="changed"),
    lambda rows: rows[0]["metadata"].pop("body_sha256"),
    lambda rows: rows[0].pop("accepted_label"),
    lambda rows: rows[0].update(accepted_label="UNSURE"),
    lambda rows: rows[0].update(accepted_label=None),
    lambda rows: rows[0].update(decision_status="TECHNICAL_ABSTENTION"),
    lambda rows: rows[0].update(raw_result={"llm_verification": {"status": "WITHHELD"}}),
    lambda rows: rows[0].update(checklist_id="different"),
])
def test_incomplete_mismatched_or_invalid_prediction_records_are_rejected(change):
    rows = reference()
    values = predictions(rows, [row["label"] for row in rows])
    change(values)
    with pytest.raises(ValueError):
        metrics.summarize(rows, {"method": values})


def test_duplicate_case_checklist_with_new_item_id_is_rejected():
    rows = reference()
    rows[1]["case_id"] = rows[0]["case_id"]
    with pytest.raises(ValueError, match="Duplicate"):
        metrics.summarize(rows, {"method": predictions(rows, [row["label"] for row in rows])})


@pytest.mark.parametrize("label,state", [("UNSURE", "VALID"), ("MET", "INVALID"), (None, "INCOMPLETE")])
def test_unresolved_reference_never_silently_becomes_gold(label, state):
    rows = reference()
    rows[0].update(label=label, state=state)
    with pytest.raises(ValueError, match="resolved"):
        metrics.summarize(rows, {"method": predictions(rows, ["MET"] * 4)})


def test_expected_count_prevents_a_smaller_accidentally_complete_subset():
    rows = reference()
    with pytest.raises(ValueError, match="expected"):
        metrics.summarize(rows, {"method": predictions(rows, ["MET"] * 4)}, expected_items=45)


def inputs(tmp_path):
    rows = reference()
    reference_path, prediction_path = tmp_path / "reference.json", tmp_path / "predictions.json"
    reference_path.write_text(json.dumps({"rows": rows}))
    prediction_path.write_text(json.dumps({"schema_version": 1, "methods": {
        "one-step": predictions(rows, ["MET", "MET", None, "UNMET"]),
        "two-step": predictions(rows, ["MET", "UNMET", "MET", "UNMET"])}}))
    return reference_path, prediction_path


def test_write_evaluation_records_sha_exports_all_items_and_mismatches(tmp_path, monkeypatch):
    monkeypatch.setattr(metrics, "VAR_ROOT", tmp_path)
    ref, preds = inputs(tmp_path)
    out = tmp_path / "evaluation"
    ref_sha = hashlib.sha256(ref.read_bytes()).hexdigest()
    result = metrics.write_evaluation(reference_path=ref, predictions_path=preds, output_dir=out,
        expected_items=4, expected_reference_sha256=ref_sha)
    assert result["reference_sha256"] == ref_sha
    assert result["predictions_sha256"] == hashlib.sha256(preds.read_bytes()).hexdigest()
    with (out / "comparison.csv").open(encoding="utf-8-sig") as stream:
        assert len(list(csv.DictReader(stream))) == 8
    with (out / "mismatches.csv").open(encoding="utf-8-sig") as stream:
        assert len(list(csv.DictReader(stream))) == 2
    assert (out / "metrics.json").stat().st_mode & 0o777 == 0o600
    assert "Luôn đoán MET" in (out / "KET_QUA_P2_THAM_DO.md").read_text()
    assert result["evidence_semantic_support_evaluated"] is False
    with pytest.raises(FileExistsError):
        metrics.write_evaluation(reference_path=ref, predictions_path=preds, output_dir=out)


def test_changed_reference_checksum_rejected_before_creating_output(tmp_path, monkeypatch):
    monkeypatch.setattr(metrics, "VAR_ROOT", tmp_path)
    ref, preds = inputs(tmp_path)
    out = tmp_path / "bad-sha"
    with pytest.raises(ValueError, match="checksum"):
        metrics.write_evaluation(reference_path=ref, predictions_path=preds, output_dir=out,
                                 expected_reference_sha256="a" * 64)
    assert not out.exists()


def test_nonprivate_or_symlink_output_is_rejected(tmp_path, monkeypatch):
    private = tmp_path / "private"
    private.mkdir()
    monkeypatch.setattr(metrics, "VAR_ROOT", private)
    ref, preds = inputs(tmp_path)
    with pytest.raises(ValueError, match="private"):
        metrics.write_evaluation(reference_path=ref, predictions_path=preds, output_dir=tmp_path / "outside")
    symlink = private / "link"
    symlink.symlink_to(private, target_is_directory=True)
    with pytest.raises(ValueError, match="private"):
        metrics.write_evaluation(reference_path=ref, predictions_path=preds, output_dir=symlink / "nested")


def test_csv_exports_protect_formula_like_method_identifiers(tmp_path, monkeypatch):
    monkeypatch.setattr(metrics, "VAR_ROOT", tmp_path)
    ref, preds = inputs(tmp_path)
    value = json.loads(preds.read_text())
    value["methods"]["=1+1"] = value["methods"].pop("one-step")
    preds.write_text(json.dumps(value))
    out = tmp_path / "formula"
    metrics.write_evaluation(reference_path=ref, predictions_path=preds, output_dir=out)
    with (out / "comparison.csv").open(encoding="utf-8-sig") as stream:
        values = list(csv.DictReader(stream))
    assert any(row["method"] == "'=1+1" for row in values)


def test_cli_works_for_complete_synthetic_run(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(metrics, "VAR_ROOT", tmp_path)
    ref, preds = inputs(tmp_path)
    assert metrics.main(["--reference", str(ref), "--predictions", str(preds), "--output-dir",
                         str(tmp_path / "cli"), "--expected-items", "4"]) == 0
    assert json.loads(capsys.readouterr().out)["items"] == 4
