"""Self-authored synthetic labels test runner mechanics and arithmetic only.

The fixtures are deliberately local, synthetic approvals. They confer no rights
or approval on any actual report, source, rubric, pilot, or human annotation.
"""

from __future__ import annotations

import copy
import csv
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import pytest

from research.gold_annotation import evaluation as gold
from research.gold_annotation import workflow


def _bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n").encode()


def _sha(contents: bytes) -> str:
    return hashlib.sha256(contents).hexdigest()


def _csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


class Pack:
    def __init__(self, root: Path, task: str, labels: list[str]) -> None:
        self.root, self.task = root, task
        self.directory = root / "pack"
        self.directory.mkdir()
        self.a: list[dict[str, str]] = []
        self.contexts: list[dict[str, Any]] = []
        self.final: list[dict[str, str]] = []
        for number, label in enumerate(labels):
            item = f"synthetic-item-{number}"
            if task == "similarity":
                row = {"pair_id": item, "report_chunk_id": f"r-{number}", "source_chunk_id": f"s-{number}",
                       "source_name": "self-authored.txt", "report_text": "prefix shared content suffix",
                       "source_text": "other shared content tail", "report_page": "1", "source_page": "2",
                       "label": label, "report_evidence_quote": "shared content" if label != "NONE" else "",
                       "source_evidence_quote": "shared content" if label != "NONE" else "",
                       "quote_or_citation": "NO", "confidence": "HIGH", "rationale": "Self-authored synthetic fixture."}
                metadata = {"report_id": "synthetic-report", "report_version": "v1", "source_id": "synthetic-source",
                            "source_version": "v1", **{name: row[name] for name in ("report_chunk_id", "source_chunk_id", "source_name", "report_page", "source_page")}}
                context = {"schema_version": 1, "item_id": item, "task": task, "metadata": metadata,
                           "report_text": row["report_text"], "source_text": row["source_text"]}
            else:
                metadata = {"report_id": "synthetic-report", "report_version": "v1", "rubric_id": "synthetic-rubric",
                            "rubric_version": "v1", "checklist_id": f"c-{number}"}
                row = {"item_id": item, **metadata, "label": label,
                       "verification_relation": workflow._RELATION_FOR_OUTCOME[label],
                       "evidence_span_ids": "s1;s2" if label == "MET" else "s2" if label == "UNMET" else "",
                       "rationale": "Self-authored synthetic fixture."}
                context = {"schema_version": 1, "item_id": item, "task": task, "metadata": metadata,
                           "report_text": "alpha beta gamma delta", "evidence_spans": [
                               {"span_id": "s1", "start": 0, "end": 5}, {"span_id": "s2", "start": 6, "end": 10},
                               {"span_id": "s3", "start": 11, "end": 16}]}
            self.a.append(row)
            self.contexts.append(context)
            self.final.append({"pair_id" if task == "similarity" else "item_id": item,
                               "quy_label": "", "yen_label": "", "final_label": "", "decision_rationale": "",
                               "decision_by": "", "decided_at": "", "final_quote_or_citation": "",
                               "final_report_evidence_quote": "", "final_source_evidence_quote": "",
                               "final_verification_relation": "", "final_evidence_span_ids": ""})
        self.b = copy.deepcopy(self.a)
        self.paths = {role: self.directory / filename for role, filename in {
            "annotator_a": "a.csv", "annotator_b": "b.csv", "adjudication": "final.csv", "context": "context.jsonl"}.items()}
        self.path = self.directory / "approved-pack.json"
        self.manifest = {"schema_version": 1, "dataset_id": "self-authored-gold-test", "dataset_version": "v1",
                         "governance": {"status": "APPROVED", "allowed_purposes": ["GOLD_EVALUATION"],
                                        "rights_basis": "Self-authored synthetic test fixture only.", "classification": "SYNTHETIC_PUBLIC",
                                        "retention": "pytest temporary directory", "approver": "fixture author",
                                        "approved_at": "2026-10-24", "contains_pii": False},
                         "split": {"name": "synthetic-only", "unit": "report", "document_ids": ["synthetic-report"]},
                         "files": {}, "gold_evaluation": {"schema_version": 1, "task": task, "gold_version": "synthetic-v1",
                             "annotation_mode": "BLINDED_INDEPENDENT", "predictions_visible": False,
                             "annotator_ids": {"a": "synthetic-author-A", "b": "synthetic-author-B"},
                             "sealed_at": "2026-10-24", "approved_by": "fixture-author", "approved_at": "2026-10-24",
                             "inputs": {role: role for role in self.paths}}}
        self.config = root / "pipeline-config.json"
        self.config.write_bytes(_bytes({"algorithm": "synthetic-test-only", "threshold": 0.5}))
        self.run = {"run_id": "synthetic-test-run", "commit": "a" * 40, "config_sha256": _sha(self.config.read_bytes()),
                    "seed": 7, "pipeline_version": "synthetic-pipeline-v1", "task": task, "labels": list(gold._LABELS[task])}
        self.save()

    def save(self) -> None:
        _csv(self.paths["annotator_a"], self.a)
        _csv(self.paths["annotator_b"], self.b)
        _csv(self.paths["adjudication"], self.final)
        self.paths["context"].write_bytes(b"".join(_bytes(row) for row in self.contexts))
        self.manifest["files"] = {role: {"path": path.name, "sha256": _sha(path.read_bytes())} for role, path in self.paths.items()}
        self.path.write_bytes(_bytes(self.manifest))

    def freeze(self, **updates: Any) -> Path:
        kwargs = {"task": self.task, **self.paths, "pack_manifest": self.path, "gold_version": "synthetic-v1",
                  "run_metadata": self.run, "config": self.config, "output_dir": self.root / "frozen"}
        kwargs.update(updates)
        return gold.freeze(**kwargs)

    def predictions(self, frozen: Path, labels: list[str | None] | None = None) -> tuple[Path, list[dict[str, Any]]]:
        records = [json.loads(line) for line in (frozen / "gold.jsonl").read_text().splitlines()]
        rows = []
        for index, record in enumerate(records):
            label = record["label"] if labels is None else labels[index]
            evidence = copy.deepcopy(record["evidence"])
            if label in (None, "NOT_RUN"):
                evidence = {}
            elif label in ("NONE", "CANNOT_ASSESS"):
                evidence = {"report_intervals": [], "source_intervals": []} if self.task == "similarity" else {"span_ids": []}
            rows.append({"schema_version": 1, "item_id": record["item_id"], "task": self.task,
                         "metadata": record["metadata"], "label": label,
                         "score": None if label in (None, "NOT_RUN") else 0.75, "evidence": evidence,
                         "run": copy.deepcopy(self.run)})
        return self.write_predictions(rows), rows

    def write_predictions(self, rows: list[dict[str, Any]]) -> Path:
        path = self.root / "predictions.jsonl"
        path.write_bytes(b"".join(_bytes(row) for row in rows))
        return path

    def evaluate(self, frozen: Path, predictions: Path, **updates: Any) -> Path:
        kwargs = {"gold_dir": frozen, "predictions": predictions, "run_metadata": self.run,
                  "config": self.config, "output_dir": self.root / "evaluated"}
        kwargs.update(updates)
        return gold.evaluate(**kwargs)


