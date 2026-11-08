"""Read returned P2 workbooks as preparation records, never as frozen gold.

The trusted packet and its original blank workbooks remain unchanged. Human
inputs are archived privately, validated against packet identities and source
paragraphs, and compared without filling labels or adjudication decisions.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import date, datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
from typing import Any, Mapping
import zipfile


_PRIVATE_ROOT = Path(__file__).resolve().parents[2] / "var"
_MAX_FILE = 8 * 1024 * 1024
_MAX_EXPANDED = 32 * 1024 * 1024
_MAX_MEMBERS = 100
_MAX_ROWS = 1000
_MAX_COLUMNS = 32
_LABELS = ("MET", "UNMET", "CANNOT_ASSESS")
_RELATIONS = {"MET": "SUPPORTED", "UNMET": "CONTRADICTED", "CANNOT_ASSESS": "INSUFFICIENT"}
_MANUAL = ("label", "evidence_basis", "evidence_paragraph_ids", "exact_evidence_quote",
           "whole_text_reviewed", "rationale", "rule_notes")
_IDENTITY = ("report_id", "report_version", "body_sha256", "rubric_id", "rubric_version", "checklist_id")
_REFERENCE_FIELDS = ("item_id", "case_id", "report_id", "report_version", "body_sha256", "rubric_id",
                     "rubric_version", "source_rubric_sha256", "checklist_id", "source_stage", "source_json")
_RECIPIENTS = {"QUY": "Quý", "YEN": "Yến", "Quý": "Quý", "Yến": "Yến"}


class IntakeError(ValueError):
    """Content-free integrity or workbook-structure error."""


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                       allow_nan=False) + "\n").encode("utf-8")


def _regular(path: Path, *, limit: int = _MAX_FILE) -> bytes:
    path = Path(os.path.abspath(path))
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise IntakeError("SYMLINK_INPUT_REJECTED")
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(descriptor, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
                raise IntakeError("INPUT_SIZE_OR_TYPE_REJECTED")
            data = stream.read(limit + 1)
    except OSError:
        raise IntakeError("INPUT_UNAVAILABLE") from None
    if len(data) > limit:
        raise IntakeError("INPUT_SIZE_OR_TYPE_REJECTED")
    return data


def _json(path: Path) -> Any:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise IntakeError("DUPLICATE_JSON_KEY")
            result[key] = value
        return result
    try:
        return json.loads(_regular(path).decode("utf-8-sig"), object_pairs_hook=unique)
    except (UnicodeError, json.JSONDecodeError):
        raise IntakeError("INVALID_PACKET_JSON") from None


def _relative(value: str) -> Path:
    if not isinstance(value, str) or not value or "\\" in value:
        raise IntakeError("INVALID_PACKET_PATH")
    relative = PurePosixPath(value)
    if relative.is_absolute() or any(part in ("..", ".") for part in relative.parts):
        raise IntakeError("INVALID_PACKET_PATH")
    return Path(*relative.parts)


def _table(path: Path) -> list[dict[str, str]]:
    try:
        reader = csv.DictReader(io.StringIO(_regular(path).decode("utf-8-sig"), newline=""))
        if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise IntakeError("INVALID_PACKET_CSV")
        rows = list(reader)
        if not rows or len(rows) > _MAX_ROWS or any(None in r or None in r.values() for r in rows):
            raise IntakeError("INVALID_PACKET_CSV")
        return rows
    except (UnicodeError, csv.Error):
        raise IntakeError("INVALID_PACKET_CSV") from None


def _packet_unchecked(packet_dir: Path, recipient: str) -> dict[str, Any]:
    if recipient not in _RECIPIENTS:
        raise IntakeError("UNKNOWN_RECIPIENT")
    name = _RECIPIENTS[recipient]
    role = "QUY" if name == "Quý" else "YEN"
    packet_dir = Path(os.path.abspath(packet_dir))
    bundle = packet_dir / f"SEFORA_PHIEU_{role}"
    manifest = _json(bundle / "bundle-manifest.json")
    if manifest.get("recipient") != name or manifest.get("labels_are_blank") is not True:
        raise IntakeError("PACKET_RECIPIENT_OR_STATUS_CHANGED")
    hashes = {}
    for entry in manifest.get("files", []):
        relative = _relative(entry["path"])
        key = relative.as_posix()
        if key in hashes:
            raise IntakeError("DUPLICATE_PACKET_FILE")
        data = _regular(bundle / relative)
        if _digest(data) != entry.get("sha256") or len(data) != entry.get("bytes"):
            raise IntakeError("PACKET_FILE_CHANGED")
        hashes[key] = entry["sha256"]
    definition = _json(bundle / "rubric-definition-manifest.json")
    files = definition.get("files", {})
    if not files or any(hashes.get(k) != v for k, v in files.items()):
        raise IntakeError("PACKET_DEFINITION_CHANGED")
    definition_sha = _digest(json.dumps(files, sort_keys=True, separators=(",", ":")).encode())
    if definition_sha != definition.get("rubric_definition_sha256") or definition_sha != manifest.get("rubric_definition_sha256"):
        raise IntakeError("PACKET_DEFINITION_CHANGED")
    mapping = _json(bundle / "checklists-draft.json")
    if hashes.get("rubric-goc.txt") != mapping.get("source_rubric_sha256"):
        raise IntakeError("PACKET_SOURCE_RUBRIC_CHANGED")
    statements = {row["checklist_id"]: row["statement_vi"] for row in mapping["checklists"]}
    baseline_name = f"PHIEU_GAN_NHAN_{role}.xlsx"
    if baseline_name not in hashes:
        raise IntakeError("MISSING_BLANK_WORKBOOK")
    rows = _table(packet_dir / f"labels_{role.lower()}_blank.csv")
    if len(rows) != manifest.get("rows"):
        raise IntakeError("PACKET_ROW_COUNT_CHANGED")
    indexed, contexts = {}, {}
    for row in rows:
        item = row.get("item_id")
        if not item or item in indexed or any(row.get(key) for key in _MANUAL):
            raise IntakeError("PACKET_BLANK_ROWS_CHANGED")
        if row.get("annotator_recipient") != name or row.get("rubric_version") != definition_sha:
            raise IntakeError("PACKET_IDENTITY_CHANGED")
        if (row.get("checklist_id") not in statements
                or row.get("statement_vi") != statements[row["checklist_id"]]
                or row.get("source_rubric_sha256") != hashes.get("rubric-goc.txt")):
            raise IntakeError("PACKET_CHECKLIST_MAPPING_CHANGED")
        context_path = f"BAI_VIET/{row['case_id']}/context.json"
        body_path = f"BAI_VIET/{row['case_id']}/body.txt"
        if context_path not in hashes or body_path not in hashes:
            raise IntakeError("PACKET_CONTEXT_NOT_HASHED")
        if row["case_id"] not in contexts:
            context = _json(bundle / _relative(context_path))
            body = _regular(bundle / _relative(body_path))
            if _digest(body) != context.get("body_sha256") or body.decode("utf-8") != context.get("report_text"):
                raise IntakeError("PACKET_BODY_CHANGED")
            contexts[row["case_id"]] = context
        context = contexts[row["case_id"]]
        for key in ("report_id", "report_version", "body_sha256", "rubric_id", "rubric_version", "source_rubric_sha256", "source_stage", "source_json"):
            if row.get(key) != context.get(key):
                raise IntakeError("PACKET_IDENTITY_CHANGED")
        indexed[item] = row
    return {"recipient": name, "role": role, "bundle": bundle, "rows": indexed, "contexts": contexts,
            "baseline": bundle / baseline_name, "definition_sha256": definition_sha,
            "manifest_sha256": _digest(_regular(bundle / "bundle-manifest.json"))}


def _packet(packet_dir: Path, recipient: str) -> dict[str, Any]:
    try:
        return _packet_unchecked(packet_dir, recipient)
    except IntakeError:
        raise
    except (KeyError, TypeError, ValueError, UnicodeError):
        raise IntakeError("INVALID_PACKET_STRUCTURE") from None


def _xlsx(data: bytes):
    """Bound the actual XML package before openpyxl reads any worksheets."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            members = archive.infolist()
            if len(members) > _MAX_MEMBERS or len({m.filename for m in members}) != len(members):
                raise IntakeError("WORKBOOK_PACKAGE_REJECTED")
            if sum(m.file_size for m in members) > _MAX_EXPANDED:
                raise IntakeError("WORKBOOK_EXPANSION_LIMIT")
            for member in members:
                _relative(member.filename)
                lower = member.filename.casefold()
                if any(part in lower for part in ("vbaproject", "externallinks/", "connections.xml", "embeddings/")):
                    raise IntakeError("ACTIVE_WORKBOOK_CONTENT_REJECTED")
                if member.file_size > _MAX_FILE:
                    raise IntakeError("WORKBOOK_MEMBER_LIMIT")
                if lower.endswith(".xml"):
                    raw = archive.read(member)
                    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
                        raise IntakeError("WORKBOOK_XML_REJECTED")
                    if lower.startswith("xl/worksheets/") and re.search(rb"<(?:[A-Za-z_][\w.-]*:)?f(?:\s|/?>)", raw):
                        raise IntakeError("WORKBOOK_FORMULA_REJECTED")
            if archive.testzip() is not None:
                raise IntakeError("WORKBOOK_CRC_REJECTED")
    except IntakeError:
        raise
    except Exception:
        raise IntakeError("INVALID_WORKBOOK_PACKAGE") from None
    try:
        from openpyxl import load_workbook
    except ImportError:
        raise IntakeError("Install optional dependency openpyxl to read annotation workbooks.") from None
    try:
        book = load_workbook(io.BytesIO(data), read_only=True, data_only=False, keep_links=False)
        for sheet in book:
            if not sheet.max_row or not sheet.max_column or sheet.max_row > _MAX_ROWS or sheet.max_column > _MAX_COLUMNS:
                raise IntakeError("WORKBOOK_DIMENSION_LIMIT")
            for cells in sheet.iter_rows():
                for cell in cells:
                    if cell.data_type == "f":
                        raise IntakeError("WORKBOOK_FORMULA_REJECTED")
                    if cell.value is not None and not isinstance(cell.value, str):
                        raise IntakeError("WORKBOOK_NON_TEXT_CELL_REJECTED")
        return book
    except IntakeError:
        raise
    except Exception:
        raise IntakeError("WORKBOOK_READ_FAILED") from None


