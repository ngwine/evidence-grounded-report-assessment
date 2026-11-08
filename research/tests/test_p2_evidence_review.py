"""Human evidence-review integrity; synthetic forms do not certify semantics."""
from copy import deepcopy
import csv
from pathlib import Path

import pytest

from research.p2_comparison import evidence_review as review
from research.p2_comparison import retrieval_study as study
from research.p2_comparison import runner as base
from research.tests.test_p2_retrieval_study import factory, source  # noqa: F401


@pytest.fixture
def packet(source, tmp_path):
    study.prepare_retrieval_study(**source)
    run = tmp_path / "run"
    study.run_retrieval_study(prepared_dir=source["output_dir"], output_dir=run,
        verifier_factory=factory({}))
    out = tmp_path / "review"
    review.prepare_review(prepared_dir=source["output_dir"],
        predictions_path=run / "all-methods-predictions.json", output_dir=out)
    return out


def _rows(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _returned(packet, tmp_path, *, rating="SUPPORTED"):
    rows = _rows(packet / "PHIEU_KIEM_BANG_CHUNG.csv")
    for row in rows:
        row.update(support_rating=rating, reviewer="Synthetic fixture reviewer",
            method_exposure="METHOD_MAPPING_NOT_SEEN", ai_assistance="NONE",
            review_reason="Synthetic workflow test, not a real semantic judgment.")
    path = tmp_path / "returned.csv"
    path.write_bytes(review._csv_bytes(rows))
    return path, rows


def test_template_has_no_invented_human_ratings_or_method_labels(packet):
    rows = _rows(packet / "PHIEU_KIEM_BANG_CHUNG.csv")
    assert len(rows) == 2
    assert all(row[key] == "" for row in rows for key in review.HUMAN_FIELDS)
    assert all("method" not in row and "reference_label" not in row for row in rows)
    for row in rows:
        assert (packet / row["report_file"]).is_file()
        assert row["model_rationale"] and row["cited_evidence"]
    receipt = base._read_json(packet / "review-receipt.json")
    assert receipt["semantic_support_certified"] is False
    assert receipt["human_review_complete"] is False
    assert set(base._read_json(packet / "private-method-mapping.json")[rows[0]["review_id"]]) >= {"method", "item_id"}


def test_pending_is_reported_without_synthesizing_support_accuracy(packet, tmp_path):
    result = review.summarize_review(review_dir=packet,
        completed_csv=packet / "PHIEU_KIEM_BANG_CHUNG.csv", output_dir=tmp_path / "pending-summary")
    assert result["complete"] is False
    assert all(m["rated"] == 0 and m["pending"] == 1 for m in result["methods"].values())
    assert all(m["fully_supported_rate_among_rated"] is None for m in result["methods"].values())
    assert result["label_accuracy_recomputed"] is False


def test_uncertain_rating_stays_in_denominator(packet, tmp_path):
    path, _ = _returned(packet, tmp_path, rating="UNCERTAIN")
    result = review.summarize_review(review_dir=packet, completed_csv=path, output_dir=tmp_path / "summary")
    assert result["complete"] is True
    assert result["independent_gold_claim"] is False
    assert all(m["rated"] == 1 and m["fully_supported_rate_among_rated"] == 0 for m in result["methods"].values())


@pytest.mark.parametrize("change", ["duplicate", "missing", "prediction", "reviewer", "disclosure", "exposure"])
def test_changed_or_incomplete_review_records_are_rejected(packet, tmp_path, change):
    path, rows = _returned(packet, tmp_path)
    if change == "duplicate":
        rows[1] = deepcopy(rows[0])
    elif change == "missing":
        rows.pop()
    elif change == "prediction":
        rows[0]["model_rationale"] = "Rewritten model interpretation"
    elif change == "reviewer":
        rows[0]["reviewer"] = ""
    elif change == "disclosure":
        rows[0]["ai_assistance"] = ""
    else:
        rows[0]["method_exposure"] = "UNKNOWN"
    path.write_bytes(review._csv_bytes(rows))
    with pytest.raises(ValueError):
        review.summarize_review(review_dir=packet, completed_csv=path, output_dir=tmp_path / "rejected")
    assert not (tmp_path / "rejected").exists()


def test_source_packet_tampering_is_rejected(packet, tmp_path):
    body = next((packet / "reports").glob("*.txt"))
    body.chmod(0o600)
    body.write_text("A different body")
    with pytest.raises(ValueError, match="Frozen review packet"):
        review.summarize_review(review_dir=packet, completed_csv=packet / "PHIEU_KIEM_BANG_CHUNG.csv",
            output_dir=tmp_path / "rejected")


def test_technical_abstentions_never_create_positive_review_rows(source, tmp_path):
    study.prepare_retrieval_study(**source)
    run = tmp_path / "technical-run"
    study.run_retrieval_study(prepared_dir=source["output_dir"], output_dir=run,
        verifier_factory=factory({}, technical=True))
    out = tmp_path / "technical-review"
    result = review.prepare_review(prepared_dir=source["output_dir"],
        predictions_path=run / "all-methods-predictions.json", output_dir=out)
    assert result["review_rows"] == 0
    receipt = base._read_json(out / "review-receipt.json")
    assert all(m["technical"] == 1 and m["conclusive"] == 0 for m in receipt["methods"].values())