@pytest.fixture
def pack_factory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    root = tmp_path / "var"
    root.mkdir(mode=0o700)
    monkeypatch.setattr(gold, "_VAR_ROOT", root)
    # Exercise the actual validator, using only a self-authored fixture registry.
    monkeypatch.setattr(gold.governance, "load_registry", lambda: {"schema_version": 1, "datasets": [
        {"id": "self-authored-gold-test", "manifest_ids": ["self-authored-gold-test"],
         "mapping": {"evidence": "pytest self-authored fixture"}, "source_sha256": {}}]})
    yield lambda task="similarity", labels=None: Pack(root, task, labels or ["VERBATIM", "NONE"])
    # Immutable production bundles deliberately need owner chmod to remove.
    for directory, _, _ in os.walk(root):
        os.chmod(directory, 0o700)


def _metrics(output: Path) -> dict[str, Any]:
    return json.loads((output / "metrics.json").read_text())


def test_known_classification_abstention_and_evidence_numbers(pack_factory) -> None:
    pack = pack_factory(labels=["VERBATIM", "VERBATIM", "NONE", "PARAPHRASE"])
    frozen = pack.freeze()
    predictions, _ = pack.predictions(frozen, ["VERBATIM", "NONE", None, "PARAPHRASE"])
    output = pack.evaluate(frozen, predictions)
    metrics = _metrics(output)
    classification = metrics["classification"]
    assert classification["accuracy"] == 0.5
    assert classification["coverage"] == 0.75
    assert classification["selective_accuracy"] == pytest.approx(2 / 3)
    assert classification["per_class"]["VERBATIM"]["precision"] == 1
    assert classification["per_class"]["VERBATIM"]["recall"] == 0.5
    assert classification["per_class"]["VERBATIM"]["f1"] == pytest.approx(2 / 3)
    assert classification["macro_f1"] == pytest.approx(5 / 12)
    assert classification["macro_f1_present_gold"] == pytest.approx(5 / 9)
    assert classification["zero_gold_support_classes"] == ["SUMMARY"]
    assert classification["confusion_matrix_gold_rows_prediction_columns"]["NONE"]["ABSTAIN"] == 1
    assert metrics["evidence"]["precision"] == 1
    assert metrics["evidence"]["recall"] == pytest.approx(2 / 3)
    assert metrics["evidence"]["f1"] == pytest.approx(0.8)
    report = (output / "metrics.json").read_text()
    assert "synthetic-item" not in report and "shared content" not in report
    provenance = json.loads((output / "evaluation-manifest.json").read_text())
    assert provenance["predictions_sha256"] == _sha(predictions.read_bytes())
    assert provenance["run"] == pack.run
    for directory in (frozen, output):
        assert directory.stat().st_mode & 0o777 == 0o500
        assert all(path.stat().st_mode & 0o777 == 0o400 for path in directory.iterdir())
    with pytest.raises(ValueError, match="invalid or unavailable"):
        pack.evaluate(frozen, predictions)