def _values(sheet) -> list[list[str]]:
    return [[cell.value or "" for cell in cells] for cells in sheet.iter_rows()]


def _provenance(values: list[list[str]], baseline: list[list[str]]) -> tuple[dict, list, list]:
    if (len(values) != len(baseline) or any(len(row) != 2 for row in values)
            or any(a[0] != b[0] for a, b in zip(values, baseline))):
        raise IntakeError("WORKBOOK_PROVENANCE_STRUCTURE_CHANGED")
    if values[0] != baseline[0] or values[1] != baseline[1]:
        raise IntakeError("WORKBOOK_RECIPIENT_CHANGED")
    keys = ("actual_annotator", "annotation_mode", "peer_labels_seen_before_save", "p2_predictions_seen_before_save",
            "teacher_feedback_seen_before_annotation", "guideline_agreement", "completed_date", "ai_assistance_details", "other_exposure_notes")
    result = {key: values[i + 2][1].strip() for i, key in enumerate(keys)}
    issues, flags = [], []
    for key in keys[:7]:
        if not result[key]:
            issues.append({"code": "MISSING_PROVENANCE", "field": key})
    if result["annotation_mode"] and result["annotation_mode"] not in ("THU_CONG", "CO_AI_HO_TRO"):
        issues.append({"code": "INVALID_ANNOTATION_MODE"})
    if result["annotation_mode"] == "CO_AI_HO_TRO":
        flags.append("AI_ASSISTANCE_DECLARED")
        if not result["ai_assistance_details"]:
            issues.append({"code": "MISSING_AI_ASSISTANCE_DETAILS"})
    for key in keys[2:5]:
        if result[key] and result[key] not in ("CO", "KHONG", "CHUA_XAC_NHAN"):
            issues.append({"code": "INVALID_EXPOSURE_DECLARATION", "field": key})
        elif result[key] in ("CO", "CHUA_XAC_NHAN"):
            flags.append(key.upper() + "_REVIEW_REQUIRED")
    if result["guideline_agreement"] and result["guideline_agreement"] not in ("DA_THONG_NHAT", "CAN_SUA", "CHUA_THONG_NHAT"):
        issues.append({"code": "INVALID_GUIDELINE_DECLARATION"})
    elif result["guideline_agreement"] and result["guideline_agreement"] != "DA_THONG_NHAT":
        flags.append("GUIDELINE_NOT_AGREED")
    if result["completed_date"]:
        try:
            if date.fromisoformat(result["completed_date"]).isoformat() != result["completed_date"]:
                raise ValueError
        except ValueError:
            issues.append({"code": "INVALID_COMPLETION_DATE"})
    return result, issues, flags


