"""Synthetic checks for private two-annotator gold workflow."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from research.gold_annotation import workflow


def _write_csv(path: Path, rows: list[dict[str, str]]) -> Path:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


def _similarity_row(item: str, label: str) -> dict[str, str]:
    return {
        "pair_id": item,
        "report_chunk_id": f"r-{item}",
        "source_chunk_id": f"s-{item}",
        "source_name": "synthetic.txt",
        "report_text": "An exact shared sentence appears here.",
        "source_text": "An exact shared sentence appears here.",
        "report_page": "1",
        "source_page": "2",
        "label": label,
        "report_evidence_quote": "shared sentence" if label not in ("NONE", "UNSURE") else "",
        "source_evidence_quote": "shared sentence" if label not in ("NONE", "UNSURE") else "",
        "quote_or_citation": "NO",
        "confidence": "HIGH",
        "rationale": "Synthetic example, manually assigned.",
    }


def _assessment_row(item: str, label: str) -> dict[str, str]:
    return {
        "item_id": item,
        "report_id": "synthetic-report",
        "report_version": "v1",
        "rubric_id": "synthetic-rubric",
        "rubric_version": "v1",
        "checklist_id": f"c-{item}",
        "label": label,
        "verification_relation": workflow._RELATION_FOR_OUTCOME.get(label, ""),
        "evidence_span_ids": "span-synthetic" if label in ("MET", "UNMET") else "",
        "rationale": "Synthetic manually reviewed evidence.",
    }


def _final_row(item: str, final_label: str = "", *, relation: str = "") -> dict[str, str]:
    return {
        "pair_id": item,
        "quy_label": "",
        "yen_label": "",
        "final_label": final_label,
        "decision_rationale": "",
        "decision_by": "",
        "decided_at": "",
        "final_verification_relation": relation,
    }


def test_similarity_agreement_requires_human_adjudication_and_writes_private_aggregate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = [_similarity_row("a", "VERBATIM"), _similarity_row("b", "NONE"), _similarity_row("c", "UNSURE")]
    second = [_similarity_row("a", "VERBATIM"), _similarity_row("b", "PARAPHRASE"), _similarity_row("c", "NONE")]
    a_path = _write_csv(tmp_path / "quy.csv", first)
    b_path = _write_csv(tmp_path / "yen.csv", second)
    final = [_final_row("a"), _final_row("b"), _final_row("c")]
    final_path = _write_csv(tmp_path / "adjudication.csv", final)
    pending = workflow.summarize(task="similarity", annotator_a=a_path, annotator_b=b_path, adjudication=final_path)
    assert pending["agreement"]["both_resolved_count"] == 2
    assert pending["agreement"]["unsure_in_either_sheet_count"] == 1
    assert pending["agreement"]["exact_agreement_rate"] == pytest.approx(0.5)
    assert pending["agreement"]["cohen_kappa"] == pytest.approx(1 / 3)
    assert pending["adjudication"]["unresolved_count"] == 2
    assert pending["gold_label_counts"] is None

    for row, label in zip(final[1:], ("NONE", "EXCLUDE"), strict=True):
        row.update(final_label=label, decision_rationale="Human review of source",
                   decision_by="two annotators", decided_at="2026-10-22")
    _write_csv(final_path, final)
    complete = workflow.summarize(task="similarity", annotator_a=a_path, annotator_b=b_path, adjudication=final_path)
    assert complete["adjudication"] == {
        "status": "COMPLETE", "unresolved_count": 0,
        "excluded_count": 1, "adjudicated_count": 2,
    }
    assert complete["gold_label_counts"] == {"NONE": 1, "VERBATIM": 1}
    private_root = tmp_path / "var"
    monkeypatch.setattr(workflow, "_VAR_ROOT", private_root)
    output = workflow.write_summary(complete, private_root / "gold-pilot")
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["gold_label_counts"] == complete["gold_label_counts"]
    assert "shared sentence" not in output.read_text(encoding="utf-8")
    assert output.stat().st_mode & 0o077 == 0
    with pytest.raises(FileExistsError):
        workflow.write_summary(complete, private_root / "gold-pilot")
    with pytest.raises(ValueError, match="ignored repository var"):
        workflow.write_summary(complete, tmp_path / "tracked")


def test_similarity_rejects_missing_quote_and_changed_context(tmp_path: Path) -> None:
    a = [_similarity_row("a", "VERBATIM")]
    b = [_similarity_row("a", "VERBATIM")]
    a[0]["report_evidence_quote"] = "not present"
    a_path = _write_csv(tmp_path / "a.csv", a)
    b_path = _write_csv(tmp_path / "b.csv", b)
    with pytest.raises(ValueError, match="exact excerpt"):
        workflow.summarize(task="similarity", annotator_a=a_path, annotator_b=b_path)
    a[0]["report_evidence_quote"] = "shared sentence"
    b[0]["source_text"] = "Another exact shared sentence appears here."
    _write_csv(a_path, a)
    _write_csv(b_path, b)
    with pytest.raises(ValueError, match="mismatched item metadata"):
        workflow.summarize(task="similarity", annotator_a=a_path, annotator_b=b_path)


def test_assessment_checks_evidence_relation_and_adjudication(tmp_path: Path) -> None:
    a = [_assessment_row("a", "MET"), _assessment_row("b", "CANNOT_ASSESS")]
    b = [_assessment_row("a", "MET"), _assessment_row("b", "UNMET")]
    a_path = _write_csv(tmp_path / "assessment-a.csv", a)
    b_path = _write_csv(tmp_path / "assessment-b.csv", b)
    final = [_final_row("a"), _final_row("b", "UNMET", relation="CONTRADICTED")]
    for row in final:
        row["item_id"] = row.pop("pair_id")
    final[1].update(decision_rationale="Source contradicts requirement",
                    decision_by="two annotators", decided_at="2026-10-22")
    final_path = _write_csv(tmp_path / "assessment-final.csv", final)
    summary = workflow.summarize(task="assessment", annotator_a=a_path, annotator_b=b_path, adjudication=final_path)
    assert summary["agreement"]["both_resolved_count"] == 2
    assert summary["adjudication"]["status"] == "COMPLETE"
    assert summary["gold_label_counts"] == {"MET": 1, "UNMET": 1}

    a[0]["verification_relation"] = "CONTRADICTED"
    _write_csv(a_path, a)
    with pytest.raises(ValueError, match="outcome/relation conflict"):
        workflow.summarize(task="assessment", annotator_a=a_path, annotator_b=b_path)


def test_identical_single_class_has_undefined_kappa_and_no_model_score(tmp_path: Path) -> None:
    rows = [_similarity_row("a", "NONE"), _similarity_row("b", "NONE")]
    a_path = _write_csv(tmp_path / "a.csv", rows)
    b_path = _write_csv(tmp_path / "b.csv", rows)
    summary = workflow.summarize(task="similarity", annotator_a=a_path, annotator_b=b_path)
    assert summary["agreement"]["exact_agreement_rate"] == 1
    assert summary["agreement"]["cohen_kappa"] is None
    assert summary["gold_label_counts"] is None
    assert "model_accuracy" not in summary


def test_disagreement_cannot_be_silently_inferred(tmp_path: Path) -> None:
    a_path = _write_csv(tmp_path / "a.csv", [_similarity_row("a", "VERBATIM")])
    b_path = _write_csv(tmp_path / "b.csv", [_similarity_row("a", "NONE")])
    adjudication = [_final_row("a", "VERBATIM")]
    final_path = _write_csv(tmp_path / "final.csv", adjudication)
    with pytest.raises(ValueError, match="require rationale"):
        workflow.summarize(task="similarity", annotator_a=a_path, annotator_b=b_path, adjudication=final_path)