def test_character_intervals_use_unions_and_exact_half_open_offsets(pack_factory) -> None:
    pack = pack_factory(labels=["VERBATIM"])
    frozen = pack.freeze()
    predictions, rows = pack.predictions(frozen)
    report = rows[0]["evidence"]["report_intervals"][0]
    assert report == [7, 21]
    rows[0]["evidence"]["report_intervals"] = [[7, 11], [9, 14]]
    rows[0]["evidence"]["source_intervals"].append([0, 2])
    predictions = pack.write_predictions(rows)
    evidence = _metrics(pack.evaluate(frozen, predictions))["evidence"]
    assert evidence["gold_count"] == 28
    assert evidence["predicted_count"] == 23
    assert evidence["overlap_count"] == 21
    assert evidence["precision"] == pytest.approx(21 / 23)
    assert evidence["recall"] == 0.75
    assert evidence["f1"] == pytest.approx(42 / 51)


def test_assessment_span_id_metrics_and_not_run(pack_factory) -> None:
    pack = pack_factory("assessment", ["MET", "UNMET", "CANNOT_ASSESS"])
    frozen = pack.freeze()
    _, rows = pack.predictions(frozen, ["MET", "UNMET", "NOT_RUN"])
    rows[0]["evidence"]["span_ids"] = ["s1"]
    rows[1]["evidence"]["span_ids"] = ["s2", "s3"]
    metrics = _metrics(pack.evaluate(frozen, pack.write_predictions(rows)))
    assert metrics["classification"]["coverage"] == pytest.approx(2 / 3)
    assert metrics["classification"]["per_class"]["CANNOT_ASSESS"]["false_negative"] == 1
    assert metrics["classification"]["confusion_matrix_gold_rows_prediction_columns"]["CANNOT_ASSESS"]["ABSTAIN"] == 1
    evidence = metrics["evidence"]
    assert evidence["unit"] == "item_context_span_id"
    assert (evidence["overlap_count"], evidence["predicted_count"], evidence["gold_count"]) == (2, 3, 3)
    assert evidence["precision"] == evidence["recall"] == evidence["f1"] == pytest.approx(2 / 3)