def _paragraph_ids(value: str, context: Mapping[str, Any]) -> list[str]:
    ordered = [p["paragraph_id"] for p in context["paragraphs"]]
    indices = {identifier: index for index, identifier in enumerate(ordered)}
    found = []
    for token in value.split(";"):
        token = token.strip()
        if not token:
            raise IntakeError("MISSING_PARAGRAPH_IDS")
        match = re.fullmatch(r"(P[0-9]+)\s*-\s*(P[0-9]+)", token)
        if match:
            first, last = match.groups()
            if first not in indices or last not in indices or indices[first] > indices[last]:
                raise IntakeError("INVALID_PARAGRAPH_RANGE")
            found.extend(ordered[indices[first]:indices[last] + 1])
        elif token in indices:
            found.append(token)
        else:
            raise IntakeError("UNKNOWN_PARAGRAPH_ID")
    if len(set(found)) != len(found):
        raise IntakeError("DUPLICATE_PARAGRAPH_ID")
    return [identifier for identifier in ordered if identifier in found]


def _quote_spans(quote: str, declared: list[str], context: Mapping[str, Any]) -> list[dict]:
    paragraphs = [p for p in context["paragraphs"] if p["paragraph_id"] in declared]
    def matches(fragment):
        found = []
        for paragraph in paragraphs:
            start = 0
            while fragment:
                index = paragraph["text"].find(fragment, start)
                if index < 0:
                    break
                found.append({"start": paragraph["start"] + index, "end": paragraph["start"] + index + len(fragment),
                              "quote": fragment, "paragraph_id": paragraph["paragraph_id"]})
                start = index + 1
        return found
    whole = matches(quote)
    if len(whole) == 1:
        return whole
    if len(whole) > 1:
        raise IntakeError("QUOTE_AMBIGUOUS")
    if "|" not in quote:
        raise IntakeError("QUOTE_NOT_FOUND")
    parts = [part.strip() for part in quote.split("|")]
    if any(not part for part in parts):
        raise IntakeError("EMPTY_QUOTE_FRAGMENT")
    spans = []
    for part in parts:
        options = matches(part)
        if len(options) != 1:
            raise IntakeError("QUOTE_AMBIGUOUS" if options else "QUOTE_NOT_FOUND")
        spans.extend(options)
    if len({(s["start"], s["end"]) for s in spans}) != len(spans):
        raise IntakeError("DUPLICATE_QUOTE_SPAN")
    return spans


