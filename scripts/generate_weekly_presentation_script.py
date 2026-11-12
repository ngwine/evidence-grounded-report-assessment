"""Generate the speaker-notes DOCX from the checked-in Markdown source."""

from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs/reports/SCRIPT_THUYET_TRINH_BAO_CAO_TUAN_05-11.09.2026.md"
OUTPUT = ROOT / "docs/reports/ScriptThuyetTrinh_BaoCaoTienDoTuan_KLTN_523H0087_52200229.docx"

NAVY = "17365D"
TEAL = "007A78"
BLUE = "2F75B5"
LIGHT_BLUE = "EAF3F8"
LIGHT_TEAL = "E8F4F3"
LIGHT_GRAY = "F3F5F7"
DARK = "1F2933"
MUTED = "52606D"
WHITE = "FFFFFF"
BORDER = "CBD5E1"


def set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_border(cell, **edges) -> None:
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_borders = tc_pr.first_child_found_in("w:tcBorders")
    if tc_borders is None:
        tc_borders = OxmlElement("w:tcBorders")
        tc_pr.append(tc_borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        if edge not in edges:
            continue
        tag = f"w:{edge}"
        element = tc_borders.find(qn(tag))
        if element is None:
            element = OxmlElement(tag)
            tc_borders.append(element)
        for key, value in edges[edge].items():
            element.set(qn(f"w:{key}"), str(value))


def set_repeat_table_header(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)


def add_page_number(paragraph) -> None:
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = paragraph.add_run("Trang ")
    run.font.name = "Aptos"
    run.font.size = Pt(8)
    run.font.color.rgb = RGBColor.from_string(MUTED)
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instruction = OxmlElement("w:instrText")
    instruction.set(qn("xml:space"), "preserve")
    instruction.text = " PAGE "
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._r.extend([begin, instruction, end])


def set_repeat_header(section) -> None:
    header = section.header
    paragraph = header.paragraphs[0]
    paragraph.text = "SCRIPT THUYẾT TRÌNH  •  BÁO CÁO TIẾN ĐỘ TUẦN 05–11/09/2026"
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = paragraph.runs[0]
    run.font.name = "Aptos"
    run.font.size = Pt(8)
    run.font.bold = True
    run.font.color.rgb = RGBColor.from_string(BLUE)
    add_page_number(section.footer.paragraphs[0])


def set_run_font(run, name="Aptos", size=11.2, color=DARK, bold=False, italic=False) -> None:
    run.font.name = name
    run._element.rPr.rFonts.set(qn("w:eastAsia"), name)
    run.font.size = Pt(size)
    run.font.color.rgb = RGBColor.from_string(color)
    run.bold = bold
    run.italic = italic


def add_rich_text(paragraph, text: str, *, base_size=11.2, base_color=DARK) -> None:
    pattern = re.compile(r"(\*\*.+?\*\*|`.+?`)")
    position = 0
    for match in pattern.finditer(text):
        if match.start() > position:
            set_run_font(paragraph.add_run(text[position : match.start()]), size=base_size, color=base_color)
        token = match.group(0)
        if token.startswith("**"):
            set_run_font(paragraph.add_run(token[2:-2]), size=base_size, color=base_color, bold=True)
        else:
            set_run_font(paragraph.add_run(token[1:-1]), name="SFMono-Regular", size=9.6, color=NAVY)
        position = match.end()
    if position < len(text):
        set_run_font(paragraph.add_run(text[position:]), size=base_size, color=base_color)


def set_paragraph_body(paragraph, *, after=6, before=0, line=1.12) -> None:
    paragraph.paragraph_format.space_after = Pt(after)
    paragraph.paragraph_format.space_before = Pt(before)
    paragraph.paragraph_format.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
    paragraph.paragraph_format.line_spacing = line


def add_box(document, text: str, *, fill=LIGHT_BLUE, accent=BLUE, label: str | None = None) -> None:
    table = document.add_table(rows=1, cols=1)
    table.autofit = True
    cell = table.cell(0, 0)
    set_cell_shading(cell, fill)
    set_cell_border(
        cell,
        left={"val": "single", "sz": "18", "color": accent},
        top={"val": "single", "sz": "2", "color": fill},
        bottom={"val": "single", "sz": "2", "color": fill},
        right={"val": "single", "sz": "2", "color": fill},
    )
    cell.margin_top = Cm(0.15)
    paragraph = cell.paragraphs[0]
    set_paragraph_body(paragraph, after=1, line=1.05)
    if label:
        run = paragraph.add_run(label.upper() + "  ")
        set_run_font(run, size=8.7, color=accent, bold=True)
    add_rich_text(paragraph, text, base_size=10.2, base_color=DARK)
    document.add_paragraph().paragraph_format.space_after = Pt(0)


def add_cover(document) -> None:
    section = document.sections[0]
    section.top_margin = Cm(1.7)
    section.bottom_margin = Cm(1.7)
    section.left_margin = Cm(1.9)
    section.right_margin = Cm(1.9)

    bar = document.add_table(rows=1, cols=1)
    bar_cell = bar.cell(0, 0)
    set_cell_shading(bar_cell, NAVY)
    bar_cell.height = Cm(0.35)
    bar_cell.paragraphs[0].text = ""

    document.add_paragraph().paragraph_format.space_after = Pt(20)
    kicker = document.add_paragraph()
    kicker.alignment = WD_ALIGN_PARAGRAPH.LEFT
    set_run_font(kicker.add_run("BÁO CÁO TIẾN ĐỘ TUẦN  •  05–11/09/2026"), size=11, color=TEAL, bold=True)
    kicker.paragraph_format.space_after = Pt(12)

    title = document.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.LEFT
    set_run_font(title.add_run("SCRIPT\nTHUYẾT TRÌNH"), size=30, color=NAVY, bold=True)
    title.paragraph_format.line_spacing = 0.9
    title.paragraph_format.space_after = Pt(18)

    subtitle = document.add_paragraph()
    add_rich_text(
        subtitle,
        "Xây dựng hệ thống hỗ trợ kiểm tra đạo văn và đánh giá báo cáo sinh viên dựa trên bằng chứng",
        base_size=16,
        base_color=DARK,
    )
    subtitle.paragraph_format.space_after = Pt(6)

    english = document.add_paragraph()
    run = english.add_run(
        "Development of an Evidence-Grounded System for Plagiarism Checking and Student Report Assessment"
    )
    set_run_font(run, size=10.5, color=MUTED, italic=True)
    english.paragraph_format.space_after = Pt(28)

    info = document.add_table(rows=4, cols=2)
    info.autofit = False
    info.columns[0].width = Cm(4.2)
    info.columns[1].width = Cm(12.2)
    rows = [
        ("THỜI LƯỢNG", "8–10 phút"),
        ("THÀNH VIÊN", "Nguyễn Trần Ngọc Quý — 523H0087"),
        ("", "Võ Thị Kim Yến — 52200229"),
        ("GIẢNG VIÊN HƯỚNG DẪN", "Vũ Đình Hồng"),
    ]
    for index, (left, right) in enumerate(rows):
        for cell in info.rows[index].cells:
            set_cell_shading(cell, LIGHT_GRAY if index % 2 == 0 else WHITE)
            set_cell_border(cell, bottom={"val": "single", "sz": "2", "color": BORDER})
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        p_left = info.cell(index, 0).paragraphs[0]
        set_run_font(p_left.add_run(left), size=8.2, color=BLUE, bold=True)
        p_right = info.cell(index, 1).paragraphs[0]
        set_run_font(p_right.add_run(right), size=10.5, color=DARK, bold=index in (1, 2))

    document.add_paragraph().paragraph_format.space_after = Pt(15)
    add_box(
        document,
        "Phần chữ thông thường có thể nói trực tiếp. Nội dung trong ngoặc vuông là thao tác trình bày; phần sau dấu “Chuyển” là câu nối sang nội dung kế tiếp.",
        fill=LIGHT_TEAL,
        accent=TEAL,
        label="Cách sử dụng",
    )

    document.add_page_break()


def add_section_heading(document, title: str, *, level: int) -> None:
    if level == 1:
        paragraph = document.add_paragraph()
        set_run_font(paragraph.add_run(title), size=22, color=NAVY, bold=True)
        paragraph.paragraph_format.space_before = Pt(3)
        paragraph.paragraph_format.space_after = Pt(13)
    else:
        paragraph = document.add_paragraph()
        set_run_font(paragraph.add_run(title), size=17, color=NAVY, bold=True)
        paragraph.paragraph_format.keep_with_next = True
        paragraph.paragraph_format.space_before = Pt(5)
        paragraph.paragraph_format.space_after = Pt(8)
        p_pr = paragraph._p.get_or_add_pPr()
        border = OxmlElement("w:pBdr")
        bottom = OxmlElement("w:bottom")
        bottom.set(qn("w:val"), "single")
        bottom.set(qn("w:sz"), "12")
        bottom.set(qn("w:space"), "5")
        bottom.set(qn("w:color"), TEAL)
        border.append(bottom)
        p_pr.append(border)


def add_timing(document, text: str) -> None:
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.space_after = Pt(8)
    run = paragraph.add_run("⏱  " + text.replace("**", ""))
    set_run_font(run, size=9.5, color=TEAL, bold=True)


def add_code_block(document, lines: list[str]) -> None:
    table = document.add_table(rows=1, cols=1)
    cell = table.cell(0, 0)
    set_cell_shading(cell, LIGHT_GRAY)
    set_cell_border(
        cell,
        top={"val": "single", "sz": "3", "color": BORDER},
        bottom={"val": "single", "sz": "3", "color": BORDER},
        left={"val": "single", "sz": "3", "color": BORDER},
        right={"val": "single", "sz": "3", "color": BORDER},
    )
    paragraph = cell.paragraphs[0]
    paragraph.paragraph_format.space_after = Pt(0)
    for index, line in enumerate(lines):
        if index:
            paragraph.add_run("\n")
        run = paragraph.add_run(line)
        set_run_font(run, name="SFMono-Regular", size=8.2, color=DARK)
    document.add_paragraph().paragraph_format.space_after = Pt(0)


def build_document(markdown: str) -> Document:
    document = Document()
    core = document.core_properties
    core.title = "Script thuyết trình báo cáo tiến độ tuần 05–11/09/2026"
    core.subject = "KLTN Evidence-Grounded System"
    core.author = "Nguyễn Trần Ngọc Quý; Võ Thị Kim Yến"
    core.keywords = "KLTN, presentation script, evidence-grounded, weekly progress"

    styles = document.styles
    normal = styles["Normal"]
    normal.font.name = "Aptos"
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Aptos")
    normal.font.size = Pt(11.2)
    normal.font.color.rgb = RGBColor.from_string(DARK)

    for section in document.sections:
        set_repeat_header(section)
    add_cover(document)

    lines = markdown.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("## Phân chia"))
    lines = lines[start:]
    code_lines: list[str] = []
    in_code = False
    first_main_page = True
    seen_h1 = False

    for raw_line in lines:
        line = raw_line.rstrip()
        stripped = line.strip()

        if stripped.startswith("```"):
            if in_code:
                add_code_block(document, code_lines)
                code_lines = []
            in_code = not in_code
            continue
        if in_code:
            code_lines.append(line)
            continue
        if not stripped or stripped == "---":
            continue

        if stripped.startswith("# "):
            if seen_h1 or document.paragraphs:
                document.add_page_break()
            seen_h1 = True
            add_section_heading(document, stripped[2:], level=1)
            continue

        if stripped.startswith("## "):
            title = stripped[3:]
            if title.startswith("Trang "):
                if not first_main_page:
                    document.add_page_break()
                first_main_page = False
            elif title.startswith(tuple(f"{n}." for n in range(1, 20))):
                pass
            elif title != "Phân chia nếu cả hai cùng trình bày":
                document.add_page_break()
            add_section_heading(document, title, level=2)
            continue

        if stripped.startswith("**Thời lượng:**"):
            add_timing(document, stripped)
            continue

        if stripped.startswith("**Chuyển:**"):
            add_box(document, stripped[len("**Chuyển:**") :].strip(), fill=LIGHT_TEAL, accent=TEAL, label="Chuyển ý")
            continue

        if stripped.startswith("> "):
            add_box(document, stripped[2:], fill=LIGHT_BLUE, accent=BLUE, label="Lưu ý")
            continue

        if stripped.startswith("- "):
            paragraph = document.add_paragraph(style="List Bullet")
            set_paragraph_body(paragraph, after=4, line=1.08)
            add_rich_text(paragraph, stripped[2:], base_size=10.5)
            continue

        if stripped.startswith("[") and stripped.endswith("]"):
            add_box(document, stripped[1:-1], fill=LIGHT_BLUE, accent=BLUE, label="Thao tác")
            continue

        paragraph = document.add_paragraph()
        set_paragraph_body(paragraph)
        add_rich_text(paragraph, stripped)

    return document


def main() -> None:
    markdown = SOURCE.read_text(encoding="utf-8")
    document = build_document(markdown)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    document.save(OUTPUT)
    print(OUTPUT)


if __name__ == "__main__":
    main()
