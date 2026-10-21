"""Validate two blinded sheets and summarize human agreement locally.

The output contains aggregate counts and input hashes, never excerpts or item IDs.
Model predictions are deliberately outside this workflow: the sheets must be
sealed and dataset governance approved before any model comparison.
"""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any, Mapping, Sequence


_VAR_ROOT = Path(__file__).resolve().parents[2] / "var"
_SIMILARITY_LABELS = ("VERBATIM", "PARAPHRASE", "SUMMARY", "NONE")
_ASSESSMENT_LABELS = ("MET", "UNMET", "CANNOT_ASSESS")
_RELATION_FOR_OUTCOME = {
    "MET": "SUPPORTED",
    "UNMET": "CONTRADICTED",
    "CANNOT_ASSESS": "INSUFFICIENT",
}
_SIMILARITY_FIELDS = (
    "pair_id", "report_chunk_id", "source_chunk_id", "source_name",
    "report_text", "source_text", "report_page", "source_page", "label",
    "report_evidence_quote", "source_evidence_quote", "quote_or_citation",
    "confidence", "rationale",
)
_ASSESSMENT_FIELDS = (
    "item_id", "report_id", "report_version", "rubric_id", "rubric_version",
    "checklist_id", "label", "verification_relation", "evidence_span_ids",
    "rationale",
)
_ADJUDICATION_FIELDS = (
    "quy_label", "yen_label", "final_label", "decision_rationale",
    "decision_by", "decided_at",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_csv(path: Path, fields: Sequence[str], id_field: str) -> dict[str, dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None or len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise ValueError(f"{path.name}: missing or duplicated CSV header")
        missing = set(fields) - set(reader.fieldnames)
        if missing:
            raise ValueError(f"{path.name}: missing required columns {sorted(missing)}")
        result: dict[str, dict[str, str]] = {}
        for line_number, row in enumerate(reader, 2):
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"{path.name}: malformed CSV row {line_number}")
            identifier = row[id_field].strip()
            if not identifier:
                raise ValueError(f"{path.name}: empty {id_field} at row {line_number}")
            if identifier in result:
                raise ValueError(f"{path.name}: duplicate {id_field} at row {line_number}")
            result[identifier] = row
    if not result:
        raise ValueError(f"{path.name}: no annotation rows")
    return result


def _check_sheet(rows: Mapping[str, Mapping[str, str]], task: str, sheet_name: str) -> None:
    labels = _SIMILARITY_LABELS if task == "similarity" else _ASSESSMENT_LABELS
    for row_number, row in enumerate(rows.values(), 2):
        label = row["label"].strip()
        if label not in (*labels, "UNSURE"):
            raise ValueError(f"{sheet_name}: invalid or missing label at row {row_number}")
        if not row["rationale"].strip():
            raise ValueError(f"{sheet_name}: missing rationale at row {row_number}")
        if task == "similarity":
            if row["confidence"].strip() not in ("HIGH", "MEDIUM", "LOW"):
                raise ValueError(f"{sheet_name}: invalid confidence at row {row_number}")
            if row["quote_or_citation"].strip() not in ("YES", "NO", "UNSURE"):
                raise ValueError(f"{sheet_name}: invalid quote_or_citation at row {row_number}")
            if label in _SIMILARITY_LABELS[:3]:
                for quote_field, text_field in (
                    ("report_evidence_quote", "report_text"),
                    ("source_evidence_quote", "source_text"),
                ):
                    quote = row[quote_field]
                    # pilot_pack escapes spreadsheet formula prefixes with a
                    # single apostrophe; it is not part of the original span.
                    text = row[text_field]
                    if text.startswith("'") and text[1:].lstrip().startswith(("=", "+", "-", "@")):
                        text = text[1:]
                    if not quote.strip() or quote not in text:
                        raise ValueError(
                            f"{sheet_name}: {quote_field} must be an exact excerpt at row {row_number}"
                        )
        else:
            for field in ("report_id", "report_version", "rubric_id", "rubric_version", "checklist_id"):
                if not row[field].strip():
                    raise ValueError(f"{sheet_name}: missing {field} at row {row_number}")
            relation = row["verification_relation"].strip()
            if label == "UNSURE":
                if relation and relation not in _RELATION_FOR_OUTCOME.values():
                    raise ValueError(f"{sheet_name}: invalid relation at row {row_number}")
            elif relation != _RELATION_FOR_OUTCOME[label]:
                raise ValueError(f"{sheet_name}: outcome/relation conflict at row {row_number}")
            if label in ("MET", "UNMET") and not row["evidence_span_ids"].strip():
                raise ValueError(f"{sheet_name}: missing evidence_span_ids at row {row_number}")


def _agreement(
    first: Mapping[str, Mapping[str, str]],
    second: Mapping[str, Mapping[str, str]],
    labels: Sequence[str],
) -> dict[str, Any]:
    resolved = [
        (first[item]["label"].strip(), second[item]["label"].strip())
        for item in first
        if first[item]["label"].strip() != "UNSURE"
        and second[item]["label"].strip() != "UNSURE"
    ]
    total = len(resolved)
    matrix = {
        label: {other: sum(a == label and b == other for a, b in resolved) for other in labels}
        for label in labels
    }
    if total == 0:
        raw, kappa = None, None
    else:
        raw = sum(a == b for a, b in resolved) / total
        count_a = Counter(a for a, _ in resolved)
        count_b = Counter(b for _, b in resolved)
        expected = sum(count_a[label] * count_b[label] for label in labels) / total**2
        # When both annotators use one identical class, chance agreement is 1;
        # Cohen's kappa is mathematically undefined, not zero or one.
        kappa = None if expected == 1 else (raw - expected) / (1 - expected)
    return {
        "both_resolved_count": total,
        "unsure_in_either_sheet_count": len(first) - total,
        "exact_agreement_count": sum(a == b for a, b in resolved),
        "exact_agreement_rate": raw,
        "cohen_kappa": kappa,
        "confusion_matrix_a_rows_b_columns": matrix,
    }


def summarize(
    *,
    task: str,
    annotator_a: str | Path,
    annotator_b: str | Path,
    adjudication: str | Path | None = None,
) -> dict[str, Any]:
    """Return aggregate annotation diagnostics with no raw text or item IDs."""

    if task not in ("similarity", "assessment"):
        raise ValueError("task must be similarity or assessment")
    id_field = "pair_id" if task == "similarity" else "item_id"
    fields = _SIMILARITY_FIELDS if task == "similarity" else _ASSESSMENT_FIELDS
    labels = _SIMILARITY_LABELS if task == "similarity" else _ASSESSMENT_LABELS
    a_path = Path(annotator_a).expanduser().resolve(strict=True)
    b_path = Path(annotator_b).expanduser().resolve(strict=True)
    if a_path == b_path:
        raise ValueError("Annotator sheets must be distinct files")
    first = _read_csv(a_path, fields, id_field)
    second = _read_csv(b_path, fields, id_field)
    if first.keys() != second.keys():
        raise ValueError("Annotator sheets must contain identical item IDs")
    _check_sheet(first, task, a_path.name)
    _check_sheet(second, task, b_path.name)
    metadata_fields = (
        ("report_chunk_id", "source_chunk_id", "source_name", "report_text", "source_text", "report_page", "source_page")
        if task == "similarity"
        else ("report_id", "report_version", "rubric_id", "rubric_version", "checklist_id")
    )
    for item in first:
        if any(first[item][field] != second[item][field] for field in metadata_fields):
            raise ValueError("Annotator sheets have mismatched item metadata")

    agreement = _agreement(first, second, labels)
    result: dict[str, Any] = {
        "task": task,
        "item_count": len(first),
        "annotation_counts": {
            "a": dict(sorted(Counter(row["label"].strip() for row in first.values()).items())),
            "b": dict(sorted(Counter(row["label"].strip() for row in second.values()).items())),
        },
        "agreement": agreement,
        "input_sha256": {"annotator_a": _sha256(a_path), "annotator_b": _sha256(b_path)},
        "adjudication": {"status": "NOT_PROVIDED", "unresolved_count": None},
        "gold_label_counts": None,
    }
    if adjudication is None:
        return result

    final_path = Path(adjudication).expanduser().resolve(strict=True)
    final = _read_csv(final_path, (id_field, *_ADJUDICATION_FIELDS), id_field)
    if final.keys() != first.keys():
        raise ValueError("Adjudication sheet must contain identical item IDs")
    if task == "assessment" and any("final_verification_relation" not in row for row in final.values()):
        raise ValueError("Assessment adjudication requires final_verification_relation column")
    gold: Counter[str] = Counter()
    unresolved = excluded = adjudicated = 0
    for item in first:
        a_label = first[item]["label"].strip()
        b_label = second[item]["label"].strip()
        row = final[item]
        if row["quy_label"].strip() not in ("", a_label) or row["yen_label"].strip() not in ("", b_label):
            raise ValueError("Adjudication copied labels disagree with independent sheets")
        label = row["final_label"].strip()
        agreed = a_label == b_label and a_label != "UNSURE"
        if not label and agreed:
            label = a_label
        elif not label:
            unresolved += 1
            continue
        if label not in (*labels, "EXCLUDE"):
            raise ValueError("Adjudication contains an invalid final label")
        relation = row.get("final_verification_relation", "").strip()
        if task == "assessment" and label in labels:
            agreed_relation = first[item]["verification_relation"].strip()
            if not relation and agreed:
                relation = agreed_relation
            if relation != _RELATION_FOR_OUTCOME[label]:
                raise ValueError("Adjudicated outcome/relation conflict")
        if task == "assessment" and label == "EXCLUDE" and relation:
            raise ValueError("Excluded assessment item must not have a final relation")
        if not agreed or label != a_label or label == "EXCLUDE":
            if not all(row[field].strip() for field in ("decision_rationale", "decision_by", "decided_at")):
                raise ValueError("Changed/disputed labels require rationale, decider and date")
            decided_at = row["decided_at"].strip()
            try:
                if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", decided_at):
                    raise ValueError("wrong date format")
                date.fromisoformat(decided_at)
            except ValueError as exc:
                raise ValueError("Adjudication dates must be ISO YYYY-MM-DD") from exc
            adjudicated += 1
        if label == "EXCLUDE":
            excluded += 1
        else:
            gold[label] += 1
    result["input_sha256"]["adjudication"] = _sha256(final_path)
    result["adjudication"] = {
        "status": "COMPLETE" if unresolved == 0 else "INCOMPLETE",
        "unresolved_count": unresolved,
        "excluded_count": excluded,
        "adjudicated_count": adjudicated,
    }
    # A partial label distribution is not a sealed gold set.
    if unresolved == 0:
        result["gold_label_counts"] = dict(sorted(gold.items()))
    return result


def write_summary(summary: Mapping[str, Any], output_dir: str | Path) -> Path:
    output = Path(output_dir).expanduser().resolve()
    root = _VAR_ROOT.resolve()
    if not output.is_relative_to(root) or output == root:
        raise ValueError("output_dir must be a new directory under the ignored repository var/")
    if output.exists():
        raise FileExistsError("Refusing to overwrite an annotation summary")
    output.mkdir(parents=True, mode=0o700)
    os.chmod(output, 0o700)
    path = output / "annotation-summary.json"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(summary, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
    return path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", choices=("similarity", "assessment"), required=True)
    parser.add_argument("--annotator-a", required=True, type=Path)
    parser.add_argument("--annotator-b", required=True, type=Path)
    parser.add_argument("--adjudication", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    summary = summarize(
        task=args.task,
        annotator_a=args.annotator_a,
        annotator_b=args.annotator_b,
        adjudication=args.adjudication,
    )
    path = write_summary(summary, args.output_dir)
    print(json.dumps({"summary": str(path), "adjudication_status": summary["adjudication"]["status"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