def _annotation(source: dict, values: list[str], context: Mapping[str, Any], sheet_row: int) -> dict:
    from research.gold_annotation.assessment_evidence import validate_evidence_record

    raw = dict(zip(_MANUAL, values))
    row = {"item_id": source["item_id"], "metadata": {key: source[key] for key in _IDENTITY},
           "case_id": source["case_id"], "sheet_row": sheet_row, "label": None,
           "verification_relation": None, "evidence": None, "source_fields": raw, "issues": []}
    label = raw["label"].strip()
    if not label:
        row.update(state="INCOMPLETE", issues=[{"code": "MISSING_LABEL"}])
        return row
    if label not in (*_LABELS, "UNSURE"):
        row.update(state="INVALID", issues=[{"code": "INVALID_LABEL"}])
        return row
    row["label"] = label
    row["verification_relation"] = _RELATIONS.get(label)
    rationale, basis = raw["rationale"].strip(), raw["evidence_basis"].strip()
    identity = {"schema_version": 1, **{key: source[key] for key in ("report_id", "report_version", "body_sha256")}}
    try:
        if not rationale:
            raise IntakeError("MISSING_RATIONALE")
        if raw["whole_text_reviewed"].strip() not in ("CO", "CHUA", "TRICH_XUAT_THIEU"):
            raise IntakeError("MISSING_OR_INVALID_WHOLE_TEXT_REVIEW")
        declared = _paragraph_ids(raw["evidence_paragraph_ids"], context) if raw["evidence_paragraph_ids"].strip() else []
        quote = raw["exact_evidence_quote"]
        if label in ("MET", "UNMET") and basis == "QUOTE":
            if not declared:
                raise IntakeError("MISSING_PARAGRAPH_IDS")
            if not quote:
                raise IntakeError("MISSING_QUOTE")
            evidence = {**identity, "kind": "SPAN_SET", "spans": _quote_spans(quote, declared, context)}
        elif label == "UNMET" and basis == "TOAN_VAN_VANG_MAT":
            if raw["whole_text_reviewed"].strip() != "CO":
                raise IntakeError("ABSENCE_REQUIRES_WHOLE_TEXT_REVIEW")
            if quote:
                raise IntakeError("ABSENCE_MUST_NOT_INVENT_QUOTE")
            if set(declared) != {p["paragraph_id"] for p in context["paragraphs"]}:
                raise IntakeError("ABSENCE_REQUIRES_COMPLETE_PARAGRAPH_COVERAGE")
            evidence = {**identity, "kind": "DOCUMENT_ABSENCE", "scope": "ENTIRE_CAPTURED_TEXT",
                        "reviewed_whole_text": True, "paragraph_ids": declared, "rationale": rationale}
        elif label == "CANNOT_ASSESS" and basis == "THIEU_DU_LIEU":
            evidence = {**identity, "kind": "INSUFFICIENT_INPUT", "rationale": rationale}
            if quote:
                if not declared:
                    raise IntakeError("MISSING_PARAGRAPH_IDS")
                row["diagnostic_spans"] = _quote_spans(quote, declared, context)
        elif label == "UNSURE" and basis == "CAN_LAM_RO":
            evidence = {**identity, "kind": "UNRESOLVED", "rationale": rationale}
            if quote:
                if not declared:
                    raise IntakeError("MISSING_PARAGRAPH_IDS")
                row["diagnostic_spans"] = _quote_spans(quote, declared, context)
        else:
            raise IntakeError("BASIS_LABEL_CONFLICT")
        row["evidence"] = validate_evidence_record(evidence, context)
        row["rationale"] = rationale
        row["state"] = "PENDING_REVIEW" if label == "UNSURE" else "VALID"
    except (ValueError, KeyError, TypeError) as exc:
        row["state"] = "INVALID"
        row["issues"] = [{"code": str(exc) if isinstance(exc, IntakeError) else "INVALID_EVIDENCE_RECORD"}]
        row["evidence"] = None
    return row


