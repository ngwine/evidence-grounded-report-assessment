"""Synthetic returned-sheet fixtures; never generate labels for the real pilot."""
import csv
import hashlib
import json
import zipfile

import pytest

openpyxl = pytest.importorskip("openpyxl", reason="Optional workbook intake requires openpyxl")

from research.gold_annotation import p2_workbook_intake as intake  # noqa: E402


FIELDS = ["item_id", "case_id", "report_id", "report_version", "body_sha256", "rubric_id", "rubric_version",
          "source_rubric_sha256", "checklist_id", "source_stage", "source_json"]
HEADERS = ["Mã bài", "Checklist", "Nội dung cần kiểm", "Nhãn", "Căn cứ", "Đoạn P đã dẫn/đã kiểm",
           "Quote nguyên văn", "Đã đọc toàn bài?", "Lý do / thiếu gì", "Ghi chú quy tắc / lỗi nguồn", "item_id"]
MANUAL = ["label", "evidence_basis", "evidence_paragraph_ids", "exact_evidence_quote", "whole_text_reviewed", "rationale", "rule_notes"]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def original_book(path, recipient, rows):
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.title = "BAT_DAU"
    sheet.append(["Field", "Instructions"])
    sheet.append(["Guideline", "Synthetic test guideline"])
    sheet = book.create_sheet("GAN_NHAN")
    sheet.append(HEADERS)
    for row in rows:
        sheet.append([row["case_id"], row["checklist_id"], row["statement_vi"], *[""] * 7, row["item_id"]])
    sheet = book.create_sheet("THONG_TIN")
    sheet.append(["Field", "Answer"])
    sheet.append(["Recipient", recipient])
    for field in ("Actual annotator", "Mode", "Peer labels seen", "P2 seen", "Teacher feedback seen",
                  "Guideline agreement", "Completion date", "AI details", "Other notes"):
        sheet.append([field, ""])
    sheet = book.create_sheet("DINH_DANH")
    sheet.append(FIELDS)
    for row in rows:
        sheet.append([row[field] for field in FIELDS])
    book.save(path)


