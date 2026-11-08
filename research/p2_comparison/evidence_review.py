"""Prepare method-masked human evidence review; never infer semantic ratings.

Source geometry and model/reference label agreement are not human judgments of
whether the cited text supports a conclusion. This separate form covers every
conclusive decision, keeps method identities in a private mapping and leaves
all human fields empty. Missing/uncertain judgments remain visible in metrics.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path

from research.p2_comparison import runner as base


RATINGS = ("SUPPORTED", "PARTIAL", "UNSUPPORTED", "UNCERTAIN")
EXPOSURES = ("METHOD_MAPPING_NOT_SEEN", "METHOD_MAPPING_SEEN")
FIXED_FIELDS = ("review_id", "report_alias", "checklist_statement", "model_outcome",
                "model_rationale", "cited_evidence", "report_file")
HUMAN_FIELDS = ("support_rating", "reviewer", "method_exposure", "ai_assistance", "review_reason")
FIELDS = (*FIXED_FIELDS, *HUMAN_FIELDS)


def _id(value):
    return hashlib.sha256(base._canonical(value)).hexdigest()[:20]


def _csv_bytes(rows):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=FIELDS)
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8-sig")


def _text(value):
    """Prevent a source-controlled string from becoming a spreadsheet formula."""
    text = str(value)
    if text.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


def prepare_review(*, prepared_dir: Path, predictions_path: Path, output_dir: Path):
    prepared = Path(prepared_dir).resolve(strict=True)
    manifest = base._read_json(prepared / "preparation-manifest.json")
    if manifest.get("design") != "P2_RETRIEVAL_DEV_COMPARISON_V1":
        raise ValueError("Use a prepared retrieval DEV study, not an unversioned prediction dump")
    for relative, checksum in manifest["locked_files"].items():
        path = prepared / relative
        if (Path(relative).is_absolute() or ".." in Path(relative).parts
                or path.is_symlink() or not path.resolve().is_relative_to(prepared)
                or base._sha(path) != checksum):
            raise ValueError("Frozen review input changed")
    predictions_path = Path(predictions_path).resolve(strict=True)
    predictions = base._read_json(predictions_path)
    methods = predictions.get("methods")
    if (not isinstance(methods, dict) or set(methods) != set(manifest["methods"])
            or any(len(rows) != manifest["items_per_method"] for rows in methods.values())):
        raise ValueError("Review requires every prepared item for each executed method")
    out = base._private_output(Path(output_dir))
    reports = out / "reports"
    reports.mkdir(mode=0o700)
    forms, mapping, counts = [], {}, {}
    reference = base._read_json(prepared / "reference.json")
    reference_ids = {r["item_id"] for r in reference["rows"]}
    case_ids = {c["case_id"] for c in manifest["cases"]}
    for method, rows in methods.items():
        if len({r["item_id"] for r in rows}) != len(rows) or {r["item_id"] for r in rows} != reference_ids:
            raise ValueError("Duplicate or missing review item identity")
        counts[method] = {"predictions": len(rows), "conclusive": 0, "semantic_ca": 0, "technical": 0}
        for row in rows:
            label, status = row.get("accepted_label"), row.get("decision_status")
            if status == "TECHNICAL_ABSTENTION" and label is None:
                counts[method]["technical"] += 1
                continue
            if status != "SEMANTIC_DECISION" or label not in ("MET", "UNMET", "CANNOT_ASSESS"):
                raise ValueError("Invalid decision status or outcome")
            if label == "CANNOT_ASSESS":
                counts[method]["semantic_ca"] += 1
                continue
            case = row["case_id"]
            if case not in case_ids:
                raise ValueError("Unknown prepared case")
            items = base._read_json(prepared / "cases" / case / (method + ".json"))["items"]
            item = next((item for item in items if item["checklist"]["checklist_id"] == row["checklist_id"]), None)
            if (item is None or row.get("method_pack_sha256") != item["evidence_pack_sha256"]
                    or row.get("method_catalog_sha256") != item["source_units_sha256"]):
                raise ValueError("Prediction pack differs from prepared review source")
            raw = row["raw_result"]
            if raw.get("llm_verification", {}).get("status") != "VALIDATED":
                raise ValueError("A withheld prediction cannot be a semantic conclusion")
            alias = "report-" + _id({"body": row["metadata"]["body_sha256"]})
            body = prepared / "cases" / case / "body.txt"
            if base._sha(body) != row["metadata"]["body_sha256"]:
                raise ValueError("Report does not match reference body version")
            report_file = "reports/" + alias + ".txt"
            if not (out / report_file).exists():
                (out / report_file).write_bytes(body.read_bytes())
            identifier = "review-" + _id({"method": method, "item": row["item_id"],
                "prediction": base._digest(raw), "preparation": base._sha(prepared / "preparation-manifest.json")})
            if identifier in mapping:
                raise ValueError("Duplicate review identifier")
            proofs = raw.get("matched_evidence_spans", []) + raw.get("contradiction_hits", [])
            citations = [{"relation": hit.get("relation"), "evidence_id": hit.get("evidence_id"),
                "quote": hit.get("span", {}).get("text"), "span": hit.get("span")}
                for hit in proofs]
            fixed = {"review_id": identifier, "report_alias": alias,
                "checklist_statement": _text(item["checklist"]["statement"]),
                "model_outcome": label, "model_rationale": _text(raw.get("rationale", "")),
                "cited_evidence": _text(json.dumps(citations, ensure_ascii=False)), "report_file": report_file}
            forms.append({**fixed, **{key: "" for key in HUMAN_FIELDS}})
            mapping[identifier] = {"method": method, "item_id": row["item_id"], "case_id": case,
                "prediction_sha256": base._digest(raw), "fixed_fields": fixed}
            counts[method]["conclusive"] += 1
    forms.sort(key=lambda row: _id({"order": row["review_id"], "seed": "p2-evidence-audit-v1"}))
    template = _csv_bytes(forms)
    (out / "PHIEU_KIEM_BANG_CHUNG.csv").write_bytes(template)
    base._write(out / "private-method-mapping.json", mapping)
    report_hashes = {str(p.relative_to(out)): base._sha(p) for p in sorted(reports.glob("*.txt"))}
    receipt = {"schema_version": 1, "design": "METHOD_MASKED_HUMAN_SEMANTIC_SUPPORT_REVIEW_V1",
        "predictions_sha256": base._sha(predictions_path),
        "preparation_manifest_sha256": base._sha(prepared / "preparation-manifest.json"),
        "template_sha256": hashlib.sha256(template).hexdigest(),
        "mapping_sha256": base._sha(out / "private-method-mapping.json"), "report_hashes": report_hashes,
        "review_tool_sha256": base._sha(Path(__file__)),
        "methods": counts, "review_rows": len(forms), "all_human_fields_blank": True,
        "semantic_support_certified": False, "human_review_complete": False,
        "scope": "All conclusive predictions. CA and technical decisions are counted separately, not certified as grounded.",
        "masking_limit": "Method labels/order are masked; writing/citation style can still reveal workflow clues."}
    base._write(out / "review-receipt.json", receipt)
    instructions = """# Kiểm bằng chứng có thực sự hỗ trợ kết luận