def test_all_abstentions_are_false_negatives_and_zero_evidence_not_perfect(pack_factory) -> None:
    pack = pack_factory(labels=["VERBATIM", "NONE"])
    frozen = pack.freeze()
    predictions, _ = pack.predictions(frozen, [None, "NOT_RUN"])
    metrics = _metrics(pack.evaluate(frozen, predictions))
    assert metrics["classification"]["accuracy"] == 0
    assert metrics["classification"]["coverage"] == 0
    assert metrics["classification"]["selective_accuracy"] is None
    assert metrics["classification"]["per_class"]["VERBATIM"]["false_negative"] == 1
    assert metrics["classification"]["per_class"]["NONE"]["false_negative"] == 1
    assert metrics["evidence"]["precision"] is None
    assert metrics["evidence"]["recall"] == metrics["evidence"]["f1"] == 0


def test_single_class_exposes_missing_class_support_and_undefined_empty_evidence(pack_factory) -> None:
    pack = pack_factory(labels=["NONE", "NONE"])
    frozen = pack.freeze()
    predictions, _ = pack.predictions(frozen)
    metrics = _metrics(pack.evaluate(frozen, predictions))
    assert metrics["classification"]["accuracy"] == 1
    assert metrics["classification"]["macro_f1"] == 0.25
    assert metrics["classification"]["macro_f1_present_gold"] == 1
    assert len(metrics["classification"]["zero_gold_support_classes"]) == 3
    assert metrics["evidence"]["precision"] is metrics["evidence"]["recall"] is metrics["evidence"]["f1"] is None


def test_accepted_prediction_without_a_confidence_score_is_supported(pack_factory) -> None:
    pack = pack_factory()
    frozen = pack.freeze()
    _, rows = pack.predictions(frozen)
    for row in rows:
        row["score"] = None
    assert _metrics(pack.evaluate(frozen, pack.write_predictions(rows)))["classification"]["accuracy"] == 1


@pytest.mark.parametrize("mutation", ["missing", "extra", "duplicate", "version", "context", "run", "task", "score_bool", "score_nan", "label", "interval", "abstain_evidence"])
def test_prediction_identity_version_and_schema_fail_closed(pack_factory, mutation: str) -> None:
    pack = pack_factory()
    frozen = pack.freeze()
    _, rows = pack.predictions(frozen)
    if mutation == "missing":
        rows.pop()
    elif mutation == "extra":
        rows.append({**copy.deepcopy(rows[0]), "item_id": "unknown-item"})
    elif mutation == "duplicate":
        rows.append(copy.deepcopy(rows[0]))
    elif mutation == "version":
        rows[0]["metadata"]["report_version"] = "v2"
    elif mutation == "context":
        rows[0]["metadata"]["context_sha256"] = "0" * 64
    elif mutation == "run":
        rows[0]["run"]["seed"] = 8
    elif mutation == "task":
        rows[0]["task"] = "assessment"
    elif mutation == "score_bool":
        rows[0]["score"] = True
    elif mutation == "score_nan":
        rows[0]["score"] = float("nan")
    elif mutation == "label":
        rows[0]["label"] = "MODEL_VISIBLE_REVIEW_SECRET"
    elif mutation == "interval":
        rows[0]["evidence"]["report_intervals"] = [[-1, 4]]
    else:
        rows[0]["label"], rows[0]["score"] = None, None
    with pytest.raises(ValueError) as error:
        pack.evaluate(frozen, pack.write_predictions(rows))
    assert str(error.value) == gold._ERROR
    assert not (pack.root / "evaluated").exists()


