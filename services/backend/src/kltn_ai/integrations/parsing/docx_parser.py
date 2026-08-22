"""
Trích xuất cấu trúc từ file DOCX: tách thành danh sách các elements (heading/paragraph/caption/table),
mỗi elements kèm section_path (chương/mục chứa nó).

Đầu ra dùng chung schema với pdf_parser.py để chunking.py xử lý thống nhất.

Khác với PDF (phải suy luận cấu trúc từ tín hiệu hình ảnh như size/bold/toạ độ),
DOCX lưu sẵn cấu trúc ngữ nghĩa dưới dạng "style" (Heading 1, TOC 1, Caption...)
gắn trực tiếp vào từng đoạn văn, phần lớn logic ở đây là ĐỌC RA đúng style đã
có sẵn, không phải đoán như PDF.
Tuy vậy, DOCX có phát sinh vấn đề riêng: nội dung có thể nằm trong
Content Control (SDT, như ô điền sẵn "Click để nhập tên"),
cần duyệt đệ quy để không bị mất dữ liệu;
và DOCX không lưu số trang thật (dùng para_index thay page).
"""

from docx import Document   #dùng để mở file docx
from docx.table import Table    # dùng để kiểm tra có phải bảng không
from docx.text.paragraph import Paragraph   # dùng để kiểm tra đây có phải đoạn văn không (phân biệt với bảng)
from docx.oxml.ns import qn # dùng cho Content Control (SDT)
import re
import sys
sys.stdout.reconfigure(encoding='utf-8')

# Style Word gán khi chọn "Heading 1/2/3..." trên giao diện
# đọc thẳng để biết đây là heading, không cần đoán qua size/bold như PDF
HEADING_STYLE_RE = re.compile(r"^Heading\s+(\d+)$", re.IGNORECASE)

# Style Word tự gán cho từng dòng trong Mục lục khi dùng tính năng "Insert Table of Contents"
# (vd "TOC 1", "TOC Heading") - dùng để lọc bỏ TOC
TOC_STYLE_RE = re.compile(r"^TOC", re.IGNORECASE)

# Dò theo nội dung chữ (không phải style) - dùng làm lớp kiểm tra dự phòng,
# vì caption đôi khi bị gán sai style (như bị gán nhầm "Heading 4") trong thực tế,
# không thể chỉ tin tưởng vào style
CAPTION_TEXT_RE = re.compile(r"^(Hình|Bảng|Biểu đồ|Sơ đồ|Figure|Table|Chart)\s+\d", re.IGNORECASE)

# Style Word gán khi dùng tính năng "Insert Caption" cho ảnh/bảng
CAPTION_STYLE_RE = re.compile(r"^Caption$", re.IGNORECASE)

# Tiêu đề các section chỉ mang tính điều hướng (Mục lục, Danh mục bảng biểu/hình vẽ)
NAV_SECTION_HEADING_RE = re.compile(
    r"^(MỤC LỤC|DANH MỤC\s+(BẢNG BIỂU|HÌNH VẼ|HÌNH ẢNH|BẢNG|HÌNH)|"
    r"TABLE OF CONTENTS|LIST OF (TABLES|FIGURES))\s*$",
    re.IGNORECASE
)