Mở PHIEU_KIEM_BANG_CHUNG.csv. Mỗi dòng là một quyết định MET/UNMET; đọc
checklist, model_rationale, cited_evidence và report_file tương ứng.
Tên phương pháp bị che trong phiếu; không mở private-method-mapping.json
trước khi điền nếu muốn giữ điều kiện không biết phương pháp.

Chỉ điền năm cột cuối, giữ nguyên các cột đầu:
- support_rating: SUPPORTED (đủ căn cứ cho toàn bộ kết luận), PARTIAL
  (chỉ hỗ trợ một phần), UNSUPPORTED (không hỗ trợ/sai người/sai nguồn),
  UNCERTAIN (chưa xác định được). Quote đúng nguyên văn chưa đủ là SUPPORTED.
- reviewer: người thực sự kiểm; không ghi tên người khác hoặc công cụ làm người.
- method_exposure: METHOD_MAPPING_NOT_SEEN hoặc METHOD_MAPPING_SEEN, ghi thật.
- ai_assistance: ghi NONE hoặc mô tả công cụ/cách hỗ trợ thực tế.
- review_reason: lý do ngắn, chỉ rõ phần được/không được hỗ trợ.

Lưu bản đã điền thành CSV UTF-8 riêng rồi dùng lệnh summarize. Không sửa
template gốc. Công cụ không tự điền/đổi nhãn Yến hoặc đánh giá thay người.
CA và lỗi kỹ thuật được đếm riêng; phiếu này không đo độ đúng của CA.
Phần nguồn giữ nguyên phiên bản DEV, có thể còn đoạn giống feedback;
không lấy feedback của người chấm làm bằng chứng sinh viên đáp ứng yêu cầu.
"""
    (out / "README_KIEM_BANG_CHUNG.md").write_text(instructions, encoding="utf-8")
    for path in out.rglob("*"):
        if path.is_file():
            path.chmod(0o400)
    return {"status": "PREPARED_HUMAN_FIELDS_BLANK", "review_rows": len(forms), "output_dir": str(out)}


def summarize_review(*, review_dir: Path, completed_csv: Path, output_dir: Path):
    root = Path(review_dir).resolve(strict=True)
    receipt = base._read_json(root / "review-receipt.json")
    if (base._sha(root / "PHIEU_KIEM_BANG_CHUNG.csv") != receipt["template_sha256"]
            or base._sha(root / "private-method-mapping.json") != receipt["mapping_sha256"]
            or any(base._sha(root / relative) != checksum for relative, checksum in receipt["report_hashes"].items())):
        raise ValueError("Frozen review packet changed")
    mapping = base._read_json(root / "private-method-mapping.json")
    with Path(completed_csv).open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != list(FIELDS):
            raise ValueError("Review columns changed")
        rows = list(reader)
    if len(rows) != len(mapping) or {r["review_id"] for r in rows} != set(mapping):
        raise ValueError("Missing, duplicate or unknown review rows")
    by_method = {method: {**counts, "rated": 0, "pending": 0, "ratings": Counter(), "reviewers": set()}
                 for method, counts in receipt["methods"].items()}
    for row in rows:
        original = mapping[row["review_id"]]
        if any(row[key] != value for key, value in original["fixed_fields"].items()):
            raise ValueError("Immutable review identity or prediction changed")
        rating = row["support_rating"]
        summary = by_method[original["method"]]
        if not rating:
            if any(row[key].strip() for key in HUMAN_FIELDS):
                raise ValueError("Partial human record requires a support rating")
            summary["pending"] += 1
            continue
        if (rating not in RATINGS or row["method_exposure"] not in EXPOSURES
                or any(not row[key].strip() for key in ("reviewer", "ai_assistance", "review_reason"))):
            raise ValueError("Rated rows require a real reviewer, exposure, AI disclosure and reason")
        summary["rated"] += 1
        summary["ratings"][rating] += 1
        summary["reviewers"].add(row["reviewer"])
    for summary in by_method.values():
        rated = summary["rated"]
        summary["ratings"] = {rating: summary["ratings"][rating] for rating in RATINGS}
        summary["reviewers"] = sorted(summary["reviewers"])
        summary["conclusive_review_coverage"] = rated / summary["conclusive"] if summary["conclusive"] else None
        summary["fully_supported_rate_among_rated"] = summary["ratings"]["SUPPORTED"] / rated if rated else None
        summary["uncertain_kept_in_rated_denominator"] = True
    result = {"schema_version": 1, "design": receipt["design"], "methods": by_method,
        "complete": any(value["rated"] for value in by_method.values())
                    and all(not value["pending"] for value in by_method.values()),
        "completed_csv_sha256": base._sha(Path(completed_csv)),
        "label_accuracy_recomputed": False, "independent_gold_claim": False,
        "note": "Human support ratings are distinct from reference-label agreement and source geometry. Incomplete review cannot certify the full cohort."}
    out = base._private_output(Path(output_dir))
    base._write(out / "semantic-support-summary.json", result)
    (out / "returned-human-review.csv").write_bytes(Path(completed_csv).read_bytes())
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--prepared-dir", type=Path, required=True)
    prepare.add_argument("--predictions", type=Path, required=True)
    prepare.add_argument("--output-dir", type=Path, required=True)
    summarize = commands.add_parser("summarize")
    summarize.add_argument("--review-dir", type=Path, required=True)
    summarize.add_argument("--completed-csv", type=Path, required=True)
    summarize.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "prepare":
        result = prepare_review(prepared_dir=args.prepared_dir, predictions_path=args.predictions, output_dir=args.output_dir)
    else:
        result = summarize_review(review_dir=args.review_dir, completed_csv=args.completed_csv, output_dir=args.output_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