def parse_workbook(packet_dir: Path, workbook_path: Path, recipient: str) -> dict[str, Any]:
    """Validate a returned workbook against its original packet, preserving unresolved rows."""
    packet = _packet(Path(packet_dir), recipient)
    workbook_path = Path(workbook_path)
    if workbook_path.suffix.casefold() != ".xlsx":
        raise IntakeError("XLSX_REQUIRED")
    raw = _regular(workbook_path)
    returned, baseline = _xlsx(raw), _xlsx(_regular(packet["baseline"]))
    try:
        expected_sheets = {"BAT_DAU", "GAN_NHAN", "THONG_TIN", "DINH_DANH"}
        if set(returned.sheetnames) != expected_sheets or set(baseline.sheetnames) != expected_sheets:
            raise IntakeError("WORKBOOK_SHEETS_CHANGED")
        if _values(returned["BAT_DAU"]) != _values(baseline["BAT_DAU"]):
            raise IntakeError("WORKBOOK_GUIDE_CHANGED")
        provenance, issues, flags = _provenance(_values(returned["THONG_TIN"]), _values(baseline["THONG_TIN"]))
        reference = _values(returned["DINH_DANH"])
        if reference[0] != list(_REFERENCE_FIELDS) or len(reference) != len(packet["rows"]) + 1:
            raise IntakeError("WORKBOOK_IDENTITY_SHEET_CHANGED")
        seen = set()
        for values in reference[1:]:
            row = dict(zip(_REFERENCE_FIELDS, values))
            item = row["item_id"]
            if item not in packet["rows"] or item in seen or any(row[key] != packet["rows"][item][key] for key in _REFERENCE_FIELDS):
                raise IntakeError("WORKBOOK_IDENTITY_CHANGED")
            seen.add(item)
        values = _values(returned["GAN_NHAN"])
        if values[0] != _values(baseline["GAN_NHAN"])[0] or len(values) != len(packet["rows"]) + 1:
            raise IntakeError("WORKBOOK_ANNOTATION_STRUCTURE_CHANGED")
        rows, seen = [], set()
        for number, cells in enumerate(values[1:], 2):
            if len(cells) != 11:
                raise IntakeError("WORKBOOK_ANNOTATION_STRUCTURE_CHANGED")
            item = cells[10]
            if item not in packet["rows"] or item in seen:
                raise IntakeError("WORKBOOK_ITEM_IDS_CHANGED")
            source = packet["rows"][item]
            if cells[:3] != [source["case_id"], source["checklist_id"], source["statement_vi"]]:
                raise IntakeError("WORKBOOK_ITEM_METADATA_CHANGED")
            seen.add(item)
            rows.append(_annotation(source, cells[3:10], packet["contexts"][source["case_id"]], number))
        if set(packet["rows"]) != seen or _regular(workbook_path) != raw:
            raise IntakeError("WORKBOOK_CHANGED_DURING_READ")
        state = "INCOMPLETE" if issues or any(r["state"] in ("INCOMPLETE", "INVALID") for r in rows) else (
            "NEEDS_REVIEW" if flags or any(r["state"] == "PENDING_REVIEW" for r in rows) else "READY_FOR_REVIEW")
        return {"schema_version": 1, "classification": "RETURNED_ANNOTATION_PREPARATION_NOT_GOLD",
                "recipient": packet["recipient"], "status": state, "rows": rows,
                "provenance": provenance, "provenance_issues": issues, "provenance_review_flags": flags,
                "input_sha256": _digest(raw), "packet_manifest_sha256": packet["manifest_sha256"],
                "rubric_definition_sha256": packet["definition_sha256"], "gold_frozen": False,
                "independence_certified": False,
                "counts": {"rows": len(rows), "states": dict(Counter(r["state"] for r in rows)),
                           "labels": dict(Counter(r["label"] or "BLANK" for r in rows))}}
    finally:
        returned.close()
        baseline.close()