def iter_block_items(doc):
    """
    Duyệt qua mọi block-level item (paragraph/table) trong body của file docx,
    theo đúng thứ tự xuất hiện trong tài liệu.

    Content Control là 1 loại "ô điền sẵn có định dạng" của Word
    (hay dùng cho ô "Click để nhập tên" trên trang bìa theo template chuẩn của trường).
    API thông thường của python-docx (doc.paragraphs, doc.tables) bỏ qua hoàn toàn nội dung
    nằm trong Content Control - gây mất dữ liệu thật.
    Hàm này khắc phục bằng cách tự duyệt đệ quy xuống tận nội dung bên trong Content Control.
    """
    # hàm con, định nghĩa bên trong hàm cha - chỉ để dùng nội bộ
    def walk(parent_elm):
        for child in parent_elm.iterchildren(): # duyệt qua từng con trực tiếp của parent_elm
            # lấy "tên thẻ" đầy đủ (kèm namespace, dạng "{...}p"): nếu
                # 1. tên thẻ kết thúc bằng "}p" -> đây là <w:p> (đoạn văn)
                # 2. tên thẻ kết thúc bằng "}tbl" -> đây là <w:tbl> (bảng)
                # 3. tên thẻ kết thúc bằng "}sdt" -> đây là Content Control
            tag = child.tag 
            if tag.endswith('}p'):
                yield Paragraph(child, doc)
            elif tag.endswith('}tbl'):
                yield Table(child, doc)
            elif tag.endswith('}sdt'):
                sdt_content = child.find(qn('w:sdtContent'))    # tìm thẻ con <w:sdtContent> bên trong sdt
                if sdt_content is not None:
                    yield from walk(sdt_content)    # đệ quy: gọi lại walk() cho nội dung bên trong sdt
    yield from walk(doc.element.body)   # bắt đầu duyệt từ gốc (body) của toàn bộ tài liệu


def _normalize_text(t):
    """
    Chuẩn hóa 1 chuỗi text:
        thay tab/xuống dòng bằng khoảng trắng thường
        gộp khoảng trắng thừa,
        xóa khoảng trắng đầu/cuối.
    """
    t = t.replace("\t", " ").replace("\n", " ").replace("\r", " ")
    t = re.sub(r"[ ]+", " ", t)
    return t.strip()


def extract_docx_elements(file_path):
    """
    Đọc file DOCX, trả về danh sách elements (heading/paragraph/caption/table),
    mỗi phần tử kèm section_path (chương/mục chứa nó).
    Thứ tự kiểm tra khi phân loại 1 đoạn văn: Kiểm tra caption trước heading.
    Nếu nội dung khớp pattern caption (như "Hình 1.1...", hoặc style "Caption") thì luôn coi là caption,
    bất kể style Word gán cho nó có trùng "Heading N" hay không.
    Vì trên thực tế, caption đôi khi bị gán nhầm style "Heading N"
    (không tự dùng tính năng Insert Caption của Word), nên không thể chỉ tin tưởng style.
    """
    doc = Document(file_path)
    elements = []
    section_path = []
    idx = 0
    skip_nav_section = False
    skip_level = None

    # Chạy vòng lặp để lấy các block Paragraph, Table trong file
    for block in iter_block_items(doc):
        # Xử lý trường hợp block Paragraph
        if isinstance(block, Paragraph):
            # Chuẩn hóa nội dung trong block
            text = _normalize_text(block.text)
            if not text:
                continue

            # Lấy style của block
            style_name = block.style.name if block.style else ""

            # Lọc TOC
            if TOC_STYLE_RE.match(style_name):
                idx += 1
                continue

            # Xét caption và heading
            is_caption = bool(CAPTION_TEXT_RE.match(text)) or bool(CAPTION_STYLE_RE.match(style_name))
            heading_match = None if is_caption else HEADING_STYLE_RE.match(style_name)

            # Xử lý heading, bỏ qua nội dung của nav_section
            # Xây section_path, thêm nội dung vào elements
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

        # Xử lý block Table, cần cải tiến phần bảng có ô merge
        elif isinstance(block, Table):
            # Bỏ qua nội dung nav_section
            if skip_nav_section:
                idx += 1
                continue

            rows_data = []  # Lưu trữ nội dung theo hàng
                            # rows_data là list của list — mỗi hàng là 1 list các ô đã chuẩn hoá

            # Duyệt từng hàng trong bảng
            for row in block.rows:
                cells_text = [_normalize_text(c.text) for c in row.cells]   # Chuẩn hóa nội dung trong ô
                rows_data.append(cells_text)

            elements.append({
                "type": "table", "rows": rows_data,
                "para_index": idx, "section_path": [s[1] for s in section_path]
            })
            
            idx += 1   # chỉ tăng 1 lần cho CẢ bảng, vì cả bảng là 1 element duy nhất
                       # (khác Paragraph — mỗi đoạn văn là 1 element riêng)
    return elements