@pytest.fixture
def packet(tmp_path, monkeypatch):
    monkeypatch.setattr(intake, "_PRIVATE_ROOT", tmp_path)
    root = tmp_path / "packet"
    root.mkdir()
    texts = ["Repeated sentence. Repeated sentence. A unique event happened.",
             "Repeated sentence. I baked bread after a failed recipe.", "The next loaf baked evenly."]
    body = "\n\n".join(texts)
    body_hash = hashlib.sha256(body.encode()).hexdigest()
    paragraphs, offset = [], 0
    for index, text in enumerate(texts, 1):
        paragraphs.append({"paragraph_id": f"P{index:04d}", "start": offset, "end": offset + len(text), "text": text})
        offset += len(text) + 2
    contexts = []
    for role, recipient in (("QUY", "Quý"), ("YEN", "Yến")):
        bundle = root / f"SEFORA_PHIEU_{role}"
        bundle.mkdir()
        (bundle / "rubric-goc.txt").write_text("Synthetic source rubric", encoding="utf-8")
        source_hash = sha(bundle / "rubric-goc.txt")
        mapping = {"source_rubric_sha256": source_hash, "checklists": [
            {"checklist_id": key, "statement_vi": statement}
            for key, statement in (("CLM001", "Explicit claim"), ("EXP001", "Personal example"), ("QUO001", "Two quotations"))]}
        save(bundle / "checklists-draft.json", mapping)
        for name in ("CHECKLIST_3_MUC.md", "HUONG_DAN_GAN_NHAN.md"):
            (bundle / name).write_text("Synthetic instructions", encoding="utf-8")
        definitions = {name: sha(bundle / name) for name in
                       ("checklists-draft.json", "CHECKLIST_3_MUC.md", "HUONG_DAN_GAN_NHAN.md")}
        definition = hashlib.sha256(json.dumps(definitions, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        save(bundle / "rubric-definition-manifest.json", {"rubric_definition_sha256": definition, "files": definitions})
        context = {"case_id": "C2-01-IDX", "report_id": "report-x", "report_version": "a" * 64,
                   "body_sha256": body_hash, "rubric_id": "rubric-x", "rubric_version": definition,
                   "source_rubric_sha256": source_hash, "source_stage": "Revision", "source_json": "source/test.json",
                   "report_text": body, "paragraphs": paragraphs}
        folder = bundle / "BAI_VIET/C2-01-IDX"
        folder.mkdir(parents=True)
        (folder / "body.txt").write_text(body, encoding="utf-8")
        save(folder / "context.json", context)
        rows = [{**{key: value for key, value in context.items() if key not in ("report_text", "paragraphs")},
                 "item_id": "C2-01-IDX-" + item["checklist_id"], "checklist_id": item["checklist_id"],
                 "statement_vi": item["statement_vi"], **{field: "" for field in MANUAL}, "annotator_recipient": recipient}
                for item in mapping["checklists"]]
        original_book(bundle / f"PHIEU_GAN_NHAN_{role}.xlsx", recipient, rows)
        manifest = {"recipient": recipient, "rows": 3, "labels_are_blank": True,
                    "rubric_definition_sha256": definition,
                    "files": [{"path": p.relative_to(bundle).as_posix(), "bytes": p.stat().st_size, "sha256": sha(p)}
                              for p in sorted(bundle.rglob("*")) if p.is_file()]}
        save(bundle / "bundle-manifest.json", manifest)
        with (root / f"labels_{role.lower()}_blank.csv").open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        contexts.append(context)
    return root, contexts[0]


def returned(packet, tmp_path, role="QUY", *, fill=True):
    root, _ = packet
    path = tmp_path / f"returned-{role}.xlsx"
    book = openpyxl.load_workbook(root / f"SEFORA_PHIEU_{role}/PHIEU_GAN_NHAN_{role}.xlsx")
    if fill:
        sheet = book["GAN_NHAN"]
        values = ["MET", "QUOTE", "P0002", "I baked bread after a failed recipe.", "CO", "A concrete event is described.", ""]
        for row in range(2, 5):
            for column, value in enumerate(values, 4):
                sheet.cell(row, column, value)
        info = book["THONG_TIN"]
        for row, value in {3: "Reviewer " + role, 4: "THU_CONG", 5: "KHONG", 6: "KHONG", 7: "KHONG",
                           8: "DA_THONG_NHAT", 9: "2026-11-05"}.items():
            info.cell(row, 2, value)
    book.save(path)
    return path


def edit(path, sheet, cell, value):
    book = openpyxl.load_workbook(path)
    book[sheet][cell] = value
    book.save(path)


def test_blank_packet_stays_incomplete_and_never_creates_labels(packet, tmp_path):
    path = returned(packet, tmp_path, fill=False)
    result = intake.parse_workbook(packet[0], path, "QUY")
    assert result["status"] == "INCOMPLETE"
    assert result["counts"]["labels"] == {"BLANK": 3}
    assert all(row["label"] is None and row["evidence"] is None for row in result["rows"])
    assert result["gold_frozen"] is False
    assert result["independence_certified"] is False
    assert result["provenance"]["actual_annotator"] == ""


def test_exact_spans_and_versions_are_derived_from_trusted_source(packet, tmp_path):
    result = intake.parse_workbook(packet[0], returned(packet, tmp_path), "Quý")
    assert result["status"] == "READY_FOR_REVIEW"
    evidence = result["rows"][0]["evidence"]
    assert evidence["kind"] == "SPAN_SET"
    span = evidence["spans"][0]
    assert packet[1]["report_text"][span["start"]:span["end"]] == span["quote"]
    assert span["paragraph_id"] == "P0002" and span["span_id"]
    assert evidence["body_sha256"] == packet[1]["body_sha256"]


def test_paragraph_id_disambiguates_quote_repeated_elsewhere(packet, tmp_path):
    path = returned(packet, tmp_path)
    edit(path, "GAN_NHAN", "G2", "Repeated sentence.")
    result = intake.parse_workbook(packet[0], path, "QUY")
    assert result["rows"][0]["state"] == "VALID"
    assert result["rows"][0]["evidence"]["spans"][0]["paragraph_id"] == "P0002"


@pytest.mark.parametrize("paragraphs,quote,code", [
    ("P0001", "Repeated sentence.", "QUOTE_AMBIGUOUS"),
    ("P0002", "A paraphrase about bread", "QUOTE_NOT_FOUND"),
    ("P9999", "I baked bread after a failed recipe.", "UNKNOWN_PARAGRAPH_ID"),
    ("P0002;P0002", "I baked bread after a failed recipe.", "DUPLICATE_PARAGRAPH_ID"),
    ("P0003-P0001", "The next loaf baked evenly.", "INVALID_PARAGRAPH_RANGE"),
])
def test_invalid_quote_and_scope_are_not_repaired(packet, tmp_path, paragraphs, quote, code):
    path = returned(packet, tmp_path)
    edit(path, "GAN_NHAN", "F2", paragraphs)
    edit(path, "GAN_NHAN", "G2", quote)
    result = intake.parse_workbook(packet[0], path, "QUY")
    row = result["rows"][0]
    assert row["state"] == "INVALID" and row["evidence"] is None
    assert row["issues"] == [{"code": code}]
    assert row["source_fields"]["exact_evidence_quote"] == quote


def test_compound_quotes_keep_exact_ranges(packet, tmp_path):
    path = returned(packet, tmp_path)
    edit(path, "GAN_NHAN", "F2", "P0002;P0003")
    edit(path, "GAN_NHAN", "G2", "I baked bread after a failed recipe. | The next loaf baked evenly.")
    result = intake.parse_workbook(packet[0], path, "QUY")
    assert result["rows"][0]["state"] == "VALID"
    assert len(result["rows"][0]["evidence"]["spans"]) == 2


def test_literal_pipe_inside_one_source_quote_is_not_split():
    context = {"paragraphs": [{"paragraph_id": "P0001", "start": 0,
                                "end": 10, "text": "left | end"}]}
    spans = intake._quote_spans("left | end", ["P0001"], context)
    assert spans == [{"start": 0, "end": 10, "quote": "left | end", "paragraph_id": "P0001"}]


def test_absence_has_whole_document_provenance_and_no_fake_span(packet, tmp_path):
    path = returned(packet, tmp_path)
    for cell, value in {"D2": "UNMET", "E2": "TOAN_VAN_VANG_MAT", "F2": "P0001-P0003",
                        "G2": "", "I2": "Read all captured paragraphs; the required component is absent."}.items():
        edit(path, "GAN_NHAN", cell, value)
    result = intake.parse_workbook(packet[0], path, "QUY")
    evidence = result["rows"][0]["evidence"]
    assert evidence["kind"] == "DOCUMENT_ABSENCE"
    assert evidence["reviewed_whole_text"] is True
    assert evidence["paragraph_ids"] == ["P0001", "P0002", "P0003"]
    assert "spans" not in evidence


@pytest.mark.parametrize("cell,value,code", [
    ("H2", "CHUA", "ABSENCE_REQUIRES_WHOLE_TEXT_REVIEW"),
    ("F2", "P0001;P0003", "ABSENCE_REQUIRES_COMPLETE_PARAGRAPH_COVERAGE"),
    ("G2", "The essay does not have it.", "ABSENCE_MUST_NOT_INVENT_QUOTE"),
    ("D2", "MET", "BASIS_LABEL_CONFLICT"),
])
def test_absence_is_not_inferred_from_missing_retrieval(packet, tmp_path, cell, value, code):
    path = returned(packet, tmp_path)
    for name, text in {"D2": "UNMET", "E2": "TOAN_VAN_VANG_MAT", "F2": "P0001-P0003", "G2": ""}.items():
        edit(path, "GAN_NHAN", name, text)
    edit(path, "GAN_NHAN", cell, value)
    row = intake.parse_workbook(packet[0], path, "QUY")["rows"][0]
    assert row["state"] == "INVALID" and row["issues"] == [{"code": code}]


@pytest.mark.parametrize("label,basis,kind,state", [
    ("CANNOT_ASSESS", "THIEU_DU_LIEU", "INSUFFICIENT_INPUT", "VALID"),
    ("UNSURE", "CAN_LAM_RO", "UNRESOLVED", "PENDING_REVIEW"),
])
def test_insufficient_and_human_unsure_remain_distinct(packet, tmp_path, label, basis, kind, state):
    path = returned(packet, tmp_path)
    for cell, value in {"D2": label, "E2": basis, "F2": "", "G2": "", "I2": "The basis needs review."}.items():
        edit(path, "GAN_NHAN", cell, value)
    row = intake.parse_workbook(packet[0], path, "QUY")["rows"][0]
    assert row["state"] == state and row["evidence"]["kind"] == kind
    assert row["verification_relation"] == ("INSUFFICIENT" if label == "CANNOT_ASSESS" else None)


@pytest.mark.parametrize("sheet,cell,value,code", [
    ("GAN_NHAN", "A2", "another-case", "WORKBOOK_ITEM_METADATA_CHANGED"),
    ("GAN_NHAN", "K2", "fake-item", "WORKBOOK_ITEM_IDS_CHANGED"),
    ("DINH_DANH", "D2", "wrong-version", "WORKBOOK_IDENTITY_CHANGED"),
    ("DINH_DANH", "E2", "b" * 64, "WORKBOOK_IDENTITY_CHANGED"),
    ("BAT_DAU", "B2", "Changed rule", "WORKBOOK_GUIDE_CHANGED"),
    ("THONG_TIN", "B2", "Yến", "WORKBOOK_RECIPIENT_CHANGED"),
    ("GAN_NHAN", "I2", "=1+1", "WORKBOOK_FORMULA_REJECTED"),
])
def test_tampered_metadata_and_formulas_rejected(packet, tmp_path, sheet, cell, value, code):
    path = returned(packet, tmp_path)
    edit(path, sheet, cell, value)
    with pytest.raises(intake.IntakeError, match=code):
        intake.parse_workbook(packet[0], path, "QUY")


def test_packet_definition_and_body_hashes_checked(packet, tmp_path):
    path = returned(packet, tmp_path)
    source = packet[0] / "SEFORA_PHIEU_QUY/BAI_VIET/C2-01-IDX/body.txt"
    source.write_text("changed")
    with pytest.raises(intake.IntakeError, match="PACKET_FILE_CHANGED"):
        intake.parse_workbook(packet[0], path, "QUY")


def test_exposure_and_ai_assistance_are_recorded_not_falsely_certified(packet, tmp_path):
    path = returned(packet, tmp_path)
    edit(path, "THONG_TIN", "B4", "CO_AI_HO_TRO")
    edit(path, "THONG_TIN", "B5", "CO")
    edit(path, "THONG_TIN", "B10", "Used an assistant to help read the text.")
    result = intake.parse_workbook(packet[0], path, "QUY")
    assert result["status"] == "NEEDS_REVIEW"
    assert "AI_ASSISTANCE_DECLARED" in result["provenance_review_flags"]
    assert result["provenance"]["peer_labels_seen_before_save"] == "CO"
    assert result["independence_certified"] is False


def test_row_sorting_preserves_identity_by_item_id(packet, tmp_path):
    path = returned(packet, tmp_path)
    book = openpyxl.load_workbook(path)
    sheet = book["GAN_NHAN"]
    before = [[sheet.cell(i, j).value for j in range(1, 12)] for i in (2, 4)]
    for i, values in zip((4, 2), before):
        for j, value in enumerate(values, 1):
            sheet.cell(i, j, value)
    book.save(path)
    result = intake.parse_workbook(packet[0], path, "QUY")
    assert result["status"] == "READY_FOR_REVIEW"
    assert result["rows"][0]["item_id"].endswith("QUO001")


def test_pair_archive_and_unresolved_disputes_never_fill_final_label(packet, tmp_path):
    a, b = returned(packet, tmp_path, "QUY"), returned(packet, tmp_path, "YEN")
    edit(b, "GAN_NHAN", "D2", "UNMET")
    before = (a.read_bytes(), b.read_bytes())
    output = tmp_path / "intake"
    summary = intake.prepare_intake(packet[0], a, b, output)
    assert summary["status"] == "NEEDS_ADJUDICATION"
    assert summary["comparable_resolved_items"] == 3 and summary["matching_labels"] == 2
    assert summary["gold_frozen"] is False and summary["model_predictions_read"] is False
    reviews = json.loads((output / "review_items.json").read_text())
    assert len(reviews) == 1 and reviews[0]["final_label"] == "" and reviews[0]["decision_by"] == ""
    assert (output / "originals/quy_return.xlsx").read_bytes() == before[0]
    assert (output / "originals/yen_return.xlsx").read_bytes() == before[1]
    assert a.read_bytes() == before[0] and b.read_bytes() == before[1]
    assert (output / "originals/quy_return.xlsx").stat().st_mode & 0o222 == 0
    with pytest.raises(intake.IntakeError, match="OUTPUT_ALREADY_EXISTS"):
        intake.prepare_intake(packet[0], a, b, output)


def test_same_labels_with_different_quotes_still_need_evidence_review(packet, tmp_path):
    a, b = returned(packet, tmp_path, "QUY"), returned(packet, tmp_path, "YEN")
    edit(b, "GAN_NHAN", "G2", "Repeated sentence.")
    output = tmp_path / "intake"
    summary = intake.prepare_intake(packet[0], a, b, output)
    reviews = json.loads((output / "review_items.json").read_text())
    assert summary["matching_labels"] == 3
    assert reviews[0]["review_reasons"] == ["EVIDENCE_DIFFERENCE"]


def test_bounded_packages_reject_xml_entities_and_excess_dimensions(packet, tmp_path):
    path = returned(packet, tmp_path)
    with zipfile.ZipFile(path) as source:
        files = {info.filename: source.read(info.filename) for info in source.infolist()}
    files["xl/workbook.xml"] = b'<!DOCTYPE x [<!ENTITY a "test">]>' + files["xl/workbook.xml"]
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as target:
        for name, data in files.items():
            target.writestr(name, data)
    with pytest.raises(intake.IntakeError, match="WORKBOOK_XML_REJECTED"):
        intake.parse_workbook(packet[0], path, "QUY")


def test_excess_workbook_dimensions_are_rejected(packet, tmp_path):
    path = returned(packet, tmp_path)
    edit(path, "GAN_NHAN", "A1001", "distant row")
    with pytest.raises(intake.IntakeError, match="WORKBOOK_DIMENSION_LIMIT"):
        intake.parse_workbook(packet[0], path, "QUY")


def test_all_same_label_agreement_does_not_fabricate_kappa(packet, tmp_path):
    a, b = returned(packet, tmp_path, "QUY"), returned(packet, tmp_path, "YEN")
    summary = intake.prepare_intake(packet[0], a, b, tmp_path / "intake")
    assert summary["status"] == "READY_FOR_REVIEW"
    assert summary["agreement_rate"] == 1
    assert summary["cohen_kappa"] is None
    assert summary["gold_frozen"] is False