def _evidence_signature(evidence: Mapping[str, Any] | None):
    if not evidence:
        return None
    if evidence["kind"] == "SPAN_SET":
        return (evidence["kind"], tuple(sorted((s["start"], s["end"], s["quote"]) for s in evidence["spans"])))
    if evidence["kind"] == "DOCUMENT_ABSENCE":
        return (evidence["kind"], evidence["body_sha256"], evidence["scope"], tuple(evidence["paragraph_ids"]))
    return (evidence["kind"],)


def prepare_single_intake(packet_dir: Path, workbook_path: Path, recipient: str,
                          output_dir: Path) -> dict[str, Any]:
    """Archive one actual returned sheet without implying independent consensus or gold."""
    output = Path(os.path.abspath(output_dir))
    root = Path(os.path.abspath(_PRIVATE_ROOT))
    if output == root or not output.is_relative_to(root) or any(p.is_symlink() for p in (output, *output.parents)):
        raise IntakeError("OUTPUT_MUST_BE_PRIVATE_VAR")
    if output.exists():
        raise IntakeError("OUTPUT_ALREADY_EXISTS")
    packet = _packet(Path(packet_dir), recipient)
    role = packet["role"].lower()
    source = Path(workbook_path)
    if source.suffix.casefold() != ".xlsx":
        raise IntakeError("XLSX_REQUIRED")
    snapshot = _regular(source)
    output.mkdir(parents=True, mode=0o700)
    originals = output / "originals"
    originals.mkdir(mode=0o700)
    target = originals / f"{role}_return.xlsx"
    with target.open("xb") as stream:
        stream.write(snapshot)
    target.chmod(0o400)
    receipt = {"recipient": packet["recipient"], "source_path": str(source),
               "archived_path": str(target.relative_to(output)), "bytes": len(snapshot),
               "sha256": _digest(snapshot)}
    # Keep the receipt even when subsequent workbook validation rejects the input.
    receipt_path = output / "source-receipts.json"
    receipt_path.write_bytes(_canonical([receipt]))
    receipt_path.chmod(0o600)
    parsed = parse_workbook(Path(packet_dir), target, recipient)
    review = [row for row in parsed["rows"] if row["state"] != "VALID"]
    summary = {
        "schema_version": 1, "status": parsed["status"],
        "classification": "SINGLE_HUMAN_SHEET_INTAKE_NOT_MODEL_EVALUATION",
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "annotation_design": "SINGLE_ANNOTATOR", "annotator_count": 1,
        "recipient": parsed["recipient"],
        "annotation_mode": parsed["provenance"]["annotation_mode"],
        "ai_assistance_declared": "AI_ASSISTANCE_DECLARED" in parsed["provenance_review_flags"],
        "counts": parsed["counts"], "review_items": len(review),
        "provenance_issues": parsed["provenance_issues"],
        "provenance_review_flags": parsed["provenance_review_flags"],
        "agreement_rate": None, "cohen_kappa": None,
        "agreement_not_applicable_reason": "SINGLE_ANNOTATOR",
        "second_annotator_required_by_this_intake": False,
        "gold_frozen": False, "independence_certified": False,
        "model_predictions_read": False, "labels_generated": False,
    }
    for name, value in ((f"canonical_{role}.json", parsed), ("summary.json", summary),
                        ("review_items.json", review)):
        path = output / name
        path.write_bytes(_canonical(value))
        path.chmod(0o600)
    return summary


