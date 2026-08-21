from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
from docx.oxml.ns import qn
import re # nhận diện style TOC/Caption, tiêu đề Mục lục/Danh mục bảng biểu, caption ảnh
import sys
sys.stdout.reconfigure(encoding='utf-8')

HEADING_STYLE_RE = re.compile(r"^Heading\s+(\d+)$", re.IGNORECASE)
TOC_STYLE_RE = re.compile(r"^TOC", re.IGNORECASE)
CAPTION_TEXT_RE = re.compile(r"^(Hình|Bảng|Biểu đồ|Sơ đồ|Figure|Table|Chart)\s+\d", re.IGNORECASE)
CAPTION_STYLE_RE = re.compile(r"^Caption$", re.IGNORECASE)
NAV_SECTION_HEADING_RE = re.compile(
    r"^(MỤC LỤC|DANH MỤC\s+(BẢNG BIỂU|HÌNH VẼ|HÌNH ẢNH|BẢNG|HÌNH)|"
    r"TABLE OF CONTENTS|LIST OF (TABLES|FIGURES))\s*$",
    re.IGNORECASE
)

def iter_block_items(doc):
    def walk(parent_elm):
        for child in parent_elm.iterchildren():
            tag = child.tag
            if tag.endswith('}p'):
                yield Paragraph(child, doc)
            elif tag.endswith('}tbl'):
                yield Table(child, doc)
            elif tag.endswith('}sdt'):
                sdt_content = child.find(qn('w:sdtContent'))
                if sdt_content is not None:
                    yield from walk(sdt_content)
    yield from walk(doc.element.body)


def _normalize_text(t):
    t = t.replace("\t", " ").replace("\n", " ").replace("\r", " ")
    t = re.sub(r"[ ]+", " ", t)
    return t.strip()


def extract_docx_elements(file_path):
    """
    v6 — SỬA REGRESSION: v5 vô tình check style heading TRƯỚC check caption, làm
    caption bị gán nhầm style "Heading N" (như bug gốc) quay lại thành heading một
    lần nữa. Đưa is_caption về đúng vị trí ƯU TIÊN CAO NHẤT như v3/v4: nếu khớp
    pattern caption ("Hình 1.1 ...", style "Caption"...) thì LUÔN là caption, bất
    kể style_name có trùng "Heading N" hay không — chỉ khi KHÔNG phải caption mới
    xét tiếp có phải heading hay không.
    """
    doc = Document(file_path)
    elements = []
    section_path = []
    idx = 0
    skip_nav_section = False
    skip_level = None

    for block in iter_block_items(doc):
        if isinstance(block, Paragraph):
            text = _normalize_text(block.text)
            if not text:
                continue
            style_name = block.style.name if block.style else ""

            if TOC_STYLE_RE.match(style_name):
                idx += 1
                continue

            is_caption = bool(CAPTION_TEXT_RE.match(text)) or bool(CAPTION_STYLE_RE.match(style_name))
            heading_match = None if is_caption else HEADING_STYLE_RE.match(style_name)

            if heading_match:
                level = int(heading_match.group(1))
                if skip_nav_section and level <= skip_level:
                    skip_nav_section = False

                section_path = [s for s in section_path if s[0] < level]
                section_path.append((level, text))
                elements.append({
                    "type": "heading", "level": level, "text": text,
                    "para_index": idx, "section_path": [s[1] for s in section_path[:-1]]
                })

                if NAV_SECTION_HEADING_RE.match(text):
                    skip_nav_section = True
                    skip_level = level
                idx += 1
                continue

            if skip_nav_section:
                idx += 1
                continue

            if is_caption:
                elements.append({
                    "type": "caption", "text": text,
                    "para_index": idx, "section_path": [s[1] for s in section_path]
                })
            else:
                elements.append({
                    "type": "paragraph", "text": text,
                    "para_index": idx, "section_path": [s[1] for s in section_path]
                })
            idx += 1

        elif isinstance(block, Table):
            if skip_nav_section:
                idx += 1
                continue
            rows_data = []
            for row in block.rows:
                cells_text = [_normalize_text(c.text) for c in row.cells]
                rows_data.append(cells_text)
            elements.append({
                "type": "table", "rows": rows_data,
                "para_index": idx, "section_path": [s[1] for s in section_path]
            })
            idx += 1
    return elements
