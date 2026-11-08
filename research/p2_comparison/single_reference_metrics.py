"""Compare P2 decisions with a single, declared human reference.

This is exploratory reference-label agreement, not consensus gold evaluation.
Source-bound citations never automatically count as semantically correct proof.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import itertools
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
VAR_ROOT = ROOT / "var"
LABELS = ("MET", "UNMET", "CANNOT_ASSESS")
TECHNICAL = "TECHNICAL_ABSTENTION"
IDENTITY = ("report_id", "report_version", "body_sha256", "rubric_id", "rubric_version", "checklist_id")
MAX_JSON_BYTES = 64 * 1024 * 1024


def _identity(row: Mapping[str, Any]) -> dict[str, str]:
    metadata = row.get("metadata")
    if not isinstance(metadata, dict) or any(not isinstance(metadata.get(k), str) or not metadata[k] for k in IDENTITY):
        raise ValueError("Each item requires its complete reference metadata identity")
    return {key: metadata[key] for key in IDENTITY}


def _index(rows: Sequence[Mapping[str, Any]], *, reference: bool) -> dict[str, dict[str, Any]]:
    if not isinstance(rows, list) or not rows:
        raise ValueError("A nonempty list of complete item records is required")
    indexed, case_checklists = {}, set()
    for source in rows:
        if not isinstance(source, dict):
            raise ValueError("Invalid item record")
        item, case = source.get("item_id"), source.get("case_id")
        if not isinstance(item, str) or not item or not isinstance(case, str) or not case:
            raise ValueError("Each item requires stable item_id and case_id")
        metadata = _identity(source)
        pair = (case, metadata["checklist_id"])
        if item in indexed or pair in case_checklists:
            raise ValueError("Duplicate item or case-checklist identity")
        case_checklists.add(pair)
        if source.get("checklist_id", metadata["checklist_id"]) != metadata["checklist_id"]:
            raise ValueError("Conflicting checklist identity")
        if reference:
            label = source.get("label")
            if label not in LABELS or source.get("state", "VALID") != "VALID":
                raise ValueError("Reference items must have resolved, valid labels")
            decision_status = "REFERENCE_LABEL"
        else:
            if "accepted_label" not in source:
                raise ValueError("Prediction is missing an explicit accepted_label")
            label, decision_status = source["accepted_label"], source.get("decision_status")
            if label is None:
                if decision_status != TECHNICAL:
                    raise ValueError("Null decisions must be explicit technical abstentions")
            elif label not in LABELS or decision_status != "SEMANTIC_DECISION":
                raise ValueError("Accepted labels must be semantic decisions in the declared label set")
            diagnostics = source.get("raw_result", {}).get("llm_verification", {})
            if diagnostics.get("status") == "WITHHELD" and label is not None:
                raise ValueError("A withheld result cannot be counted as a semantic decision")
        indexed[item] = {"item_id": item, "case_id": case, "metadata": metadata,
                         "label": label, "decision_status": decision_status}
    return indexed


def _pool(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    reference_counts = Counter(row["reference_label"] for row in rows)
    predicted_counts = Counter(row["predicted_label"] for row in rows if row["predicted_label"] is not None)
    accepted = sum(row["predicted_label"] is not None for row in rows)
    matching = sum(row["label_match"] for row in rows)
    confusion = {label: {column: 0 for column in (*LABELS, TECHNICAL)} for label in LABELS}
    for row in rows:
        confusion[row["reference_label"]][row["predicted_label"] or TECHNICAL] += 1
    per_class = {}
    for label in LABELS:
        tp = sum(row["reference_label"] == row["predicted_label"] == label for row in rows)
        fp = sum(row["reference_label"] != label and row["predicted_label"] == label for row in rows)
        fn = sum(row["reference_label"] == label and row["predicted_label"] != label for row in rows)
        support, predictions = reference_counts[label], predicted_counts[label]
        per_class[label] = {
            "reference_support": support, "predicted_support": predictions,
            "true_positive": tp, "false_positive": fp, "false_negative": fn,
            "precision": tp / predictions if predictions else None,
            "recall": tp / support if support else None,
            # An unsupported reference class is not an evaluated class, even if predicted.
            "f1": 2 * tp / (2 * tp + fp + fn) if support else None,
            "reference_class_evaluated": support > 0,
        }
    observed = [label for label in LABELS if reference_counts[label]]
    return {
        "items": total, "accepted_decisions": accepted, "technical_abstentions": total - accepted,
        "accepted_coverage": accepted / total if total else None,
        "reference_label_agreement": {"matching": matching, "denominator": total,
                                      "rate": matching / total if total else None,
                                      "technical_abstentions_count_as_mismatches": True},
        "accepted_only_agreement": {"matching": matching, "denominator": accepted,
                                    "rate": matching / accepted if accepted else None},
        "reference_label_counts": {label: reference_counts[label] for label in LABELS},
        "predicted_label_counts": {label: predicted_counts[label] for label in LABELS},
        "confusion_matrix": confusion, "per_class": per_class,
        "macro_f1_observed_reference_classes": (
            sum(per_class[label]["f1"] for label in observed) / len(observed) if observed else None),
        "macro_f1_observed_labels": observed,
        "macro_f1_fixed_three_class": (
            sum(per_class[label]["f1"] for label in LABELS) / len(LABELS) if len(observed) == len(LABELS) else None),
        "unsupported_reference_classes": [label for label in LABELS if not reference_counts[label]],
        "zero_denominator_policy": "Undefined precision/recall are null; F1 for absent reference classes is null and excluded from observed-class macro F1.",
    }


def summarize(
    reference_rows: list[dict[str, Any]], predictions_by_method: Mapping[str, list[dict[str, Any]]], *,
    reference_sha256: str | None = None, expected_items: int | None = None,
) -> dict[str, Any]:
    """Require every item once per method; never silently drop technical failures."""
    references = _index(reference_rows, reference=True)
    if expected_items is not None and (type(expected_items) is not int or expected_items < 1 or len(references) != expected_items):
        raise ValueError("Reference item count differs from the frozen expected count")
    if not isinstance(predictions_by_method, dict) or not predictions_by_method:
        raise ValueError("At least one complete method prediction list is required")
    methods, comparison_rows, method_rows = {}, [], {}
    for method, prediction_rows in predictions_by_method.items():
        if not isinstance(method, str) or not method.strip():
            raise ValueError("Method identifiers must be nonempty strings")
        predictions = _index(prediction_rows, reference=False)
        if set(predictions) != set(references):
            raise ValueError("Method and reference item sets differ; missing records cannot be silently excluded")
        aligned = []
        for item, reference in references.items():
            prediction = predictions[item]
            if reference["case_id"] != prediction["case_id"] or reference["metadata"] != prediction["metadata"]:
                raise ValueError("Prediction and reference version identities differ")
            row = {"method": method, "item_id": item, "case_id": reference["case_id"],
                   "checklist_id": reference["metadata"]["checklist_id"],
                   "reference_label": reference["label"], "predicted_label": prediction["label"],
                   "decision_status": prediction["decision_status"],
                   "label_match": reference["label"] == prediction["label"],
                   "evidence_semantics_evaluated": False}
            aligned.append(row)
        method_rows[method] = aligned
        grouped = _pool(aligned)
        grouped["per_checklist"] = {
            checklist: _pool([row for row in aligned if row["checklist_id"] == checklist])
            for checklist in sorted({row["checklist_id"] for row in aligned})}
        grouped["per_report"] = {
            case: _pool([row for row in aligned if row["case_id"] == case])
            for case in sorted({row["case_id"] for row in aligned})}
        methods[method] = grouped
        comparison_rows.extend(aligned)
    baseline_rows = [{"reference_label": row["label"], "predicted_label": "MET",
                      "label_match": row["label"] == "MET"} for row in references.values()]
    paired = {}
    for left, right in itertools.combinations(method_rows, 2):
        a, b = method_rows[left], method_rows[right]
        paired[left + "__vs__" + right] = {
            "items": len(a), "both_match_reference": sum(x["label_match"] and y["label_match"] for x, y in zip(a, b)),
            "only_first_matches": sum(x["label_match"] and not y["label_match"] for x, y in zip(a, b)),
            "only_second_matches": sum(not x["label_match"] and y["label_match"] for x, y in zip(a, b)),
            "neither_matches": sum(not x["label_match"] and not y["label_match"] for x, y in zip(a, b)),
            "agreement_rate_second_minus_first": (
                sum(row["label_match"] for row in b) - sum(row["label_match"] for row in a)) / len(a),
            "causal_or_significance_claim": False,
        }
    return {
        "schema_version": 1, "classification": "SINGLE_REFERENCE_EXPLORATORY_LABEL_AGREEMENT_NOT_CONSENSUS_GOLD",
        "annotation_design": "SINGLE_ANNOTATOR_AI_ASSISTED", "reference_sha256": reference_sha256,
        "items": len(references), "reports": len({row["case_id"] for row in references.values()}),
        "methods": methods, "always_met_baseline": _pool(baseline_rows),
        "paired_method_comparisons": paired, "comparison_rows": comparison_rows,
        "inter_annotator_agreement": None, "cohen_kappa": None,
        "evidence_semantic_support_evaluated": False, "gold_approval_asserted": False,
        "limitations": [
            "Single AI-assisted human reference; no independent multi-rater consensus or inter-annotator agreement.",
            "Reference-label agreement does not establish full rubric grading accuracy or teacher-score agreement.",
            "Source-bound citation validity and semantic support are different; this evaluator computes labels only.",
            "Absent reference classes have no measured recall/F1; checklist groups with one class do not measure class discrimination.",
            "Technical abstentions remain in the full denominator and are not semantic CANNOT_ASSESS predictions.",
        ],
    }


def _read(path: Path) -> tuple[Any, str]:
    path = path.absolute()
    if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file() or path.stat().st_size > MAX_JSON_BYTES:
        raise ValueError("Evaluation input must be a bounded regular JSON file without symlinks")
    raw = path.read_bytes()
    def unique(pairs):
        values = {}
        for key, value in pairs:
            if key in values:
                raise ValueError("Duplicate JSON key")
            values[key] = value
        return values
    def reject(_):
        raise ValueError("Non-finite JSON number")
    return json.loads(raw.decode("utf-8"), object_pairs_hook=unique, parse_constant=reject), hashlib.sha256(raw).hexdigest()


def _percent(value: float | None) -> str:
    return "—" if value is None else f"{100 * value:.2f}%"


def render_markdown(metrics: Mapping[str, Any]) -> str:
    lines = ["# Kết quả P2 — đánh giá thăm dò với một người gán nhãn", "",
             f"Bộ tham chiếu: {metrics['reports']} bài, {metrics['items']} mục; một người gán nhãn có AI hỗ trợ.",
             "Không tính đồng thuận hai người. Các tỷ lệ dưới đây đo khớp nhãn tham chiếu, chưa chứng nhận chất lượng bằng chứng hoặc điểm chấm toàn bài.", "",
             "| Phương pháp | Khớp nhãn / tổng | Tỷ lệ | Quyết định được chấp nhận | Lỗi kỹ thuật | Macro F1 trên lớp có mẫu tham chiếu |",
             "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for name, method in metrics["methods"].items():
        agreement = method["reference_label_agreement"]
        lines.append(f"| {name} | {agreement['matching']}/{agreement['denominator']} | {_percent(agreement['rate'])} | {method['accepted_decisions']}/{method['items']} | {method['technical_abstentions']} | {_percent(method['macro_f1_observed_reference_classes'])} |")
    baseline = metrics["always_met_baseline"]["reference_label_agreement"]
    lines.extend([f"| Luôn đoán MET | {baseline['matching']}/{baseline['denominator']} | {_percent(baseline['rate'])} | — | — | {_percent(metrics['always_met_baseline']['macro_f1_observed_reference_classes'])} |", "",
                  "Lỗi timeout/schema/proof thuộc lỗi kỹ thuật: không đổi thành CANNOT_ASSESS đúng. Mẫu lỗi vẫn nằm trong mẫu số đầy đủ; tỷ lệ chỉ trên các quyết định được chấp nhận được lưu riêng trong JSON.", ""])
    for name, method in metrics["methods"].items():
        lines.extend([f"## {name}: từng checklist", "",
                      "| Checklist | Khớp / tổng | Tỷ lệ | MET / UNMET / CA tham chiếu |",
                      "| --- | ---: | ---: | ---: |"])
        for checklist, group in method["per_checklist"].items():
            agreement, support = group["reference_label_agreement"], group["reference_label_counts"]
            lines.append(f"| {checklist} | {agreement['matching']}/{agreement['denominator']} | {_percent(agreement['rate'])} | {support['MET']} / {support['UNMET']} / {support['CANNOT_ASSESS']} |")
        lines.append("")
        if method["unsupported_reference_classes"]:
            lines.append("Lớp không có mẫu tham chiếu: " + ", ".join(method["unsupported_reference_classes"]) + ". Không suy khả năng nhận diện các lớp này từ kết quả hiện tại.")
        lines.append("")
    lines.extend(["## Cách đọc và giới hạn", "",
                  "- Cần so kết quả với baseline luôn MET, nhất là khi phân bố nhãn lệch.",
                  "- Macro F1 chính chỉ lấy các lớp có mẫu tham chiếu; macro F1 cố định ba lớp để null khi thiếu lớp. Precision/recall không có mẫu số để null.",
                  "- Checklist có toàn MET chưa đánh giá được phân biệt MET và UNMET.",
                  "- Nhãn một người có AI hỗ trợ là nguồn tham chiếu thăm dò, không phải gold độc lập đa giám khảo.",
                  "- Cần đọc thủ công các căn cứ trước khi kết luận bằng chứng thực sự hỗ trợ quyết định. Trích đúng nguồn chưa đồng nghĩa lập luận đúng.", "",
                  "`comparison.csv` giữ toàn bộ mục; `mismatches.csv` lọc các mục lệch nhãn hoặc lỗi kỹ thuật. Không sửa nhãn tham chiếu hay phương pháp sau khi nhìn kết quả rồi gọi lượt chạy mới là holdout.", ""])
    return "\n".join(lines)


def write_evaluation(
    *, reference_path: Path, predictions_path: Path, output_dir: Path,
    expected_items: int | None = None, expected_reference_sha256: str | None = None,
) -> dict[str, Any]:
    reference, reference_sha = _read(Path(reference_path))
    predictions, predictions_sha = _read(Path(predictions_path))
    if expected_reference_sha256 is not None and reference_sha != expected_reference_sha256:
        raise ValueError("Frozen reference checksum mismatch")
    result = summarize(reference["rows"], predictions["methods"], reference_sha256=reference_sha,
                       expected_items=expected_items)
    result["predictions_sha256"] = predictions_sha
    output = Path(output_dir).absolute()
    if ".." in output.parts or output == VAR_ROOT.absolute() or not output.is_relative_to(VAR_ROOT.absolute()) or any(p.is_symlink() for p in (output, *output.parents)):
        raise ValueError("Evaluation output must be below the private var directory")
    if output.exists():
        raise FileExistsError("Use a new evaluation directory; existing results are retained")
    output.mkdir(parents=True, mode=0o700)
    for name, rows in (("comparison.csv", result["comparison_rows"]),
                       ("mismatches.csv", [r for r in result["comparison_rows"] if not r["label_match"]])):
        with (output / name).open("x", encoding="utf-8-sig", newline="") as stream:
            fields = ["method", "item_id", "case_id", "checklist_id", "reference_label", "predicted_label",
                      "decision_status", "label_match", "evidence_semantics_evaluated"]
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                writer.writerow({key: "'" + value if isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r")) else value for key, value in row.items()})
    with (output / "metrics.json").open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    (output / "KET_QUA_P2_THAM_DO.md").write_text(render_markdown(result), encoding="utf-8")
    for path in output.iterdir():
        path.chmod(0o600)
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-items", type=int)
    parser.add_argument("--expected-reference-sha256")
    args = parser.parse_args(argv)
    result = write_evaluation(reference_path=args.reference, predictions_path=args.predictions,
        output_dir=args.output_dir, expected_items=args.expected_items,
        expected_reference_sha256=args.expected_reference_sha256)
    print(json.dumps({"classification": result["classification"], "items": result["items"],
                      "methods": {name: value["reference_label_agreement"] for name, value in result["methods"].items()}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