def prepare_intake(packet_dir: Path, quy_workbook: Path, yen_workbook: Path, output_dir: Path) -> dict[str, Any]:
    """Archive and compare actual returned sheets; no predictions or final labels are created."""
    output = Path(os.path.abspath(output_dir))
    root = Path(os.path.abspath(_PRIVATE_ROOT))
    if output == root or not output.is_relative_to(root) or any(p.is_symlink() for p in (output, *output.parents)):
        raise IntakeError("OUTPUT_MUST_BE_PRIVATE_VAR")
    if output.exists():
        raise IntakeError("OUTPUT_ALREADY_EXISTS")
    for role in ("QUY", "YEN"):
        _packet(Path(packet_dir), role)
    sources = {"quy": Path(quy_workbook), "yen": Path(yen_workbook)}
    snapshots = {role: _regular(path) for role, path in sources.items()}
    output.mkdir(parents=True, mode=0o700)
    originals = output / "originals"
    originals.mkdir(mode=0o700)
    receipts, parsed = [], {}
    for role in ("quy", "yen"):
        target = originals / f"{role}_return.xlsx"
        with target.open("xb") as stream:
            stream.write(snapshots[role])
        target.chmod(0o400)
        receipts.append({"recipient": role, "source_path": str(sources[role]),
                         "archived_path": str(target.relative_to(output)), "bytes": len(snapshots[role]),
                         "sha256": _digest(snapshots[role])})
        parsed[role] = parse_workbook(Path(packet_dir), target, role.upper())
        (output / f"canonical_{role}.json").write_bytes(_canonical(parsed[role]))
    first = {r["item_id"]: r for r in parsed["quy"]["rows"]}
    second = {r["item_id"]: r for r in parsed["yen"]["rows"]}
    if set(first) != set(second):
        raise IntakeError("ANNOTATOR_ITEM_SETS_DIFFER")
    review, comparable = [], []
    for item, a in first.items():
        b = second[item]
        reasons = []
        if a["metadata"] != b["metadata"]:
            raise IntakeError("ANNOTATOR_IDENTITIES_DIFFER")
        for role, row in (("QUY", a), ("YEN", b)):
            if row["state"] != "VALID":
                reasons.append(role + "_" + row["state"])
        if a["state"] == b["state"] == "VALID":
            comparable.append((a["label"], b["label"]))
            if a["label"] != b["label"]:
                reasons.append("LABEL_DISAGREEMENT")
            elif _evidence_signature(a["evidence"]) != _evidence_signature(b["evidence"]):
                reasons.append("EVIDENCE_DIFFERENCE")
            elif a["label"] == "CANNOT_ASSESS" and a["rationale"] != b["rationale"]:
                reasons.append("INSUFFICIENCY_REASON_REVIEW")
        if reasons:
            review.append({"item_id": item, "metadata": a["metadata"], "review_reasons": reasons,
                           "quy_label": a["label"], "yen_label": b["label"],
                           "quy_evidence": a["evidence"], "yen_evidence": b["evidence"],
                           "quy_rationale": a.get("rationale", a["source_fields"]["rationale"]),
                           "yen_rationale": b.get("rationale", b["source_fields"]["rationale"]),
                           "quy_source_fields": a["source_fields"], "yen_source_fields": b["source_fields"],
                           "quy_issues": a["issues"], "yen_issues": b["issues"],
                           "final_label": "", "final_evidence": None, "decision_by": "",
                           "decided_at": "", "decision_rationale": ""})
    global_flags = {role: record["provenance_review_flags"] for role, record in parsed.items()}
    names = [parsed[role]["provenance"]["actual_annotator"].casefold() for role in ("quy", "yen")]
    if names[0] and names[0] == names[1]:
        global_flags["pair"] = ["SAME_DECLARED_ANNOTATOR"]
    status = "INCOMPLETE" if any(r["status"] == "INCOMPLETE" for r in parsed.values()) else (
        "NEEDS_ADJUDICATION" if review or any(global_flags.values()) else "READY_FOR_REVIEW")
    count = len(comparable)
    matching = sum(a == b for a, b in comparable)
    counts_a, counts_b = Counter(a for a, _ in comparable), Counter(b for _, b in comparable)
    expected = sum(counts_a[label] * counts_b[label] for label in _LABELS) / count**2 if count else None
    summary = {"schema_version": 1, "status": status, "classification": "HUMAN_SHEET_INTAKE_NOT_MODEL_EVALUATION",
               "recorded_at_utc": datetime.now(timezone.utc).isoformat(), "items": len(first),
               "per_person": {role: {"status": r["status"], **r["counts"], "provenance_issues": r["provenance_issues"]}
                              for role, r in parsed.items()},
               "comparable_resolved_items": count, "matching_labels": matching,
               "agreement_rate": matching / count if count else None,
               "cohen_kappa": (matching / count - expected) / (1 - expected) if count and expected != 1 else None,
               "unresolved_or_missing_items": len(first) - count, "review_items": len(review),
               "provenance_review_flags": global_flags, "gold_frozen": False,
               "independence_certified": False, "model_predictions_read": False, "labels_generated": False}
    for name, value in (("summary.json", summary), ("source-receipts.json", receipts), ("review_items.json", review)):
        (output / name).write_bytes(_canonical(value))
    fields = ["item_id", "review_reasons", "quy_label", "yen_label", "quy_issues", "yen_issues", "quy_rationale", "yen_rationale",
              "final_label", "final_evidence_kind", "final_paragraph_ids", "final_quote", "final_whole_text_reviewed",
              "decision_by", "decided_at", "decision_rationale"]
    with (output / "review_items.csv").open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in review:
            values = {key: row.get(key, "") for key in fields}
            values["review_reasons"] = ";".join(row["review_reasons"])
            for role in ("quy", "yen"):
                values[role + "_issues"] = ";".join(issue["code"] for issue in row[role + "_issues"])
            # This is a human review export, never executable spreadsheet input.
            writer.writerow({key: "'" + str(value) if str(value).startswith(("=", "+", "-", "@", "\t", "\r")) else value
                             for key, value in values.items()})
    for path in output.rglob("*"):
        if path.is_file() and path.parent != originals:
            path.chmod(0o600)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet-dir", type=Path, required=True)
    parser.add_argument("--quy-workbook", type=Path)
    parser.add_argument("--yen-workbook", type=Path)
    parser.add_argument("--single-workbook", type=Path)
    parser.add_argument("--recipient", choices=("QUY", "YEN"))
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.single_workbook is not None:
        if args.recipient is None or args.quy_workbook is not None or args.yen_workbook is not None:
            parser.error("--single-workbook requires --recipient and cannot be combined with paired workbooks")
    elif args.recipient is not None or args.quy_workbook is None or args.yen_workbook is None:
        parser.error("Provide both paired workbooks, or --single-workbook with --recipient")
    try:
        if args.single_workbook is not None:
            result = prepare_single_intake(args.packet_dir, args.single_workbook, args.recipient, args.output_dir)
        else:
            result = prepare_intake(args.packet_dir, args.quy_workbook, args.yen_workbook, args.output_dir)
    except IntakeError as exc:
        parser.exit(2, f"P2 intake rejected: {exc}\n")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "READY_FOR_REVIEW" else 1


if __name__ == "__main__":
    raise SystemExit(main())
