"""Freeze independently annotated gold and evaluate exact, versioned predictions.

All inputs and immutable outputs stay in ignored var/. Approval is obtained from
the real dataset registry; this module never creates an approval or a label.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
from datetime import date, datetime, timezone
from typing import Any, Mapping, Sequence

from research.gold_annotation import workflow
from research.governance import registry as governance


_VAR_ROOT = Path(__file__).resolve().parents[2] / "var"
_MAX_BYTES = 16 * 1024 * 1024
_MAX_ROWS = 100_000
_MAX_TOTAL_BYTES = 64 * 1024 * 1024
_ERROR = "Gold evaluation input is invalid or unavailable."
_LABELS = {"similarity": workflow._SIMILARITY_LABELS, "assessment": workflow._ASSESSMENT_LABELS}
_SIM_METADATA = (
    "report_id", "report_version", "source_id", "source_version",
    "report_chunk_id", "source_chunk_id", "source_name", "report_page", "source_page",
)
_ASSESS_METADATA = ("report_id", "report_version", "rubric_id", "rubric_version", "checklist_id")
_CAUGHT = (ValueError, OSError, UnicodeError, KeyError, TypeError, OverflowError, csv.Error, RecursionError)


def _json(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _text(value: Any) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(_ERROR)
    return value


def _version(value: Any) -> str:
    value = _text(value)
    if any(token in value.upper() for token in ("UNFROZEN", "SET_AFTER", "PENDING", "PLACEHOLDER")):
        raise ValueError(_ERROR)
    return value


def _sha(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError(_ERROR)
    return value


def _path(value: str | Path) -> Path:
    raw = Path(value)
    if ".." in raw.parts or str(raw).startswith("~"):
        raise ValueError(_ERROR)
    path = Path(os.path.abspath(raw))
    root = Path(os.path.abspath(_VAR_ROOT))
    if path == root or not path.is_relative_to(root):
        raise ValueError(_ERROR)
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise ValueError(_ERROR)
    return path


def _read(value: str | Path) -> tuple[Path, bytes]:
    path = _path(value)
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > _MAX_BYTES:
            raise ValueError(_ERROR)
        data = stream.read(_MAX_BYTES + 1)
    if len(data) > _MAX_BYTES:
        raise ValueError(_ERROR)
    return path, data


def _decode(data: bytes) -> Any:
    def reject_constant(_: str) -> None:
        raise ValueError(_ERROR)

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(_ERROR)
            result[key] = value
        return result

    return json.loads(data.decode("utf-8"), parse_constant=reject_constant, object_pairs_hook=unique_object)


def _rows(data: bytes) -> list[dict[str, Any]]:
    lines = data.splitlines()
    if len(lines) > _MAX_ROWS or any(not line.strip() for line in lines):
        raise ValueError(_ERROR)
    result = [_decode(line) for line in lines]
    if any(not isinstance(row, dict) for row in result):
        raise ValueError(_ERROR)
    return result


def _indexed(rows: Sequence[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        item = _text(row.get("item_id"))
        if item in result:
            raise ValueError(_ERROR)
        result[item] = row
    return result


def _approved(pack_manifest: str | Path) -> tuple[Path, dict[str, Any], dict[str, Path], dict[str, Any]]:
    path, data = _read(pack_manifest)
    manifest = _decode(data)
    # Preflight every file before the registry opens it: bounded private regular
    # files, no traversal, no symlinks, including files not used by this runner.
    files = manifest["files"]
    if not isinstance(files, dict) or not files:
        raise ValueError(_ERROR)
    paths: dict[str, Path] = {}
    total_bytes = len(data)
    for logical_name, record in files.items():
        relative = PurePosixPath(_text(record["path"]))
        if relative.is_absolute() or ".." in relative.parts or "\\" in str(relative):
            raise ValueError(_ERROR)
        candidate, contents = _read(path.parent / str(relative))
        total_bytes += len(contents)
        if total_bytes > _MAX_TOTAL_BYTES:
            raise ValueError(_ERROR)
        if not candidate.is_relative_to(path.parent) or _digest(contents) != _sha(record["sha256"]):
            raise ValueError(_ERROR)
        paths[logical_name] = candidate
    validation = {**governance.validate_pack_manifest(path, "GOLD_EVALUATION", verify_files=True),
                  "manifest_sha256": _digest(data)}
    if _read(path)[1] != data:
        raise ValueError(_ERROR)
    protocol = manifest["gold_evaluation"]
    if (type(protocol["schema_version"]) is not int or protocol["schema_version"] != 1 or protocol["task"] not in _LABELS
            or protocol["annotation_mode"] != "BLINDED_INDEPENDENT"
            or protocol["predictions_visible"] is not False):
        raise ValueError(_ERROR)
    annotators = protocol["annotator_ids"]
    if _text(annotators["a"]) == _text(annotators["b"]):
        raise ValueError(_ERROR)
    _text(protocol["approved_by"])
    date.fromisoformat(_text(protocol["approved_at"]))
    date.fromisoformat(_text(protocol["sealed_at"]))
    _version(protocol["gold_version"])
    inputs = protocol["inputs"]
    if not isinstance(inputs, dict) or set(inputs) != {"annotator_a", "annotator_b", "adjudication", "context"}:
        raise ValueError(_ERROR)
    selected = {role: paths[_text(name)] for role, name in inputs.items()}
    identities = [(p.stat().st_dev, p.stat().st_ino) for p in selected.values()]
    if len(set(identities)) != len(identities):
        raise ValueError(_ERROR)
    return path, manifest, selected, validation


def _run(metadata: Mapping[str, Any], config: str | Path, task: str) -> dict[str, Any]:
    required = {"run_id", "commit", "config_sha256", "seed", "pipeline_version", "task", "labels"}
    if not isinstance(metadata, Mapping) or set(metadata) != required:
        raise ValueError(_ERROR)
    if (metadata["task"] != task or metadata["labels"] != list(_LABELS[task])
            or type(metadata["seed"]) is not int
            or not isinstance(metadata["commit"], str)
            or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", metadata["commit"])):
        raise ValueError(_ERROR)
    _text(metadata["run_id"])
    _version(metadata["pipeline_version"])
    _, contents = _read(config)
    if _digest(contents) != _sha(metadata["config_sha256"]):
        raise ValueError(_ERROR)
    return dict(metadata)


def _intervals(value: Any, length: int) -> list[list[int]]:
    if not isinstance(value, list):
        raise ValueError(_ERROR)
    for pair in value:
        if (not isinstance(pair, list) or len(pair) != 2
                or any(type(number) is not int for number in pair)
                or not 0 <= pair[0] < pair[1] <= length):
            raise ValueError(_ERROR)
    return _union(value)


def _union(intervals: Sequence[Sequence[int]]) -> list[list[int]]:
    result: list[list[int]] = []
    for start, end in sorted(intervals):
        if result and start <= result[-1][1]:
            result[-1][1] = max(end, result[-1][1])
        else:
            result.append([start, end])
    return result


def _quote_interval(quote: str, text: str) -> list[list[int]]:
    if not quote or quote not in text:
        raise ValueError(_ERROR)
    start = text.index(quote)
    # Even overlapping repeated matches are ambiguous. Never pick the first.
    if text.find(quote, start + 1) != -1:
        raise ValueError(_ERROR)
    return [[start, start + len(quote)]]


def _csv_text(text: str) -> str:
    if text.startswith("'") and text[1:].lstrip().startswith(("=", "+", "-", "@")):
        return text[1:]
    return text


def _contexts(path: Path, task: str, expected_sha: str) -> dict[str, dict[str, Any]]:
    _, data = _read(path)
    if _digest(data) != expected_sha:
        raise ValueError(_ERROR)
    result = _indexed(_rows(data))
    metadata_fields = _SIM_METADATA if task == "similarity" else _ASSESS_METADATA
    texts: dict[tuple[str, ...], str] = {}
    span_versions: dict[tuple[str, ...], tuple[int, int]] = {}
    for context in result.values():
        expected = {"schema_version", "item_id", "task", "metadata", "report_text"}
        expected.add("source_text" if task == "similarity" else "evidence_spans")
        if (set(context) != expected or type(context["schema_version"]) is not int or context["schema_version"] != 1
                or context["task"] != task or not isinstance(context["metadata"], dict)
                or set(context["metadata"]) != set(metadata_fields)):
            raise ValueError(_ERROR)
        for name, value in context["metadata"].items():
            (_version if name.endswith("version") else _text)(value)
        if not isinstance(context["report_text"], str):
            raise ValueError(_ERROR)
        if task == "similarity" and not isinstance(context["source_text"], str):
            raise ValueError(_ERROR)
        metadata = context["metadata"]
        for side in (("report", "source") if task == "similarity" else ("report",)):
            key = (side, metadata[f"{side}_id"], metadata[f"{side}_version"])
            if task == "similarity":
                key += (metadata[f"{side}_chunk_id"],)
            digest = _digest(context[f"{side}_text"].encode("utf-8"))
            if key in texts and texts[key] != digest:
                raise ValueError(_ERROR)
            texts[key] = digest
        if task == "assessment":
            spans = context["evidence_spans"]
            if not isinstance(spans, list):
                raise ValueError(_ERROR)
            seen: set[str] = set()
            for span in spans:
                if not isinstance(span, dict) or set(span) != {"span_id", "start", "end"}:
                    raise ValueError(_ERROR)
                identifier = _text(span["span_id"])
                if identifier in seen:
                    raise ValueError(_ERROR)
                seen.add(identifier)
                _intervals([[span["start"], span["end"]]], len(context["report_text"]))
                key = (metadata["report_id"], metadata["report_version"], identifier)
                interval = (span["start"], span["end"])
                if key in span_versions and span_versions[key] != interval:
                    raise ValueError(_ERROR)
                span_versions[key] = interval
    return result


def _gold(manifest: Mapping[str, Any], inputs: Mapping[str, Path]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    task = manifest["gold_evaluation"]["task"]
    summary = workflow.summarize(task=task, annotator_a=inputs["annotator_a"],
                                 annotator_b=inputs["annotator_b"], adjudication=inputs["adjudication"])
    if summary["adjudication"]["status"] != "COMPLETE":
        raise ValueError(_ERROR)
    protocol = manifest["gold_evaluation"]
    for role, digest in summary["input_sha256"].items():
        if digest != manifest["files"][protocol["inputs"][role]]["sha256"]:
            raise ValueError(_ERROR)
    id_field = "pair_id" if task == "similarity" else "item_id"
    fields = workflow._SIMILARITY_FIELDS if task == "similarity" else workflow._ASSESSMENT_FIELDS
    first = workflow._read_csv(inputs["annotator_a"], fields, id_field)
    second = workflow._read_csv(inputs["annotator_b"], fields, id_field)
    final = workflow._read_csv(inputs["adjudication"], (id_field, *workflow._ADJUDICATION_FIELDS), id_field)
    contexts = _contexts(inputs["context"], task, manifest["files"][protocol["inputs"]["context"]]["sha256"])
    if len(first) > _MAX_ROWS or first.keys() != contexts.keys():
        raise ValueError(_ERROR)
    records: list[dict[str, Any]] = []
    for item in sorted(first):
        a, b, decision, context = first[item], second[item], final[item], contexts[item]
        metadata = context["metadata"]
        compare = ("report_chunk_id", "source_chunk_id", "source_name", "report_page", "source_page") if task == "similarity" else _ASSESS_METADATA
        if any(a[name] != metadata[name] for name in compare):
            raise ValueError(_ERROR)
        if task == "similarity":
            if any(_csv_text(a[name]) != context[name] for name in ("report_text", "source_text")):
                raise ValueError(_ERROR)
        agreed = workflow._same_evidence(task, a, b)
        label = decision["final_label"].strip() or (a["label"].strip() if agreed else "")
        if label == "EXCLUDE":
            continue
        # Explicitly restating consensus does not substitute new, unvalidated
        # final evidence. Overrides/disputes use only validated final fields.
        needs_decision = not agreed or label != a["label"].strip()
        evidence: dict[str, Any]
        if task == "similarity":
            evidence = {"report_intervals": [], "source_intervals": []}
            if label in _LABELS[task][:3]:
                for side in ("report", "source"):
                    field = f"{'final_' if needs_decision else ''}{side}_evidence_quote"
                    source = decision if needs_decision else a
                    evidence[f"{side}_intervals"] = _quote_interval(source[field], context[f"{side}_text"])
        else:
            evidence = {"span_ids": []}
            if label in ("MET", "UNMET"):
                span_ids = list(workflow._span_ids((decision if needs_decision else a)["final_evidence_span_ids" if needs_decision else "evidence_span_ids"]))
                known = {span["span_id"] for span in context["evidence_spans"]}
                if not set(span_ids).issubset(known):
                    raise ValueError(_ERROR)
                evidence["span_ids"] = span_ids
        records.append({"schema_version": 1, "item_id": item, "task": task,
                        "metadata": {**metadata, "context_sha256": _digest(_json(context))},
                        "label": label, "evidence": evidence, "context": context})
    # Detect changes while the legacy CSV validator was reading the inputs.
    for role, digest in summary["input_sha256"].items():
        if _digest(_read(inputs[role])[1]) != digest:
            raise ValueError(_ERROR)
    if not records:
        raise ValueError(_ERROR)
    return records, summary


def _bundle(output_dir: str | Path, files: Mapping[str, bytes]) -> Path:
    output = _path(output_dir)
    if output.exists():
        raise FileExistsError(_ERROR)
    if any(len(contents) > _MAX_BYTES for contents in files.values()):
        raise ValueError(_ERROR)
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    os.chmod(output, 0o700)
    for name, contents in files.items():
        descriptor = os.open(output / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(contents)
        os.chmod(output / name, 0o400)
    os.chmod(output, 0o500)
    return output


def freeze(*, task: str, annotator_a: str | Path, annotator_b: str | Path,
           adjudication: str | Path, context: str | Path, pack_manifest: str | Path,
           gold_version: str, run_metadata: Mapping[str, Any], config: str | Path,
           output_dir: str | Path) -> Path:
    """Seal only COMPLETE, independently attested, source-approved human sheets."""
    try:
        path, manifest, inputs, validation = _approved(pack_manifest)
        protocol = manifest["gold_evaluation"]
        if task != protocol["task"] or gold_version != protocol["gold_version"]:
            raise ValueError(_ERROR)
        supplied = {"annotator_a": annotator_a, "annotator_b": annotator_b,
                    "adjudication": adjudication, "context": context}
        if any(_read(value)[0] != inputs[role] for role, value in supplied.items()):
            raise ValueError(_ERROR)
        run = _run(run_metadata, config, task)
        records, summary = _gold(manifest, inputs)
        contents = b"".join(_json(record) for record in records)
        _, checked_pack, checked_inputs, checked_approval = _approved(path)
        if (_json(checked_pack) != _json(manifest) or checked_inputs != inputs
                or checked_approval != validation or _run(run_metadata, config, task) != run):
            raise ValueError(_ERROR)
        seal = {"schema_version": 1, "kind": "INDEPENDENT_HUMAN_GOLD", "task": task,
                "gold_version": gold_version, "labels": list(_LABELS[task]),
                "item_count": len(records), "excluded_count": summary["adjudication"]["excluded_count"],
                "gold_sha256": _digest(contents), "pack_manifest_sha256": validation["manifest_sha256"],
                "pack_manifest": str(path.relative_to(Path(os.path.abspath(_VAR_ROOT)))),
                "input_sha256": {role: _digest(_read(value)[1]) for role, value in inputs.items()},
                "approval": validation, "annotation_protocol": protocol,
                "freeze_run": run, "created_at": datetime.now(timezone.utc).isoformat()}
        return _bundle(output_dir, {"gold.jsonl": contents, "gold-manifest.json": _json(seal),
                                    "annotation-summary.json": _json(summary)})
    except _CAUGHT:
        raise ValueError(_ERROR) from None


def _frozen(gold_dir: str | Path) -> tuple[list[dict[str, Any]], dict[str, Any], str]:
    directory = _path(gold_dir)
    _, manifest_data = _read(directory / "gold-manifest.json")
    seal = _decode(manifest_data)
    if type(seal["schema_version"]) is not int or seal["schema_version"] != 1 or seal["kind"] != "INDEPENDENT_HUMAN_GOLD":
        raise ValueError(_ERROR)
    relative = PurePosixPath(_text(seal["pack_manifest"]))
    if relative.is_absolute() or ".." in relative.parts or "\\" in str(relative):
        raise ValueError(_ERROR)
    path, pack, inputs, validation = _approved(_VAR_ROOT / str(relative))
    protocol = pack["gold_evaluation"]
    if (_digest(_read(path)[1]) != seal["pack_manifest_sha256"]
            or validation != seal["approval"] or protocol != seal["annotation_protocol"]
            or seal["gold_version"] != protocol["gold_version"] or seal["task"] != protocol["task"]
            or seal["labels"] != list(_LABELS[protocol["task"]])
            or seal["input_sha256"] != {role: _digest(_read(value)[1]) for role, value in inputs.items()}):
        raise ValueError(_ERROR)
    records, summary = _gold(pack, inputs)
    _, data = _read(directory / "gold.jsonl")
    expected = b"".join(_json(record) for record in records)
    if (data != expected or _digest(data) != _sha(seal["gold_sha256"])
            or len(records) != seal["item_count"]
            or summary["adjudication"]["excluded_count"] != seal["excluded_count"]
            or _read(directory / "annotation-summary.json")[1] != _json(summary)):
        raise ValueError(_ERROR)
    return records, seal, _digest(manifest_data)


def _predictions(data: bytes, gold: Sequence[dict[str, Any]], task: str,
                 run: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    predictions = _indexed(_rows(data))
    frozen = _indexed(gold)
    if predictions.keys() != frozen.keys():
        raise ValueError(_ERROR)
    required = {"schema_version", "item_id", "task", "metadata", "label", "score", "evidence", "run"}
    for item, row in predictions.items():
        record = frozen[item]
        if (set(row) != required or type(row["schema_version"]) is not int or row["schema_version"] != 1 or row["task"] != task
                or row["metadata"] != record["metadata"] or _json(row["run"]) != _json(run)):
            raise ValueError(_ERROR)
        label = row["label"]
        abstain = label is None or label == "NOT_RUN"
        if not abstain and label not in _LABELS[task]:
            raise ValueError(_ERROR)
        if abstain:
            if row["score"] is not None or row["evidence"] != {}:
                raise ValueError(_ERROR)
            row["label"] = "ABSTAIN"
            row["evidence"] = {"report_intervals": [], "source_intervals": []} if task == "similarity" else {"span_ids": []}
            continue
        if row["score"] is not None and (type(row["score"]) not in (int, float) or not math.isfinite(row["score"])):
            raise ValueError(_ERROR)
        evidence = row["evidence"]
        if not isinstance(evidence, dict):
            raise ValueError(_ERROR)
        context = record["context"]
        if task == "similarity":
            if set(evidence) != {"report_intervals", "source_intervals"}:
                raise ValueError(_ERROR)
            for side in ("report", "source"):
                evidence[f"{side}_intervals"] = _intervals(evidence[f"{side}_intervals"], len(context[f"{side}_text"]))
            if label == "NONE" and any(evidence.values()):
                raise ValueError(_ERROR)
        else:
            if set(evidence) != {"span_ids"} or not isinstance(evidence["span_ids"], list):
                raise ValueError(_ERROR)
            ids = evidence["span_ids"]
            known = {span["span_id"] for span in context["evidence_spans"]}
            if (any(not isinstance(value, str) for value in ids) or len(ids) != len(set(ids))
                    or not set(ids).issubset(known) or (label == "CANNOT_ASSESS" and ids)):
                raise ValueError(_ERROR)
    return predictions


def _prf(tp: int, predicted: int, gold: int) -> dict[str, float | None]:
    return {"precision": tp / predicted if predicted else None,
            "recall": tp / gold if gold else None,
            "f1": 2 * tp / (predicted + gold) if predicted + gold else None}


def _overlap(first: Sequence[Sequence[int]], second: Sequence[Sequence[int]]) -> int:
    a, b = _union(first), _union(second)
    i = j = total = 0
    while i < len(a) and j < len(b):
        total += max(0, min(a[i][1], b[j][1]) - max(a[i][0], b[j][0]))
        if a[i][1] <= b[j][1]:
            i += 1
        else:
            j += 1
    return total


def _metrics(gold: Sequence[dict[str, Any]], predictions: Mapping[str, dict[str, Any]], task: str) -> dict[str, Any]:
    labels = _LABELS[task]
    matrix = {label: {other: 0 for other in (*labels, "ABSTAIN")} for label in labels}
    for record in gold:
        matrix[record["label"]][predictions[record["item_id"]]["label"]] += 1
    per_class: dict[str, Any] = {}
    for label in labels:
        tp = matrix[label][label]
        support = sum(matrix[label].values())
        predicted = sum(matrix[other][label] for other in labels)
        per_class[label] = {**_prf(tp, predicted, support), "support": support,
                            "true_positive": tp, "false_positive": predicted - tp, "false_negative": support - tp}
    f1s = [value["f1"] if value["f1"] is not None else 0.0 for value in per_class.values()]
    present_f1s = [value["f1"] for value in per_class.values() if value["support"]]
    total = len(gold)
    abstained = sum(row["ABSTAIN"] for row in matrix.values())
    accepted = total - abstained
    correct = sum(matrix[label][label] for label in labels)
    evidence_tp = evidence_predicted = evidence_gold = 0
    gold_with_evidence = predicted_with_evidence = 0
    for record in gold:
        actual = record["evidence"]
        predicted = predictions[record["item_id"]]["evidence"]
        if task == "similarity":
            actual_count = predicted_count = overlap = 0
            for side in ("report_intervals", "source_intervals"):
                actual_count += sum(end - start for start, end in _union(actual[side]))
                predicted_count += sum(end - start for start, end in _union(predicted[side]))
                overlap += _overlap(actual[side], predicted[side])
        else:
            actual_ids, predicted_ids = set(actual["span_ids"]), set(predicted["span_ids"])
            actual_count, predicted_count, overlap = len(actual_ids), len(predicted_ids), len(actual_ids & predicted_ids)
        evidence_tp += overlap
        evidence_predicted += predicted_count
        evidence_gold += actual_count
        gold_with_evidence += bool(actual_count)
        predicted_with_evidence += bool(predicted_count)
    return {"schema_version": 1, "task": task, "item_count": total,
            "classification": {"per_class": per_class, "macro_f1": sum(f1s) / len(f1s) if f1s else None,
                               "macro_f1_class_count": len(f1s), "macro_f1_denominator": "all configured classes; absent undefined class f1 contributes zero",
                               "macro_f1_present_gold": sum(present_f1s) / len(present_f1s) if present_f1s else None,
                               "macro_f1_present_gold_class_count": len(present_f1s),
                               "zero_gold_support_classes": [label for label in labels if not per_class[label]["support"]],
                               "confusion_matrix_gold_rows_prediction_columns": matrix,
                               "correct_count": correct, "accepted_count": accepted, "abstained_count": abstained,
                               "accuracy": correct / total if total else None,
                               "coverage": accepted / total if total else None,
                               "selective_accuracy": correct / accepted if accepted else None},
            "evidence": {"unit": "pair_context_character_union" if task == "similarity" else "item_context_span_id",
                         "comparable_item_count": total, "gold_with_evidence_count": gold_with_evidence,
                         "predicted_with_evidence_count": predicted_with_evidence,
                         "overlap_count": evidence_tp, "predicted_count": evidence_predicted, "gold_count": evidence_gold,
                         **_prf(evidence_tp, evidence_predicted, evidence_gold),
                         "denominator": "micro totals over all frozen items, including abstentions; report and source counted separately",
                         "undefined_policy": "null for zero precision/recall denominators; f1 null only when both evidence totals are zero"}}


def evaluate(*, gold_dir: str | Path, predictions: str | Path, run_metadata: Mapping[str, Any],
             config: str | Path, output_dir: str | Path) -> Path:
    """Compare the complete prediction set only after revalidating current approval."""
    try:
        records, seal, seal_sha = _frozen(gold_dir)
        task = seal["task"]
        run = _run(run_metadata, config, task)
        _, contents = _read(predictions)
        accepted = _predictions(contents, records, task, run)
        metrics = _metrics(records, accepted, task)
        metrics_data = _json(metrics)
        checked_records, checked_seal, checked_sha = _frozen(gold_dir)
        if (checked_records != records or checked_seal != seal or checked_sha != seal_sha
                or _read(predictions)[1] != contents or _run(run_metadata, config, task) != run):
            raise ValueError(_ERROR)
        provenance = {"schema_version": 1, "kind": "GOLD_EVALUATION", "task": task,
                      "gold_version": seal["gold_version"], "gold_sha256": seal["gold_sha256"],
                      "gold_manifest_sha256": seal_sha, "pack_manifest_sha256": seal["pack_manifest_sha256"],
                      "predictions_sha256": _digest(contents), "metrics_sha256": _digest(metrics_data),
                      "run": run, "created_at": datetime.now(timezone.utc).isoformat()}
        return _bundle(output_dir, {"metrics.json": metrics_data, "evaluation-manifest.json": _json(provenance)})
    except _CAUGHT:
        raise ValueError(_ERROR) from None


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    seal = subcommands.add_parser("freeze")
    seal.add_argument("--task", choices=tuple(_LABELS), required=True)
    for name in ("annotator-a", "annotator-b", "adjudication", "context", "pack-manifest"):
        seal.add_argument(f"--{name}", type=Path, required=True)
    seal.add_argument("--gold-version", required=True)
    score = subcommands.add_parser("evaluate")
    score.add_argument("--gold-dir", type=Path, required=True)
    score.add_argument("--predictions", type=Path, required=True)
    for command in (seal, score):
        command.add_argument("--run-metadata", type=Path, required=True)
        command.add_argument("--config", type=Path, required=True)
        command.add_argument("--output-dir", type=Path, required=True)
    args = vars(parser.parse_args(argv))
    command = args.pop("command")
    try:
        args["run_metadata"] = _decode(_read(args["run_metadata"])[1])
        (freeze if command == "freeze" else evaluate)(**args)
    except _CAUGHT:
        print(_ERROR, file=sys.stderr)
        return 2
    print(json.dumps({"status": "FROZEN" if command == "freeze" else "EVALUATED"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
