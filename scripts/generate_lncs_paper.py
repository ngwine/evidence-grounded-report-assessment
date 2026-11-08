#!/usr/bin/env python3
"""Generate the English thesis paper in a Springer LNCS-like Word layout.

The supplied `svlnproc1104.dot` is a legacy binary Word template whose macros
cannot be executed by python-docx.  This generator mirrors its documented page,
paragraph, heading, caption, list, table, equation, abstract, keyword, and
reference conventions.  The resulting DOCX can still be attached to the
original DOT in Microsoft Word if the publisher requires macro-linked styles.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Iterable

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import (
    WD_ALIGN_PARAGRAPH,
    WD_BREAK,
    WD_LINE_SPACING,
)
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs/paper/BaiBao_523H0087_52200229_EN.md"
OUTPUT = ROOT / "docs/paper/BaiBao_523H0087_52200229_EN_LNCS.docx"
FIGURE_1 = ROOT / "docs/paper/figures/framework_overview.png"
FIGURE_2 = ROOT / "docs/paper/figures/pipeline1_experiment.png"

FONT = "Times New Roman"
MONO_FONT = "Courier New"
TEXT_WIDTH_CM = 12.2

TABLE_CAPTIONS = [
    "Claim–evidence relations and final checklist outcomes.",
    "Dataset roles and the evidence actually available in this study.",
    "Locked A1–A5 ablation configurations.",
    "Repository artifacts supporting the reported run.",
    "Query-window macro results on the frozen DEV0 diagnostic.",
    "Parent-annotation-balanced macro results on DEV0.",
    "Paired parent-cluster bootstrap contrasts on DEV0; delta is left method minus right method.",
    "Rank-transition groups used to explain fusion and reranking behavior.",
    "Controlled A5/A6 input-construction comparison on DEV1; parent-balanced metrics with 95% parent-cluster intervals.",
    "Within-paper paragraph evidence retrieval on 646 evaluable QASPER DEV questions.",
]


@dataclass
class Block:
    kind: str
    value: object


def set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_margins(cell, *, top=55, start=70, bottom=55, end=70) -> None:
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for edge, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        tag = f"w:{edge}"
        node = tc_mar.find(qn(tag))
        if node is None:
            node = OxmlElement(tag)
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def prevent_row_split(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    cant_split = OxmlElement("w:cantSplit")
    tr_pr.append(cant_split)


def repeat_table_header(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)


def remove_table_borders(table) -> None:
    """Make a layout table invisible in Word-compatible renderers."""

    tbl_pr = table._tbl.tblPr
    borders = tbl_pr.find(qn("w:tblBorders"))
    if borders is None:
        borders = OxmlElement("w:tblBorders")
        tbl_pr.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        node = borders.find(qn(f"w:{edge}"))
        if node is None:
            node = OxmlElement(f"w:{edge}")
            borders.append(node)
        node.set(qn("w:val"), "nil")


def set_cell_width(cell, width_cm: float) -> None:
    cell.width = Cm(width_cm)
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_w = tc_pr.find(qn("w:tcW"))
    if tc_w is None:
        tc_w = OxmlElement("w:tcW")
        tc_pr.append(tc_w)
    # ``w:tcW`` with type ``dxa`` is expressed in twips, while python-docx's
    # Length integer value is EMU.  Writing EMU here makes Word expand tables
    # far beyond the 122 mm LNCS text block.
    tc_w.set(qn("w:w"), str(int(Cm(width_cm).twips)))
    tc_w.set(qn("w:type"), "dxa")


def add_hyperlink(paragraph, text: str, url: str):
    part = paragraph.part
    relationship_id = part.relate_to(
        url,
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
        is_external=True,
    )
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), relationship_id)
    run = OxmlElement("w:r")
    r_pr = OxmlElement("w:rPr")
    color = OxmlElement("w:color")
    color.set(qn("w:val"), "000000")
    r_pr.append(color)
    underline = OxmlElement("w:u")
    underline.set(qn("w:val"), "none")
    r_pr.append(underline)
    run.append(r_pr)
    text_node = OxmlElement("w:t")
    text_node.text = text
    run.append(text_node)
    hyperlink.append(run)
    paragraph._p.append(hyperlink)
    return hyperlink


def apply_run_font(run, *, size: float = 10, bold=None, italic=None, mono=False) -> None:
    run.font.name = MONO_FONT if mono else FONT
    run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic
    r_pr = run._element.get_or_add_rPr()
    r_fonts = r_pr.rFonts
    if r_fonts is None:
        r_fonts = OxmlElement("w:rFonts")
        r_pr.insert(0, r_fonts)
    chosen = MONO_FONT if mono else FONT
    for key in ("ascii", "hAnsi", "eastAsia", "cs"):
        r_fonts.set(qn(f"w:{key}"), chosen)
    lang = r_pr.find(qn("w:lang"))
    if lang is None:
        lang = OxmlElement("w:lang")
        r_pr.append(lang)
    lang.set(qn("w:val"), "en-US")


INLINE_RE = re.compile(
    r"(\*\*[^*]+\*\*|`[^`]+`|https?://[^\s)]+\)?|\[[0-9]+(?:[–-][0-9]+)?(?:,\s*[0-9]+)*\])"
)


def add_inline(paragraph, text: str, *, size: float = 10) -> None:
    text = text.replace("--", "–")
    position = 0
    for match in INLINE_RE.finditer(text):
        if match.start() > position:
            run = paragraph.add_run(text[position : match.start()])
            apply_run_font(run, size=size)
        token = match.group(0)
        if token.startswith("**"):
            run = paragraph.add_run(token[2:-2])
            apply_run_font(run, size=size, bold=True)
        elif token.startswith("`"):
            run = paragraph.add_run(token[1:-1])
            apply_run_font(run, size=max(7.2, size - 0.8), mono=True)
        elif token.startswith("http"):
            trailing = ")" if token.endswith(")") else ""
            url = token[:-1] if trailing else token
            add_hyperlink(paragraph, url, url)
            if trailing:
                run = paragraph.add_run(trailing)
                apply_run_font(run, size=size)
        else:
            run = paragraph.add_run(token)
            apply_run_font(run, size=size)
        position = match.end()
    if position < len(text):
        run = paragraph.add_run(text[position:])
        apply_run_font(run, size=size)


def parse_markdown(path: Path) -> list[Block]:
    lines = path.read_text(encoding="utf-8").splitlines()
    blocks: list[Block] = []
    index = 0
    while index < len(lines):
        line = lines[index].rstrip()
        if not line:
            index += 1
            continue
        if line.startswith("# "):
            blocks.append(Block("title", line[2:].strip()))
            index += 1
            continue
        if line.startswith("### "):
            blocks.append(Block("heading2", line[4:].strip()))
            index += 1
            continue
        if line.startswith("## "):
            blocks.append(Block("heading1", line[3:].strip()))
            index += 1
            continue
        if line.startswith("|"):
            table_lines: list[str] = []
            while index < len(lines) and lines[index].lstrip().startswith("|"):
                table_lines.append(lines[index].strip())
                index += 1
            rows: list[list[str]] = []
            for row_index, table_line in enumerate(table_lines):
                cells = [cell.strip() for cell in table_line.strip("|").split("|")]
                if row_index == 1 and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
                    continue
                rows.append(cells)
            blocks.append(Block("table", rows))
            continue
        if line.startswith("- "):
            items: list[str] = []
            while index < len(lines) and lines[index].startswith("- "):
                items.append(lines[index][2:].strip())
                index += 1
            blocks.append(Block("bullets", items))
            continue
        if re.match(r"^\d+\.\s", line):
            items: list[str] = []
            while index < len(lines) and re.match(r"^\d+\.\s", lines[index]):
                items.append(re.sub(r"^\d+\.\s+", "", lines[index].strip()))
                index += 1
            blocks.append(Block("numbers", items))
            continue
        paragraph_lines = [line]
        index += 1
        while index < len(lines):
            candidate = lines[index].rstrip()
            if not candidate:
                break
            if (
                candidate.startswith("#")
                or candidate.startswith("|")
                or candidate.startswith("- ")
                or re.match(r"^\d+\.\s", candidate)
            ):
                break
            paragraph_lines.append(candidate)
            index += 1
        blocks.append(Block("paragraph", " ".join(part.strip() for part in paragraph_lines)))
    return blocks


def add_style(document: Document, name: str, style_type=WD_STYLE_TYPE.PARAGRAPH):
    try:
        return document.styles[name]
    except KeyError:
        return document.styles.add_style(name, style_type)


def configure_styles(document: Document) -> None:
    styles = document.styles

    normal = styles["Normal"]
    normal.font.name = FONT
    normal.font.size = Pt(10)
    normal.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    normal.paragraph_format.line_spacing_rule = WD_LINE_SPACING.EXACTLY
    normal.paragraph_format.line_spacing = Pt(12)
    normal.paragraph_format.space_after = Pt(0)
    normal.paragraph_format.widow_control = True

    title = styles["Title"]
    title.font.name = FONT
    title.font.size = Pt(14)
    title.font.bold = True
    title.font.color.rgb = RGBColor(0, 0, 0)
    title.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.paragraph_format.line_spacing_rule = WD_LINE_SPACING.EXACTLY
    title.paragraph_format.line_spacing = Pt(17)
    title.paragraph_format.space_before = Pt(0)
    title.paragraph_format.space_after = Pt(14)
    title.paragraph_format.keep_with_next = True
    title_p_pr = title._element.get_or_add_pPr()
    title_border = title_p_pr.find(qn("w:pBdr"))
    if title_border is not None:
        title_p_pr.remove(title_border)

    author = add_style(document, "Author")
    author.font.name = FONT
    author.font.size = Pt(11)
    author.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    author.paragraph_format.space_after = Pt(5)
    author.paragraph_format.keep_with_next = True

    affiliation = add_style(document, "Affiliation")
    affiliation.font.name = FONT
    affiliation.font.size = Pt(9)
    affiliation.font.italic = True
    affiliation.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    affiliation.paragraph_format.space_after = Pt(14)
    affiliation.paragraph_format.keep_with_next = True

    abstract = add_style(document, "Abstract")
    abstract.font.name = FONT
    abstract.font.size = Pt(9)
    abstract.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    abstract.paragraph_format.left_indent = Cm(0.6)
    abstract.paragraph_format.right_indent = Cm(0.6)
    abstract.paragraph_format.line_spacing_rule = WD_LINE_SPACING.EXACTLY
    abstract.paragraph_format.line_spacing = Pt(10.8)
    abstract.paragraph_format.space_after = Pt(6)

    keywords = add_style(document, "Keywords")
    keywords.font.name = FONT
    keywords.font.size = Pt(9)
    keywords.paragraph_format.left_indent = Cm(0.6)
    keywords.paragraph_format.right_indent = Cm(0.6)
    keywords.paragraph_format.space_after = Pt(11)

    heading1 = styles["Heading 1"]
    heading1.font.name = FONT
    heading1.font.size = Pt(12)
    heading1.font.bold = True
    heading1.font.color.rgb = RGBColor(0, 0, 0)
    heading1.paragraph_format.space_before = Pt(12)
    heading1.paragraph_format.space_after = Pt(5)
    heading1.paragraph_format.keep_with_next = True
    heading1.paragraph_format.keep_together = True

    heading2 = styles["Heading 2"]
    heading2.font.name = FONT
    heading2.font.size = Pt(10)
    heading2.font.bold = True
    heading2.font.color.rgb = RGBColor(0, 0, 0)
    heading2.paragraph_format.space_before = Pt(9)
    heading2.paragraph_format.space_after = Pt(3)
    heading2.paragraph_format.keep_with_next = True
    heading2.paragraph_format.keep_together = True

    caption = add_style(document, "Figure caption")
    caption.font.name = FONT
    caption.font.size = Pt(9)
    caption.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    caption.paragraph_format.space_before = Pt(3)
    caption.paragraph_format.space_after = Pt(7)
    caption.paragraph_format.keep_with_next = False

    table_caption = add_style(document, "Table caption")
    table_caption.font.name = FONT
    table_caption.font.size = Pt(9)
    table_caption.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT
    table_caption.paragraph_format.space_before = Pt(6)
    table_caption.paragraph_format.space_after = Pt(3)
    table_caption.paragraph_format.keep_with_next = True

    equation = add_style(document, "Equation")
    equation.font.name = "Cambria Math"
    equation.font.size = Pt(9.5)
    equation.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    equation.paragraph_format.space_before = Pt(4)
    equation.paragraph_format.space_after = Pt(4)
    equation.paragraph_format.keep_together = True

    reference = add_style(document, "Reference")
    reference.font.name = FONT
    reference.font.size = Pt(9)
    reference.paragraph_format.left_indent = Cm(0.55)
    reference.paragraph_format.first_line_indent = Cm(-0.55)
    reference.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    reference.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
    reference.paragraph_format.space_after = Pt(2)


def configure_document(document: Document) -> None:
    section = document.sections[0]
    section.page_width = Cm(15.5)
    section.page_height = Cm(23.5)
    section.left_margin = Cm(1.65)
    section.right_margin = Cm(1.65)
    section.top_margin = Cm(2.0)
    section.bottom_margin = Cm(2.2)
    section.header_distance = Cm(0.7)
    section.footer_distance = Cm(0.8)
    section.start_type = WD_SECTION.NEW_PAGE

    settings = document.settings._element
    update_fields = settings.find(qn("w:updateFields"))
    if update_fields is None:
        update_fields = OxmlElement("w:updateFields")
        settings.append(update_fields)
    update_fields.set(qn("w:val"), "true")

    document.core_properties.title = (
        "An Evidence-Grounded Framework for Similarity Analysis and "
        "Rubric-Based Assessment of Student Reports"
    )
    document.core_properties.subject = "Framework design and preliminary source-retrieval evaluation"
    document.core_properties.author = "Nguyen Tran Ngoc Quy; Vo Thi Kim Yen"
    document.core_properties.keywords = (
        "evidence-grounded assessment, similarity analysis, BM25, dense retrieval, "
        "RRF, Cross-Encoder, rubric assessment"
    )
    document.core_properties.comments = (
        "Generated from the English source and formatted to the supplied Springer "
        "Word 2003 proceedings instructions."
    )


def body_paragraph(document: Document, text: str, *, first_after_structure: bool) -> None:
    paragraph = document.add_paragraph(style="Normal")
    paragraph.paragraph_format.first_line_indent = Cm(0 if first_after_structure else 0.4)
    paragraph.paragraph_format.keep_together = False
    add_inline(paragraph, text, size=10)


def add_equation(document: Document, text: str) -> None:
    """Add an inline OMML equation with a right-aligned equation number."""

    match = re.fullmatch(r"(.+?)\s*\((\d+)\)", text.strip())
    if match is None:
        raise ValueError(f"Equation is missing a terminal number: {text!r}")
    formula, number = match.groups()
    table = document.add_table(rows=1, cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    remove_table_borders(table)
    row = table.rows[0]
    prevent_row_split(row)
    formula_cell, number_cell = row.cells
    set_cell_width(formula_cell, 11.3)
    set_cell_width(number_cell, 0.9)
    set_cell_margins(formula_cell, top=0, start=0, bottom=0, end=0)
    set_cell_margins(number_cell, top=0, start=0, bottom=0, end=0)

    paragraph = formula_cell.paragraphs[0]
    paragraph.style = "Equation"
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    math = OxmlElement("m:oMath")
    math_run = OxmlElement("m:r")
    math_text = OxmlElement("m:t")
    math_text.text = formula
    math_run.append(math_text)
    math.append(math_run)
    paragraph._p.append(math)

    number_paragraph = number_cell.paragraphs[0]
    number_paragraph.style = "Equation"
    number_paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    suffix = number_paragraph.add_run(f"({number})")
    apply_run_font(suffix, size=9.5)


def add_figure(document: Document, path: Path, number: int, caption: str) -> None:
    paragraph = document.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.space_before = Pt(3)
    paragraph.paragraph_format.space_after = Pt(0)
    # ``Normal`` uses exact 12-pt leading for body text.  Inline images must
    # override that rule or legacy Word/Pages importers place most of the image
    # outside the paragraph's line box and overlap/split surrounding content.
    paragraph.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
    paragraph.paragraph_format.line_spacing = 1
    paragraph.paragraph_format.keep_together = True
    paragraph.paragraph_format.keep_with_next = True
    paragraph.add_run().add_picture(str(path), width=Cm(12.0))
    cap = document.add_paragraph(style="Figure caption")
    run = cap.add_run(f"Fig. {number}. ")
    apply_run_font(run, size=9, bold=True)
    add_inline(cap, caption, size=9)


def widths_for_table(header: list[str]) -> list[float]:
    columns = len(header)
    if header[:2] == ["Claim--evidence relation", "Checklist outcome"]:
        return [2.45, 2.0, 7.75]
    if header[:2] == ["Dataset", "Intended role"]:
        return [2.2, 4.1, 5.9]
    if header and header[0] == "ID":
        return [0.8, 3.4, 3.0, 5.0]
    if header[:2] == ["Artifact", "Repository-relative path"]:
        return [1.5, 6.5, 4.2]
    if header and header[0] == "Contrast":
        return [1.6, 3.5, 3.5, 3.6]
    if columns == 8:
        return [2.65] + [1.36] * 7
    if header and header[0] == "Transition group":
        return [4.0, 1.0, 7.2]
    if header[:2] == ["Method", "Parent R@10 [95% CI]"]:
        return [0.9, 3.2, 3.2, 3.2, 1.7]
    if columns == 7 and header[:2] == ["Method", "Hit@1"]:
        return [3.0, 1.4, 1.4, 1.4, 1.8, 1.7, 1.5]
    return [TEXT_WIDTH_CM / columns] * columns


def add_table(document: Document, rows: list[list[str]], number: int) -> None:
    caption = document.add_paragraph(style="Table caption")
    run = caption.add_run(f"Table {number}. ")
    apply_run_font(run, size=9, bold=True)
    add_inline(caption, TABLE_CAPTIONS[number - 1], size=9)

    table = document.add_table(rows=len(rows), cols=len(rows[0]))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    table.style = "Table Grid"
    widths = widths_for_table(rows[0])

    for row_index, values in enumerate(rows):
        row = table.rows[row_index]
        prevent_row_split(row)
        if row_index == 0:
            repeat_table_header(row)
        for cell_index, value in enumerate(values):
            cell = row.cells[cell_index]
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            set_cell_width(cell, widths[cell_index])
            set_cell_margins(cell)
            if row_index == 0:
                set_cell_shading(cell, "D9E2F3")
            paragraph = cell.paragraphs[0]
            paragraph.alignment = (
                WD_ALIGN_PARAGRAPH.LEFT
                if cell_index == 0 or not re.fullmatch(r"\*\*[0-9.]+\*\*|[0-9.]+", value)
                else WD_ALIGN_PARAGRAPH.CENTER
            )
            paragraph.paragraph_format.space_after = Pt(0)
            paragraph.paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
            add_inline(paragraph, value, size=7.25 if len(rows[0]) >= 7 else 8.0)
            if row_index == 0:
                for run in paragraph.runs:
                    run.bold = True
    after = document.add_paragraph()
    after.paragraph_format.space_after = Pt(0)


def add_bullets(document: Document, items: Iterable[str]) -> None:
    for item in items:
        paragraph = document.add_paragraph(style="Normal")
        paragraph.paragraph_format.left_indent = Cm(0.5)
        paragraph.paragraph_format.first_line_indent = Cm(-0.35)
        paragraph.paragraph_format.space_after = Pt(1)
        run = paragraph.add_run("• ")
        apply_run_font(run, size=10)
        add_inline(paragraph, item, size=10)


def add_numbers(document: Document, items: Iterable[str]) -> None:
    values = list(items)
    for number, item in enumerate(values, 1):
        paragraph = document.add_paragraph(style="Normal")
        paragraph.paragraph_format.left_indent = Cm(0.55)
        paragraph.paragraph_format.first_line_indent = Cm(-0.45)
        paragraph.paragraph_format.space_after = Pt(1)
        paragraph.paragraph_format.keep_with_next = number < len(values)
        run = paragraph.add_run(f"{number}. ")
        apply_run_font(run, size=9.5, bold=True)
        add_inline(paragraph, item, size=9.5)


def build() -> Path:
    blocks = parse_markdown(SOURCE)
    document = Document()
    configure_document(document)
    configure_styles(document)

    current_section = ""
    first_after_structure = True
    table_number = 0
    pending_abstract = False
    inserted_fig1 = False
    inserted_fig2 = False
    seen_title = False
    seen_author = False
    seen_affiliation = False

    for block in blocks:
        if block.kind == "title":
            paragraph = document.add_paragraph(style="Title")
            add_inline(paragraph, str(block.value), size=14)
            seen_title = True
            continue

        if seen_title and not seen_author and block.kind == "paragraph":
            paragraph = document.add_paragraph(style="Author")
            add_inline(paragraph, str(block.value), size=11)
            seen_author = True
            continue

        if seen_author and not seen_affiliation and block.kind == "paragraph":
            paragraph = document.add_paragraph(style="Affiliation")
            add_inline(paragraph, str(block.value), size=9)
            seen_affiliation = True
            continue

        if block.kind == "heading1":
            current_section = str(block.value)
            if current_section == "Abstract":
                pending_abstract = True
                continue
            if current_section == "References":
                paragraph = document.add_paragraph(style="Heading 1")
                add_inline(paragraph, current_section, size=12)
            else:
                paragraph = document.add_paragraph(style="Heading 1")
                add_inline(paragraph, current_section, size=12)
            if current_section.startswith("3 Proposed"):
                paragraph.paragraph_format.page_break_before = True
            first_after_structure = True
            if current_section.startswith("3 Proposed") and not inserted_fig1:
                add_figure(
                    document,
                    FIGURE_1,
                    1,
                    "The shared provenance layer feeds two evidence-grounded pipelines; "
                    "instructor review remains the final decision boundary.",
                )
                inserted_fig1 = True
            continue

        if block.kind == "heading2":
            heading_text = str(block.value)
            paragraph = document.add_paragraph(style="Heading 2")
            add_inline(paragraph, heading_text, size=10)
            if heading_text.startswith("3.2 Pipeline 1"):
                paragraph.paragraph_format.page_break_before = True
            first_after_structure = True
            if heading_text.startswith("3.2 Pipeline 1") and not inserted_fig2:
                add_figure(
                    document,
                    FIGURE_2,
                    2,
                    "The locked A1–A5 component diagnostic. The diagram distinguishes "
                    "candidate retrieval from reranking and exposes the top-50 gate.",
                )
                inserted_fig2 = True
            continue

        if block.kind == "paragraph":
            text = str(block.value)
            if pending_abstract:
                paragraph = document.add_paragraph(style="Abstract")
                run = paragraph.add_run("Abstract. ")
                apply_run_font(run, size=9, bold=True)
                add_inline(paragraph, text, size=9)
                pending_abstract = False
                first_after_structure = True
                continue
            if text.startswith("**Keywords:**"):
                paragraph = document.add_paragraph(style="Keywords")
                add_inline(paragraph, text, size=9)
                first_after_structure = True
                continue
            if current_section == "References" and re.match(r"^\d+\.\s", text):
                paragraph = document.add_paragraph(style="Reference")
                add_inline(paragraph, text, size=9)
                continue
            if text.startswith("`") and re.search(r"\(\d+\)$", text):
                cleaned = text.replace("`", "")
                add_equation(document, cleaned)
                first_after_structure = True
                continue
            if text.startswith("**Algorithm 1:"):
                paragraph = document.add_paragraph(style="Table caption")
                add_inline(paragraph, text, size=9)
                first_after_structure = True
                continue
            body_paragraph(document, text, first_after_structure=first_after_structure)
            first_after_structure = False
            continue

        if block.kind == "table":
            table_number += 1
            add_table(document, block.value, table_number)
            first_after_structure = True
            continue

        if block.kind == "bullets":
            add_bullets(document, block.value)
            first_after_structure = True
            continue

        if block.kind == "numbers":
            if current_section == "References":
                for number, item in enumerate(block.value, 1):
                    paragraph = document.add_paragraph(style="Reference")
                    add_inline(paragraph, f"{number}. {item}", size=9)
            else:
                add_numbers(document, block.value)
            first_after_structure = True
            continue

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    document.save(OUTPUT)
    return OUTPUT


if __name__ == "__main__":
    output = build()
    print(output)
