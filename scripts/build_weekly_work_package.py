"""Package weekly code/results for supervisor review; deliberately exclude paper.

prepare creates source/result snapshots and a Word report. Render the printed
HTML to PDF, inspect it, then finalize creates and verifies the ZIP. Original
experiment outputs and the manuscript are never edited by this builder.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
import csv
import hashlib
import html
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
from zipfile import ZIP_DEFLATED, ZipFile

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "var/submission/BAO_CAO_TUAN"
ARCHIVE = STAGE.with_suffix(".zip")
REPORT = ROOT / "docs/reports/BAO_CAO_TUAN.md"
PRINT_HTML = ROOT / "var/runtime/weekly-report/BAO_CAO_TUAN.html"
RECEIPTS = []


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(relative):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def write(relative, value):
    path = STAGE / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(value, str):
        path.write_text(value, encoding="utf-8")
    else:
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def copy(source, destination):
    source = ROOT / source
    if not source.is_file() or source.is_symlink():
        raise ValueError(f"Missing or symlink source: {source}")
    target = STAGE / destination
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    assert sha(source) == sha(target)
    RECEIPTS.append({"source": str(source.relative_to(ROOT)), "source_sha256": sha(source),
                     "output": str(target.relative_to(STAGE)), "transformation": "BYTE_IDENTICAL_COPY"})


def extract(source, destination, value, removed):
    write(destination, value)
    RECEIPTS.append({"source": source, "source_sha256": sha(ROOT / source), "output": destination,
                     "transformation": "FIELD_ALLOWLIST_SUMMARY", "omitted_fields": removed})


def blocks(text):
    lines = text.splitlines()
    result, index = [], 0
    while index < len(lines):
        line = lines[index].strip()
        if not line:
            index += 1
            continue
        if line.startswith("# "):
            result.append(("title", line[2:]))
        elif line.startswith("## "):
            result.append(("heading", line[3:]))
        elif line.startswith("|"):
            rows = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                cells = [c.strip() for c in lines[index].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-+:?", c.replace(" ", "")) for c in cells):
                    rows.append(cells)
                index += 1
            result.append(("table", rows))
            continue
        else:
            paragraph = [line]
            while index + 1 < len(lines) and lines[index + 1].strip() and not lines[index + 1].strip().startswith(("#", "|")):
                index += 1
                paragraph.append(lines[index].strip())
            result.append(("paragraph", " ".join(paragraph)))
        index += 1
    return result


def inline_html(text):
    value = html.escape(text)
    value = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", value)
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", value)


def word_text(paragraph, text):
    for part in re.split(r"(\*\*.*?\*\*|`[^`]+`)", text):
        bold = part.startswith("**") and part.endswith("**")
        code = part.startswith("`") and part.endswith("`")
        run = paragraph.add_run(part[2:-2] if bold else part[1:-1] if code else part)
        run.bold = bold
        if code:
            run.font.name = "Consolas"
            run.font.size = Pt(9)


def render_report():
    text = REPORT.read_text(encoding="utf-8")
    if (not text.startswith("# BÁO CÁO TUẦN\n")
            or re.search(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{4}\b|\b20\d{2}-\d{2}-\d{2}\b", text)
            or re.search(r"\b(?:2|hai) tuần\b", text, re.I)):
        raise ValueError("Weekly report title/body must not contain calendar dates or a two-week heading")
    parsed = blocks(text)
    document = Document()
    sec = document.sections[0]
    sec.page_width, sec.page_height = Cm(21), Cm(29.7)
    sec.top_margin, sec.bottom_margin = Cm(1.6), Cm(1.6)
    sec.left_margin, sec.right_margin = Cm(1.8), Cm(1.8)
    normal = document.styles["Normal"]
    normal.font.name, normal.font.size = "Arial", Pt(10)
    normal.paragraph_format.space_after = Pt(5)
    normal.paragraph_format.line_spacing = 1.12
    for name in ("Heading 1", "Heading 2"):
        style = document.styles[name]
        style.font.name, style.font.size = "Arial", Pt(12)
        style.font.color.rgb = RGBColor.from_string("17324D")
        style.paragraph_format.space_before = Pt(11)
        style.paragraph_format.space_after = Pt(5)
    markup = []
    for kind, data in parsed:
        if kind == "title":
            paragraph = document.add_paragraph()
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = paragraph.add_run(data)
            run.bold, run.font.size = True, Pt(17)
            markup.append("<h1>" + html.escape(data) + "</h1>")
        elif kind == "heading":
            document.add_paragraph(data, style="Heading 1")
            markup.append("<h2>" + html.escape(data) + "</h2>")
        elif kind == "paragraph":
            word_text(document.add_paragraph(), data)
            markup.append("<p>" + inline_html(data) + "</p>")
        else:
            table = document.add_table(rows=0, cols=len(data[0]))
            table.style = "Table Grid"
            table.autofit = False
            widths = ([5.0, 12.4] if len(data[0]) == 2 else [10.2, 3.4, 3.8])
            for row_index, cells in enumerate(data):
                row = table.add_row()
                properties = row._tr.get_or_add_trPr()
                properties.append(OxmlElement("w:cantSplit"))
                if row_index == 0:
                    properties.append(OxmlElement("w:tblHeader"))
                for column, value in enumerate(cells):
                    cell = row.cells[column]
                    cell.width = Cm(widths[column])
                    paragraph = cell.paragraphs[0]
                    paragraph.paragraph_format.space_after = Pt(3)
                    word_text(paragraph, value)
                    for run in paragraph.runs:
                        run.font.size = Pt(9)
                        if row_index == 0:
                            run.bold = True
                    if row_index == 0:
                        shading = OxmlElement("w:shd")
                        shading.set(qn("w:fill"), "EAF0F5")
                        cell._tc.get_or_add_tcPr().append(shading)
            markup.append("<table><thead><tr>" + "".join("<th>"+inline_html(v)+"</th>" for v in data[0])
                + "</tr></thead><tbody>" + "".join("<tr>"+"".join("<td>"+inline_html(v)+"</td>" for v in row)+"</tr>" for row in data[1:])
                + "</tbody></table>")
    footer = sec.footer.paragraphs[0]
    footer.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    footer.add_run("Trang ").font.size = Pt(9)
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), "PAGE")
    footer._p.append(field)
    document.core_properties.title = "BÁO CÁO TUẦN"
    document.core_properties.author = "Nguyễn Trần Ngọc Quý; Võ Thị Kim Yến"
    destination = STAGE / "01_BaoCaoTuan/BAO_CAO_TUAN.docx"
    destination.parent.mkdir(parents=True, exist_ok=True)
    document.save(destination)
    PRINT_HTML.parent.mkdir(parents=True, exist_ok=True)
    PRINT_HTML.write_text("""<!doctype html><html lang="vi"><meta charset="utf-8"><title>BÁO CÁO TUẦN</title>