@pytest.mark.parametrize("mutation", ["approval", "purpose", "model_visible", "predictions_visible", "annotator", "adjudication", "same_file", "incomplete", "metadata", "context", "repeated_quote", "all_excluded"])
def test_freeze_requires_exact_approved_independent_complete_inputs(pack_factory, mutation: str) -> None:
    pack = pack_factory()
    protocol = pack.manifest["gold_evaluation"]
    if mutation == "approval":
        pack.manifest["governance"]["status"] = "PENDING"
    elif mutation == "purpose":
        pack.manifest["governance"]["allowed_purposes"] = ["PILOT"]
    elif mutation == "model_visible":
        protocol["annotation_mode"] = "MODEL_VISIBLE_REVIEW"
    elif mutation == "predictions_visible":
        protocol["predictions_visible"] = True
    elif mutation == "annotator":
        protocol["annotator_ids"]["b"] = protocol["annotator_ids"]["a"]
    elif mutation == "adjudication":
        protocol["inputs"].pop("adjudication")
    elif mutation == "same_file":
        protocol["inputs"]["annotator_b"] = "annotator_a"
    elif mutation == "incomplete":
        pack.b[0]["label"] = "NONE"
    elif mutation == "metadata":
        pack.b[0]["source_chunk_id"] = "other-source"
    elif mutation == "context":
        pack.contexts[0]["source_text"] = "different context"
    elif mutation == "repeated_quote":
        for row in (pack.a[0], pack.b[0], pack.contexts[0]):
            row["report_text"] = "shared content and shared content"
    else:
        for row in pack.final:
            row.update(final_label="EXCLUDE", decision_rationale="Self-authored exclusion.",
                       decision_by="fixture-author", decided_at="2026-10-24")
    pack.save()
    with pytest.raises(ValueError, match="invalid or unavailable"):
        pack.freeze()
    assert not (pack.root / "frozen").exists()


def test_assessment_human_and_prediction_span_ids_must_exist(pack_factory) -> None:
    pack = pack_factory("assessment", ["MET"])
    for rows in (pack.a, pack.b):
        rows[0]["evidence_span_ids"] = "not-in-locked-context"
    pack.save()
    with pytest.raises(ValueError):
        pack.freeze()
    for rows in (pack.a, pack.b):
        rows[0]["evidence_span_ids"] = "s1"
    pack.save()
    frozen = pack.freeze()
    _, rows = pack.predictions(frozen)
    rows[0]["evidence"]["span_ids"] = ["unknown-span"]
    with pytest.raises(ValueError):
        pack.evaluate(frozen, pack.write_predictions(rows))


@pytest.mark.parametrize("mutation", ["gold", "gold_and_seal", "approval", "sheet", "config"])
def test_tamper_and_changed_current_approval_are_rejected(pack_factory, mutation: str) -> None:
    pack = pack_factory()
    frozen = pack.freeze()
    predictions, _ = pack.predictions(frozen)
    if mutation in ("gold", "gold_and_seal"):
        path = frozen / "gold.jsonl"
        os.chmod(path, 0o600)
        records = [json.loads(line) for line in path.read_text().splitlines()]
        records[0]["label"] = "NONE"
        path.write_bytes(b"".join(_bytes(record) for record in records))
        if mutation == "gold_and_seal":
            seal_path = frozen / "gold-manifest.json"
            seal = json.loads(seal_path.read_text())
            seal["gold_sha256"] = _sha(path.read_bytes())
            os.chmod(seal_path, 0o600)
            seal_path.write_bytes(_bytes(seal))
    elif mutation == "approval":
        pack.manifest["governance"]["allowed_purposes"] = []
        pack.path.write_bytes(_bytes(pack.manifest))
    elif mutation == "sheet":
        pack.paths["annotator_a"].write_text("changed after sealing")
    else:
        pack.config.write_text("different pipeline configuration")
    with pytest.raises(ValueError):
        pack.evaluate(frozen, predictions)


def test_missing_gold_and_exact_supplied_paths_are_rejected(pack_factory) -> None:
    pack = pack_factory()
    other = pack.root / "unapproved-a.csv"
    other.write_bytes(pack.paths["annotator_a"].read_bytes())
    with pytest.raises(ValueError):
        pack.freeze(annotator_a=other)
    with pytest.raises(ValueError):
        pack.evaluate(pack.root / "missing-gold", pack.root / "missing-predictions")


