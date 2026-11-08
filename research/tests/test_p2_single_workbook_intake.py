"""Single-reviewer intake preserves provenance without inventing a second reviewer."""
import hashlib
import json
import sys

import pytest

pytest.importorskip("openpyxl", reason="Optional workbook intake requires openpyxl")

from research.gold_annotation import p2_workbook_intake as intake  # noqa: E402
from test_p2_workbook_intake import edit, packet, returned  # noqa: E402,F401


def test_single_workbook_archives_exact_bytes_without_agreement_or_gold(packet, tmp_path):
    source = returned(packet, tmp_path, role="YEN")
    before = source.read_bytes()
    output = tmp_path / "single"
    summary = intake.prepare_single_intake(packet[0], source, "YEN", output)
    assert summary["status"] == "READY_FOR_REVIEW"
    assert summary["annotation_design"] == "SINGLE_ANNOTATOR"
    assert summary["annotator_count"] == 1
    assert summary["second_annotator_required_by_this_intake"] is False
    assert summary["agreement_rate"] is summary["cohen_kappa"] is None
    assert summary["gold_frozen"] is summary["independence_certified"] is False
    assert summary["labels_generated"] is summary["model_predictions_read"] is False
    assert summary["counts"] == {"rows": 3, "states": {"VALID": 3}, "labels": {"MET": 3}}
    archived = output / "originals/yen_return.xlsx"
    assert archived.read_bytes() == source.read_bytes() == before
    assert archived.stat().st_mode & 0o777 == 0o400
    receipt, = json.loads((output / "source-receipts.json").read_text())
    assert receipt["sha256"] == hashlib.sha256(before).hexdigest()
    assert receipt["bytes"] == len(before)
    assert not (output / "canonical_quy.json").exists()
    canonical = json.loads((output / "canonical_yen.json").read_text())
    assert canonical["provenance"]["actual_annotator"] == "Reviewer YEN"
    assert json.loads((output / "review_items.json").read_text()) == []


def test_single_blank_sheet_never_becomes_completed_annotation(packet, tmp_path):
    source = returned(packet, tmp_path, role="YEN", fill=False)
    output = tmp_path / "blank"
    summary = intake.prepare_single_intake(packet[0], source, "Yến", output)
    assert summary["status"] == "INCOMPLETE"
    assert summary["counts"]["labels"] == {"BLANK": 3}
    canonical = json.loads((output / "canonical_yen.json").read_text())
    assert all(row["label"] is row["evidence"] is None for row in canonical["rows"])
    assert summary["review_items"] == 3


def test_ai_assistance_is_retained_as_review_flag_not_certified_independence(packet, tmp_path):
    source = returned(packet, tmp_path, role="YEN")
    edit(source, "THONG_TIN", "B4", "CO_AI_HO_TRO")
    edit(source, "THONG_TIN", "B10", "Synthetic AI-assisted checking declaration")
    summary = intake.prepare_single_intake(packet[0], source, "YEN", tmp_path / "assisted")
    assert summary["status"] == "NEEDS_REVIEW"
    assert summary["annotation_mode"] == "CO_AI_HO_TRO"
    assert summary["ai_assistance_declared"] is True
    assert summary["provenance_review_flags"] == ["AI_ASSISTANCE_DECLARED"]
    assert summary["independence_certified"] is False
    assert summary["agreement_rate"] is None


def test_single_invalid_quote_remains_invalid_and_is_not_repaired(packet, tmp_path):
    source = returned(packet, tmp_path, role="YEN")
    edit(source, "GAN_NHAN", "G2", "Not an exact source quotation")
    output = tmp_path / "invalid-quote"
    summary = intake.prepare_single_intake(packet[0], source, "YEN", output)
    assert summary["status"] == "INCOMPLETE"
    review, = json.loads((output / "review_items.json").read_text())
    assert review["issues"] == [{"code": "QUOTE_NOT_FOUND"}]
    assert review["label"] == "MET" and review["evidence"] is None
    assert review["source_fields"]["exact_evidence_quote"] == "Not an exact source quotation"


def test_existing_output_is_never_overwritten(packet, tmp_path):
    source = returned(packet, tmp_path, role="YEN")
    output = tmp_path / "existing"
    output.mkdir()
    sentinel = output / "preserve"
    sentinel.write_text("keep")
    with pytest.raises(intake.IntakeError, match="OUTPUT_ALREADY_EXISTS"):
        intake.prepare_single_intake(packet[0], source, "YEN", output)
    assert sentinel.read_text() == "keep"


def test_symlink_output_and_input_are_rejected(packet, tmp_path):
    source = returned(packet, tmp_path, role="YEN")
    linked_source = tmp_path / "linked.xlsx"
    linked_source.symlink_to(source)
    with pytest.raises(intake.IntakeError, match="SYMLINK_INPUT_REJECTED"):
        intake.prepare_single_intake(packet[0], linked_source, "YEN", tmp_path / "unsafe-input")
    target = tmp_path / "real-dir"
    target.mkdir()
    link = tmp_path / "link"
    link.symlink_to(target, target_is_directory=True)
    with pytest.raises(intake.IntakeError, match="OUTPUT_MUST_BE_PRIVATE_VAR"):
        intake.prepare_single_intake(packet[0], source, "YEN", link / "unsafe-output")


def test_cli_single_mode_accepts_one_sheet(packet, tmp_path, monkeypatch, capsys):
    source = returned(packet, tmp_path, role="YEN")
    monkeypatch.setattr(sys, "argv", ["intake", "--packet-dir", str(packet[0]), "--single-workbook",
                                      str(source), "--recipient", "YEN", "--output-dir", str(tmp_path / "cli")])
    assert intake.main() == 0
    assert json.loads(capsys.readouterr().out)["annotation_design"] == "SINGLE_ANNOTATOR"


@pytest.mark.parametrize("extra", [
    ["--single-workbook", "a.xlsx"],
    ["--single-workbook", "a.xlsx", "--recipient", "YEN", "--quy-workbook", "b.xlsx"],
    ["--single-workbook", "a.xlsx", "--recipient", "YEN", "--yen-workbook", "b.xlsx"],
    ["--recipient", "YEN"],
    ["--quy-workbook", "a.xlsx"],
    ["--yen-workbook", "a.xlsx"],
    [],
])
def test_cli_rejects_ambiguous_or_incomplete_modes(tmp_path, monkeypatch, extra):
    monkeypatch.setattr(sys, "argv", ["intake", "--packet-dir", str(tmp_path / "packet"),
                                      "--output-dir", str(tmp_path / "out"), *extra])
    with pytest.raises(SystemExit) as exc:
        intake.main()
    assert exc.value.code == 2
    assert not (tmp_path / "out").exists()


def test_paired_cli_remains_backward_compatible(packet, tmp_path, monkeypatch, capsys):
    quy, yen = returned(packet, tmp_path), returned(packet, tmp_path, role="YEN")
    monkeypatch.setattr(sys, "argv", ["intake", "--packet-dir", str(packet[0]), "--quy-workbook", str(quy),
                                      "--yen-workbook", str(yen), "--output-dir", str(tmp_path / "paired")])
    assert intake.main() == 0
    result = json.loads(capsys.readouterr().out)
    assert result["agreement_rate"] == 1
    assert set(result["per_person"]) == {"quy", "yen"}