<style>@page{size:A4;margin:16mm 18mm}*{box-sizing:border-box}body{font:10.5pt/1.38 Arial,sans-serif;color:#172c3f;margin:0}
h1{text-align:center;font-size:18pt;margin:0 0 16px}h2{font-size:12pt;color:#17324d;margin:16px 0 7px;break-after:avoid}
p{margin:6px 0 9px}table{border-collapse:collapse;width:100%;font-size:9.5pt;line-height:1.3;margin:8px 0 12px}
th,td{border:1px solid #b8c5d0;padding:6px 8px;text-align:left;vertical-align:top}th{background:#eaf0f5}
thead{display:table-header-group}tr{break-inside:avoid}code{font:9pt/1.3 Consolas,monospace;overflow-wrap:anywhere}p{orphans:3;widows:3}</style>
<body>""" + "\n".join(markup) + "</body></html>", encoding="utf-8")


def source_snapshot():
    listing = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=ROOT).decode().split("\0")
    roots = {"apps", "services", "research", "tests", "infra", "scripts", ".github"}
    doc_dirs = {"api", "architecture", "adr", "rubric", "pipelines", "threat-model", "week-01"}
    root_files = {"CONTRIBUTING.md", ".env.example", ".editorconfig", ".gitignore", ".pre-commit-config.yaml", "pytest.ini", "pyproject.toml", "Makefile"}
    extensions = {".py", ".json", ".jsonl", ".yaml", ".yml", ".toml", ".ini", ".txt", ".md", ".ts", ".tsx", ".css", ".html", ".js", ".mjs", ".cjs", ".sql", ".sh", ".svg", ".xml", ".csv", ".lock"}
    selected = []
    for name in sorted(set(listing)):
        if not name:
            continue
        path = Path(name)
        allowed = path.parts[0] in roots or name in root_files or name == "docs/reports/BAO_CAO_TUAN.md"
        allowed = allowed or (len(path.parts) > 2 and path.parts[0] == "docs" and path.parts[1] in doc_dirs)
        if not allowed or path.parts[:2] == ("docs", "paper"):
            continue
        if path.name in {"generate_lncs_paper.py", "render_paper_figures.mjs"}:
            continue
        if any(part in {"node_modules", "__pycache__", ".pytest_cache", "dist", ".venv", "var"} for part in path.parts):
            continue
        fixture = path.parts[:4] == ("services", "backend", "tests", "fixtures")
        if path.suffix.lower() not in extensions and path.name not in {"Dockerfile", "Makefile", *root_files} and not (fixture and path.suffix.lower() in {".pdf", ".docx"}):
            continue
        if (ROOT / path).is_file() and not (ROOT / path).is_symlink():
            copy(path.as_posix(), "02_MaNguon/" + path.as_posix())
            selected.append(path.as_posix())
    assert "research/p2_comparison/retrieval_study.py" in selected
    assert "research/core_mvp/llm_assessment.py" in selected
    write("02_MaNguon/README_CHAY_CODE.txt", """MÃ NGUỒN DỰ ÁN

Snapshot hiện trạng gồm frontend, backend, research, cấu hình và tests.
Đây không phải danh sách mọi file đều mới được viết trong tuần. Các thay đổi
chính của tuần nằm trong FILE_CHINH.txt. Bài báo không nằm trong snapshot.

Cài dependency từ thư mục 02_MaNguon:
  python3.12 -m venv .venv-research
  .venv-research/bin/python -m pip install -r research/requirements-research.txt
  .venv-research/bin/python -m pip install -r services/backend/requirements-app.txt
  npm --prefix apps/web ci

Kiểm các chức năng vừa bổ sung, không gọi model:
  .venv-research/bin/python -m pytest -q research/tests/test_p2_context_bundles.py research/tests/test_p2_retrieval_study.py research/tests/test_p2_retrieval_study_analysis.py research/tests/test_p2_evidence_review.py

Chạy bằng model thật cần runtime/model và input đã được chuẩn bị riêng.
ZIP không chứa weights, .env thật, raw corpus hoặc workbook cá nhân.
03_KetQua có số liệu và bảng từng quyết định để xem ngay, không cần model.
Snapshots_ThucNghiem giữ các file code đã khóa của hai lượt; kết hợp code
nền hiện tại với snapshot phù hợp và input đúng hash nếu tái lập lượt cũ.
""")
    write("02_MaNguon/FILE_CHINH.txt", """CÁC FILE LIÊN QUAN CÔNG VIỆC TUẦN

research/core_mvp/llm_assessment.py — verifier local, source units/context bundles và guards.
research/gold_annotation/p2_workbook_intake.py — nhận Excel, giữ nguồn gốc phiếu.
research/gold_annotation/assessment_evidence.py — span/absence evidence có kiểu.
research/p2_comparison/single_reference.py — runner tham chiếu một người.
research/p2_comparison/single_reference_metrics.py — đối chiếu nhãn và baseline.
research/p2_comparison/retrieval_study.py — không retrieval so với LOCAL BM25.
research/p2_comparison/retrieval_study_analysis.py — audit evidence và bootstrap theo report.
research/p2_comparison/evidence_review.py — phiếu kiểm ngữ nghĩa, không tự gán rating.
research/configs/p2-comparison/ — các cấu hình đã dùng/thử, có version riêng.
scripts/dev_p2_llm.py — chạy runtime model local riêng của dự án.
research/tests/test_p2_*.py, test_llm_assessment_*.py — kiểm thử liên quan.
""")
    # Exact historical executable slices, alongside the complete current source.
    for alias, prepared in (("SEFORA_Verifier", "var/paper/p2-single-reference-eval-2026-11-07/prepared-v1"),
                            ("SEFORA_Retrieval", "var/paper/p2-main-study-preparation-2026-11-08/context-retrieval-dev-prepared-v1")):
        manifest = read(prepared + "/preparation-manifest.json")
        for relative, expected in manifest["code_hashes"].items():
            source = prepared + "/code-snapshot/" + relative
            if sha(ROOT / source) != expected:
                raise ValueError("Historical executable snapshot changed")
            copy(source, "02_MaNguon/Snapshots_ThucNghiem/" + alias + "/" + relative)
    relative = "var/paper/reviewer-audit-2026-11-08/qasper/analytic_random_baseline.py"
    copy(relative, "02_MaNguon/" + relative)
    return selected


def result_snapshot():
    roots = {
        "SEFORA_Verifier": "var/paper/p2-single-reference-eval-2026-11-07/evaluation-v1",
        "SEFORA_Retrieval": "var/paper/p2-main-study-preparation-2026-11-08/context-retrieval-dev-evaluation-v1",
    }
    for alias, source in roots.items():
        for name in ("metrics.json", "comparison.csv", "mismatches.csv"):
            copy(source + "/" + name, "03_KetQua/" + alias + "/" + name)
    copy(roots["SEFORA_Verifier"] + "/telemetry.json", "03_KetQua/SEFORA_Verifier/telemetry.json")
    copy("var/paper/p2-main-study-preparation-2026-11-08/context-retrieval-dev-analysis-v1/evidence-and-retrieval-audit.json",
         "03_KetQua/SEFORA_Retrieval/evidence-and-retrieval-audit.json")
    source = "var/paper/p2-single-reference-eval-2026-11-07/evaluation-v1/evidence-audit.json"
    extract(source, "03_KetQua/SEFORA_Verifier/evidence-audit-summary.json", read(source)["summary"], ["methods: verbatim proof records"])
    source = "var/paper/sefora-p2-diagnostic-2026-11-04/improvement/replay-v2-2"
    for name in ("summary.json", "comparison-rows.json", "DOI_CHIEU_TRUOC_SAU.csv"):
        copy(source + "/" + name, "03_KetQua/SEFORA_DEV_10_Bai/" + name)
    copy("var/paper/reviewer-audit-2026-11-08/qasper/analytic-random-baseline.json", "03_KetQua/QASPER_Random/analytic-random-baseline.json")
    source = "var/paper/sefora-p2-disagreement-review-2026-11-08/v1/combined-review.json"
    data = read(source)
    keys = ("item_id", "case_id", "checklist_id", "yen_label", "model_labels", "review_proposal_label", "assessment", "confidence")
    result = {key: data[key] for key in ("classification", "scope", "assessment_counts", "confidence_counts", "review_exposure",
        "reference_labels_changed", "model_predictions_changed", "revised_accuracy_computed", "model_called")}
    result["items"] = [{key: row[key] for key in keys} for row in data["items"]]
    result["source_feedback_flags_count"] = len(data["source_feedback_flags"])
    result["not_an_independent_human_review"] = True
    extract(source, "03_KetQua/RaSoat_BatDong/review-summary.json", result,
            ["source_quotes", "rationale_vi", "model_evidence_comment_vi", "notes_vi", "source_feedback_flags.quote"])
    rows = []
    for alias, source in roots.items():
        with (ROOT / source / "comparison.csv").open(encoding="utf-8-sig", newline="") as handle:
            current = list(csv.DictReader(handle))
        assert len(current) == 90
        rows.extend({"experiment": alias, **row} for row in current)
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    target = STAGE / "03_KetQua/DOI_CHIEU_180_QUYET_DINH.csv"
    target.write_text(output.getvalue(), encoding="utf-8-sig", newline="")
    old, new = read(roots["SEFORA_Verifier"] + "/metrics.json"), read(roots["SEFORA_Retrieval"] + "/metrics.json")
    assert [old["methods"][m]["reference_label_agreement"]["matching"] for m in ("one-step", "two-step")] == [37, 32]
    assert [new["methods"][m]["reference_label_agreement"]["matching"] for m in ("no-retrieval", "local-bm25")] == [35, 32]
    write("03_KetQua/README_KET_QUA.txt", """KẾT QUẢ THỰC TẾ

SEFORA_Verifier: một bước 37/45, hai bước 32/45; baseline luôn MET 42/45.
SEFORA_Retrieval: giữ ngữ cảnh mới; toàn báo cáo 35/45, LOCAL BM25 32/45.
Hai lượt dùng CÙNG 15 bài/45 mục tham chiếu, tổng 180 bản ghi, không phải 180 mẫu độc lập.
DOI_CHIEU_180_QUYET_DINH.csv ghép các dòng nhãn để thầy kiểm nhanh.
Các file gốc metrics/comparison giữ đúng byte; số liệu đầy đủ có từng lớp/checklist.

SEFORA_DEV_10_Bai: phát triển 3/10→9/10; toàn tham chiếu MET, không phải độ chính xác chấm 90%.
QASPER_Random: baseline phân tích hậu kiểm; Hit@10 kỳ vọng 38,56%, không gọi model.
RaSoat_BatDong: đề xuất AI sau khi thấy nhãn/model, không là giám khảo thứ hai.

Không có raw essays, quote/rationale nguyên văn, workbook người gán hoặc weights.
Trích xuất summary để loại văn bản nguồn có ghi rõ trong source-map.json.
Khớp nhãn/đúng tọa độ chưa chứng minh ngữ nghĩa. Phiếu semantic support vẫn chờ.
""")


def prepare():
    if STAGE.exists() or ARCHIVE.exists():
        raise FileExistsError("Use a new package path; previous submissions are retained")
    STAGE.mkdir(parents=True, mode=0o700)
    render_report()
    source_snapshot()
    result_snapshot()
    report_text = REPORT.read_text()
    next_section = report_text.split("## 4. ", 1)[1]
    write("04_KeHoach/CONG_VIEC_TIEP_THEO.md", "# Công việc tiếp theo\n\n" + next_section)
    write("README_MO_TRUOC.txt", """BÁO CÁO TUẦN
Nguyễn Trần Ngọc Quý — 523H0087; Võ Thị Kim Yến — 52200229.

1. Mở 01_BaoCaoTuan/BAO_CAO_TUAN.pdf hoặc .docx để đọc báo cáo.
2. 02_MaNguon có mã thực frontend/backend/research, configs và tests;
  FILE_CHINH.txt chỉ các file liên quan công việc tuần.
3. 03_KetQua có metrics JSON và CSV đối chiếu kết quả thực, mở được ngay.
4. 04_KeHoach nêu việc còn làm và phần dự kiến bổ sung bài báo.

Gói này KHÔNG KÈM BÀI BÁO theo yêu cầu. Không tự gửi/nộp lên ELIT.
Không có model weights, .env thật, raw corpora hay workbook cá nhân.
Tên gói/báo cáo không có ngày lịch; timestamps/provenance trong code và
JSON kết quả gốc được giữ để truy vết. Những kết quả chưa cải thiện vẫn được báo.
source-map.json và package-manifest.json dùng kiểm nguồn/checksum.
""")
    write("source-map.json", {"files": RECEIPTS, "all_original_sources_unchanged": True,
        "contains_article": False, "purpose": "Weekly supervisor review of code and actual results"})
    print(json.dumps({"stage": str(STAGE), "print_html": str(PRINT_HTML),
        "pdf_target": str(STAGE / "01_BaoCaoTuan/BAO_CAO_TUAN.pdf"), "files_before_pdf": len(list(STAGE.rglob("*")))}, indent=2))


def finalize():
    if ARCHIVE.exists():
        raise FileExistsError("Archive already exists; no overwrite")
    for name in ("BAO_CAO_TUAN.pdf", "BAO_CAO_TUAN.docx"):
        if not (STAGE / "01_BaoCaoTuan" / name).is_file():
            raise ValueError("Both PDF and Word reports are required")
    source_map = json.loads((STAGE / "source-map.json").read_text())
    for row in source_map["files"]:
        assert sha(ROOT / row["source"]) == row["source_sha256"]
        if row["transformation"] == "BYTE_IDENTICAL_COPY":
            assert sha(STAGE / row["output"]) == row["source_sha256"]
    files = sorted(p for p in STAGE.rglob("*") if p.is_file())
    for path in files:
        relative = path.relative_to(STAGE)
        article_path = any(relative.parts[index:index + 2] == ("docs", "paper")
                           for index in range(len(relative.parts) - 1))
        if (article_path or any(part in {"node_modules", "__pycache__", ".git"} for part in relative.parts)
                or path.name == ".env" or "BaiBao_" in path.name):
            raise ValueError("Excluded paper/runtime/secret path entered package")
        if path.suffix == ".py":
            ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(relative))
    manifest = {"package_name": "BÁO CÁO TUẦN", "contains_article": False, "contains_code": True,
        "contains_actual_result_json_csv": True, "contains_model_weights": False, "contains_raw_student_reports": False,
        "source_git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip(),
        "working_tree_snapshot_includes_uncommitted_authorized_changes": True,
        "files": [{"path": str(p.relative_to(STAGE)), "bytes": p.stat().st_size, "sha256": sha(p)} for p in files]}
    write("package-manifest.json", manifest)
    with ZipFile(ARCHIVE, "x", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(p for p in STAGE.rglob("*") if p.is_file()):
            archive.write(path, "BAO_CAO_TUAN/" + path.relative_to(STAGE).as_posix())
    with ZipFile(ARCHIVE) as archive:
        assert archive.testzip() is None
        assert len(archive.namelist()) == len(manifest["files"]) + 1
        for row in manifest["files"]:
            assert hashlib.sha256(archive.read("BAO_CAO_TUAN/" + row["path"])).hexdigest() == row["sha256"]
    assert ARCHIVE.stat().st_size < 20 * 1024 * 1024
    verification = {"status": "VERIFIED", "archive": str(ARCHIVE.relative_to(ROOT)),
        "bytes": ARCHIVE.stat().st_size, "sha256": sha(ARCHIVE), "files": len(manifest["files"]) + 1,
        "extensions": dict(Counter(p.suffix for p in STAGE.rglob("*") if p.is_file())),
        "zip_crc_and_all_file_hashes": "PASS", "python_syntax": "PASS", "article_excluded": True,
        "original_source_hashes_unchanged": True}
    ARCHIVE.with_suffix(".verification.json").write_text(json.dumps(verification, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(verification, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "finalize"))
    if parser.parse_args().command == "prepare":
        prepare()
    else:
        finalize()