@pytest.mark.parametrize("mutation", ["context", "config", "approval"])
def test_freeze_rechecks_all_inputs_after_materialization(pack_factory, monkeypatch: pytest.MonkeyPatch, mutation: str) -> None:
    pack = pack_factory()
    original = gold._gold

    def change_after_read(*args, **kwargs):
        result = original(*args, **kwargs)
        if mutation == "context":
            pack.paths["context"].write_text("changed context after materialization")
        elif mutation == "config":
            pack.config.write_text("changed config after materialization")
        else:
            pack.manifest["governance"]["allowed_purposes"] = []
            pack.path.write_bytes(_bytes(pack.manifest))
        return result

    monkeypatch.setattr(gold, "_gold", change_after_read)
    with pytest.raises(ValueError):
        pack.freeze()
    assert not (pack.root / "frozen").exists()


@pytest.mark.parametrize("mutation", ["predictions", "config", "context", "approval"])
def test_evaluate_rechecks_snapshots_before_writing(pack_factory, monkeypatch: pytest.MonkeyPatch, mutation: str) -> None:
    pack = pack_factory()
    frozen = pack.freeze()
    predictions, _ = pack.predictions(frozen)
    original = gold._metrics

    def change_after_read(*args, **kwargs):
        result = original(*args, **kwargs)
        if mutation == "predictions":
            predictions.write_text("changed predictions after scoring")
        elif mutation == "config":
            pack.config.write_text("changed config after scoring")
        elif mutation == "context":
            pack.paths["context"].write_text("changed context after scoring")
        else:
            pack.manifest["governance"]["allowed_purposes"] = []
            pack.path.write_bytes(_bytes(pack.manifest))
        return result

    monkeypatch.setattr(gold, "_metrics", change_after_read)
    with pytest.raises(ValueError):
        pack.evaluate(frozen, predictions)
    assert not (pack.root / "evaluated").exists()


@pytest.mark.parametrize("mutation", ["outside", "traversal", "symlink_output", "symlink_input", "pack_traversal", "hardlink_sheets", "oversized", "total_bytes", "too_many_rows"])
def test_private_paths_bounds_symlinks_and_distinct_files(pack_factory, monkeypatch: pytest.MonkeyPatch, mutation: str) -> None:
    pack = pack_factory()
    updates: dict[str, Any] = {}
    if mutation == "outside":
        updates["output_dir"] = pack.root.parent / "tracked-output"
    elif mutation == "traversal":
        updates["output_dir"] = pack.root / "nested" / ".." / "output"
    elif mutation == "symlink_output":
        link = pack.root / "link"
        link.symlink_to(pack.directory, target_is_directory=True)
        updates["output_dir"] = link / "output"
    elif mutation == "symlink_input":
        target = pack.root / "original.csv"
        target.write_bytes(pack.paths["annotator_a"].read_bytes())
        pack.paths["annotator_a"].unlink()
        pack.paths["annotator_a"].symlink_to(target)
    elif mutation == "pack_traversal":
        pack.manifest["files"]["annotator_a"]["path"] = "../secret.csv"
        pack.path.write_bytes(_bytes(pack.manifest))
    elif mutation == "hardlink_sheets":
        pack.paths["annotator_b"].unlink()
        os.link(pack.paths["annotator_a"], pack.paths["annotator_b"])
    elif mutation == "oversized":
        monkeypatch.setattr(gold, "_MAX_BYTES", 20)
    elif mutation == "total_bytes":
        monkeypatch.setattr(gold, "_MAX_TOTAL_BYTES", 20)
    else:
        monkeypatch.setattr(gold, "_MAX_ROWS", 1)
    with pytest.raises(ValueError):
        pack.freeze(**updates)


def test_cli_success_and_generic_failure_without_paths_or_text(pack_factory, capsys: pytest.CaptureFixture[str]) -> None:
    pack = pack_factory()
    run = pack.root / "run.json"
    run.write_bytes(_bytes(pack.run))
    argv = ["freeze", "--task", pack.task, "--gold-version", "synthetic-v1", "--pack-manifest", str(pack.path),
            "--run-metadata", str(run), "--config", str(pack.config), "--output-dir", str(pack.root / "frozen")]
    for role, path in pack.paths.items():
        argv.extend(["--" + role.replace("_", "-"), str(path)])
    assert gold.main(argv) == 0
    assert json.loads(capsys.readouterr().out) == {"status": "FROZEN"}
    assert gold.main(argv) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.strip() == gold._ERROR
    assert str(pack.root) not in captured.err
