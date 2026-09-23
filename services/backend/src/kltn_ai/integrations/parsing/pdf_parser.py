"""
Trích xuất cấu trúc từ file PDF: tách thành danh sách các elements (heading/paragraph),
mỗi elements kèm section_path (chương/mục chứa nó).

Đầu ra dùng chung schema với docx_parser.py để chunking.py xử lý thống nhất.

PDF không lưu cấu trúc ngữ nghĩa (chỉ có toạ độ chữ trên trang), nên toàn bộ logic
ở đây là suy luận cấu trúc từ tín hiệu hình ảnh: kích thước font, độ đậm, toạ độ,
khoảng cách dòng, số thứ tự trong text...
"""

import pymupdf as fitz # PyMuPDF — đọc toạ độ glyph trực tiếp, tránh lỗi chèn khoảng trắng sai (kerning)
            # khi extract text
import re   # nhận diện Mục lục (dot leader), số trang La Mã, số thứ tự heading ("1.1", "1.1.1"...)
from collections import Counter

from .text_normalization import (
    build_generation_key,
    build_parser_spec,
    normalize_with_mapping,
    resolve_document_version_id,
    sha256_text,
    stable_block_id,
    stable_element_key,
)

# Dòng kết thúc bằng chữ cái + dấu "-" -> khả năng cao là từ bị ngắt dòng giữa chừng
# do PDF word-wrap (vd: "rep-" ở cuối dòng, "resent" ở dòng sau)
_HYPHEN_END_RE = re.compile(r"[A-Za-zÀ-ỹà-ỹ]-$")

# Tiêu đề các section chỉ mang tính điều hướng (Mục lục, Danh mục bảng biểu/hình vẽ)
NAV_SECTION_HEADING_RE = re.compile(
    r"^(MỤC LỤC|MUC LUC|DANH MỤC\s+(BẢNG BIỂU|HÌNH VẼ|HÌNH ẢNH|BẢNG|HÌNH)|"
    r"DANH MUC\s+(BANG BIEU|HINH VE|HINH ANH|BANG|HINH)|"
    r"TABLE OF CONTENTS|CONTENTS|LIST OF (TABLES|FIGURES))\s*$",
    re.IGNORECASE
)

# Dòng có dạng "tiêu đề....số trang" => dòng mục lục
TOC_LINE_RE = re.compile(r"(?:\.\s?){3,}\s*\d+\s*$")

# Dòng bắt đầu bằng số thứ tự nhiều cấp (bắt buộc ≥1 dấu chấm)
# ví dụ: "1.1", "1.1.1"...
NUMBERED_HEADING_RE = re.compile(r"^(\d+(\.\d+){1,4})\b")

# Dòng bắt đầu bằng nhãn chương, (Chương|Chapter|Phần|Part) + >= 1 space + >= 1 chữ liên tiếp
# ví dụ: "Chương|Chapter|Phần|Part 1: Tổng quan", "CHƯƠNG|CHAPTER|PHẦN|PART 1"
# còn case "Chương 1.5, có thể siết chắc re.compile hoặc quy định heading phải đúng định dạng từ đầu"
CHAPTER_LABEL_RE = re.compile(r"^(Chương|Chapter|Phần|Part)\s+\d+\b", re.IGNORECASE)

# Số trang dạng số La Mã đứng riêng 1 dòng (i, ii, iii...) trong mấy trang đầu
ROMAN_PAGE_RE = re.compile(
    r"^(?=[mdclxvi])m{0,4}(cm|cd|d?c{0,3})(xc|xl|l?x{0,3})(ix|iv|v?i{0,3})$",
    re.IGNORECASE
)

_ROMAN_VALUES = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100, "d": 500, "m": 1000}


# ---------------------------------------------------------------------------
# Hàm phụ
# ---------------------------------------------------------------------------

def _roman_to_int(s):
    """
    Chuyển số La Mã thành số nguyên,
    để lọc thêm các trường hợp đúng cú pháp nhưng vô lý làm số trang
    (vd "mix" đúng cú pháp, có giá trị 1009 — không luận văn nào dài vậy).
    """
    s = s.lower()
    total = 0
    for i, ch in enumerate(s):
        val = _ROMAN_VALUES[ch]
        if i + 1 < len(s) and _ROMAN_VALUES[s[i + 1]] > val:
            total -= val
        else:
            total += val
    return total

def _join_paragraph_lines(lines_text):
    """
    Nối hiều dòng thành 1 đoạn văn hoàn chỉnh.

    Nếu 1 dòng kết thúc bằng '-' do bị ngắt dòng giữa chừng thì nối liền không chèn dấu cách
    và bỏ '-'.

    Các trường hợp còn lại nối có dấu cách.
    """
    result = lines_text[0]
    for t in lines_text[1:]:
        if _HYPHEN_END_RE.search(result) and t[:1].islower():
            result = result[:-1] + t
        else:
            result = result + " " + t
    return result

def _normalize(text):
    """
    Chuẩn hóa 1 chuỗi text: tách ligature (NFKC - PDF hay gộp nhiều chữ cái
    thành 1 ký tự duy nhất, cần tách ngược lại về chữ cái rời để so khớp/tìm kiếm đúng),
    xóa ký tự "vô hình" sót lại từ Word (zero-width space...), gộp khoảng trắng thừa,
    xóa khoảng trắng đầu/cuối.
    """
    return normalize_with_mapping(text).text


def _sort_page_lines_reading_order(lines, page_width):
    """Return deterministic single- or two-column reading order.

    PyMuPDF commonly emits each column as a separate block, but sorting every
    line only by ``y`` interleaves left and right columns.  We enable the
    column-major path only when both sides contain at least two narrow lines;
    full-width lines are kept as separators between column bands.
    """

    if len(lines) < 4 or page_width <= 0:
        return sorted(lines, key=lambda line: (line["y"], line["x"]))

    midpoint = page_width / 2
    narrow = [
        line
        for line in lines
        if (line["bbox"][2] - line["bbox"][0]) <= page_width * 0.62
    ]
    left = [line for line in narrow if line["bbox"][0] < midpoint * 0.8]
    right = [line for line in narrow if line["bbox"][0] > midpoint * 0.9]
    if len(left) < 2 or len(right) < 2:
        return sorted(lines, key=lambda line: (line["y"], line["x"]))

    spanning = [
        line
        for line in lines
        if (line["bbox"][2] - line["bbox"][0]) > page_width * 0.62
    ]
    regular = [line for line in lines if line not in spanning]

    def column_sort(items):
        return sorted(
            items,
            key=lambda line: (
                0 if line["bbox"][0] < midpoint else 1,
                line["y"],
                line["x"],
            ),
        )

    ordered = []
    lower_y = float("-inf")
    for separator in sorted(spanning, key=lambda line: (line["y"], line["x"])):
        band = [line for line in regular if lower_y <= line["y"] < separator["y"]]
        ordered.extend(column_sort(band))
        ordered.append(separator)
        lower_y = separator["y"]
    ordered.extend(column_sort([line for line in regular if line["y"] >= lower_y]))
    return ordered


def _is_header_footer_candidate(line):
    """Limit repetition filtering to page margins, never repeated body text."""

    page_height = line.get("page_height") or 0
    if page_height <= 0:
        return False
    return line["bbox"][1] <= page_height * 0.15 or line["bbox"][3] >= page_height * 0.85


def _combine_pdf_lines(lines, *, dehyphenate=False):
    """Combine extracted PDF lines while preserving raw offsets and boxes."""

    raw_text_parts = []
    fragments = []
    cursor = 0
    for line in lines:
        if raw_text_parts:
            raw_text_parts.append("\n")
            cursor += 1
        raw_line = line["raw_text"]
        start = cursor
        raw_text_parts.append(raw_line)
        cursor += len(raw_line)
        fragments.append({
            "raw_char_start": start,
            "raw_char_end": cursor,
            "page_index": line["page_index"],
            "page_number": line["page"],
            "page_label": line["page_label"],
            "bbox": list(line["bbox"]),
        })

    raw_text = "".join(raw_text_parts)
    normalized = normalize_with_mapping(
        raw_text,
        dehyphenate_line_breaks=dehyphenate,
    )
    boxes = [fragment["bbox"] for fragment in fragments]
    bbox = [
        min(box[0] for box in boxes),
        min(box[1] for box in boxes),
        max(box[2] for box in boxes),
        max(box[3] for box in boxes),
    ]
    return raw_text, normalized, fragments, bbox


def _build_pdf_element(
    *,
    element_type,
    source_lines,
    section_path,
    order,
    document_version_id,
    parser_spec,
    generation_key,
    level=None,
    dehyphenate=False,
):
    raw_text, normalized, fragments, bbox = _combine_pdf_lines(
        source_lines,
        dehyphenate=dehyphenate,
    )
    raw_digest = sha256_text(raw_text)
    source_coordinate = {
        "page_index": source_lines[0]["page_index"],
        "page_label": source_lines[0]["page_label"],
        "bbox": bbox,
        "fragments": fragments,
    }
    block_id = stable_block_id(
        document_version_id=document_version_id,
        source_kind="pdf",
        source_coordinate=source_coordinate,
        raw_text_sha256=raw_digest,
    )
    locator = {
        "locator_version": 1,
        "source_kind": "pdf",
        "coordinate_system": {
            "text": "unicode_code_point",
            "bbox": "pdf_points_top_left",
        },
        "offset_convention": "half_open",
        "page_index": source_lines[0]["page_index"],
        "page_number": source_lines[0]["page"],
        "page_label": source_lines[0]["page_label"],
        "bbox": bbox,
        "section_path": list(section_path),
        "block_id": block_id,
        "raw_char_start": 0,
        "raw_char_end": len(raw_text),
        "fragments": fragments,
    }
    element_key = stable_element_key(
        document_version_id=document_version_id,
        element_type=element_type,
        raw_text_sha256=raw_digest,
        locator=locator,
        level=level,
    )
    element = {
        "schema_version": 2,
        "document_version_id": document_version_id,
        "element_key": element_key,
        "element_id": element_key,
        "order": order,
        "type": element_type,
        "element_type": element_type.upper(),
        "raw_text": raw_text,
        "normalized_text": normalized.text,
        "text": normalized.text,
        "raw_text_sha256": raw_digest,
        "normalized_text_sha256": sha256_text(normalized.text),
        "section_path": list(section_path),
        "structure_path": list(section_path),
        "locator": locator,
        "normalization_map": normalized.normalization_map,
        "parser_spec": dict(parser_spec),
        "generation_key": generation_key,
        # Legacy one-based page alias retained for current chunker/demo code.
        "page": source_lines[0]["page"],
    }
    if level is not None:
        element["level"] = level
    return element

def _looks_like_heading_start(text):
    """
    True nếu dòng bắt đầu bằng Stt hoặc nhãn (Chương|Chapter|Phần|Part).

    Dùng để phân biệt 1 dòng heading có phải điểm bắt đầu của 1 heading mới hay không,
    tránh gộp nhầm 2 heading khác nhau làm 1 khi chúng ở gần nhau.
    """
    t = text.strip()
    return bool(NUMBERED_HEADING_RE.match(t) or CHAPTER_LABEL_RE.match(t))

def _infer_level_from_text(text, fallback_level):
    """
    Suy luận level heading từ STT trong text.
    Nếu text không có số thứ tự, dùng lại cấp độ đã suy luận từ font size (fallback_level).
    Ví dụ: 1.1 => level 2, 1.1.1 => level 3
    """
    m = NUMBERED_HEADING_RE.match(text.strip())
    if m:
        return m.group(1).count(".") + 1
    if CHAPTER_LABEL_RE.match(text.strip()):
        return 1
    return fallback_level

def _strip_page_number(text):
    """
    Bỏ số đứng ở ĐẦU hoặc CUỐI dòng — số trang có thể nằm ở header hoặc
    footer, và trong mỗi trường hợp lại có thể đứng trước hoặc sau text
    thương hiệu/tiêu đề, tuỳ cách trình bày của từng file (vd "GeoBase® 6"
    hay "6 GeoBase®" đều cần nhận ra chung 1 "lõi" là "GeoBase®").
    """
    t = re.sub(r"^\s*\d+[\s\-–]*", "", text)
    t = re.sub(r"[\s\-–]*\d+\s*$", "", t)
    return t.strip()

# ---------------------------------------------------------------------------
# Hàm chính
# ---------------------------------------------------------------------------

# file_path : đường dẫn của file pdf
# line_gap_factor :
# indent_threshold_factor : 1 dòng có bị thụt đầu dòng hay không
# => lề trái phải lệch ít nhất 1.5 lần cỡ chữ so với lề chuẩn mới coi là thụt đầu dòng
# heading_merge_gap_factor : quyết định 2 dòng heading liên tiếp có nên gộp thành 1 heading không

def extract_pdf_elements(file_path, line_gap_factor=2.0, indent_threshold_factor=1.5,
                         heading_merge_gap_factor=3.0, y_tolerance=2.0,
                         document_version_id=None):

    """
    Tham số:
        - line_gap_factor: khoảng cách dòng tối đa (= cỡ chữ * hệ số này)
            => để xét 2 dòng liên tiếp có cùng 1 đoạn văn không.
        - indent_threshold_factor: độ thụt lề tối thiểu (= cỡ chữ * hệ số này)
            => kiểm tra bắt đầu đoạn văn mới bằng thụt đầu dòng
        - heading_merge_gap_factor: khoảng cách tối đa (= cỡ chữ * hệ số này) giữa
            2 dòng heading liên tiếp để xem có gộp thành 1 heading hay không
        - y_tolerance: sai lệch toạ độ y tối đa (điểm PDF, không nhân cỡ chữ) để
            coi 2 span là cùng 1 hàng ngang
    """

    resolved_document_version_id = resolve_document_version_id(
        file_path,
        document_version_id,
    )
    parser_config = {
        "schema_version": 2,
        "line_gap_factor": line_gap_factor,
        "indent_threshold_factor": indent_threshold_factor,
        "heading_merge_gap_factor": heading_merge_gap_factor,
        "y_tolerance": y_tolerance,
        "normalization": "unicode-nfkc-zero-width-whitespace",
        "paragraph_dehyphenation": True,
    }
    parser_spec = build_parser_spec(
        name="pymupdf-layout-parser",
        version="2.0.0",
        config=parser_config,
    )
    generation_key = build_generation_key(
        document_version_id=resolved_document_version_id,
        parser_spec=parser_spec,
    )

    doc = fitz.open(file_path)
    n_pages = len(doc)
    pages_lines = []

    for page_index, page in enumerate(doc):
        try:
            page_label = page.get_label() or str(page_index + 1)
        except (AttributeError, RuntimeError, ValueError):
            page_label = str(page_index + 1)
        # Lấy toàn bộ nội dung của 1 trang dưới dạng cấu trúc "dict"
        # d (dict):
            # "width", "height" => kích thước trang
            # "blocks" (list) => danh sách các khối văn bản trên trang
                # mỗi block có "lines" (list) => các dòng trong khối
                    # mỗi line có "spans" (list) => các đoạn chữ cùng định dạng trong dòng đó
                        # mỗi span có "text", "size", "flags" (đậm/nghiêng), "bbox" (tọa độ)
        d = page.get_text("dict")
        raw_spans = []
        for block_index, block in enumerate(d["blocks"]):
            for line in block.get("lines", []):
                for s in line.get("spans", []):
                    t = s.get("text", "")
                    # bỏ qua span rỗng SAU KHI loại các ký tự "vô hình" thường sót lại
                    # từ Word (zero-width space, zero-width joiner/non-joiner, BOM...)
                    # -- .strip() thường KHÔNG coi các ký tự này là khoảng trắng, nên
                    # phải loại thủ công, nếu không chúng bị nhận nhầm thành heading
                    # khi vô tình mang cỡ chữ lớn.
                    cleaned = re.sub(r"[\u200b\u200c\u200d\u2060\ufeff]", "", t)
                    if not cleaned.strip():
                        continue
                    raw_spans.append({
                        "text": t,
                        "size": s["size"],
                        "bold": bool(s["flags"] & 2**4),
                        "x0": s["bbox"][0],
                        "y": s["bbox"][1],
                        "bbox": tuple(s["bbox"]),
                        "block_index": block_index,
                    })


        # B1: Gom span theo hàng (dựa vào tọa độ y)
        raw_spans.sort(key=lambda s: (s["y"], s["x0"]))
        raw_line_groups = []   # raw_line_group (list): lưu trữ các hàng đã thêm span vào xong
        raw_cur_line = []   # raw_cur_cluster (list): lưu trữ 1 hàng thêm span dang dở
                        # => tạm giữ các span đang nghi ngờ là cùng 1 hàng
        raw_cur_y = None    # raw_cur_y: tọa độ neo
        raw_cur_block = None
                        # => dùng làm mốc so sánh cho span tiếp theo: "span mới này có gần với hàng đang xây không?"

        for s in raw_spans:
            if (
                raw_cur_line
                and s["block_index"] == raw_cur_block
                and abs(s["y"] - raw_cur_y) <= y_tolerance
            ):
                raw_cur_line.append(s)
            else:
                if raw_cur_line:
                    raw_line_groups.append(raw_cur_line)
                raw_cur_line = [s]
                raw_cur_y = s["y"]
                raw_cur_block = s["block_index"]
        if raw_cur_line:
            raw_line_groups.append(raw_cur_line)

        # B2: Trong từng hàng, sắp xếp lại theo x theo chiều từ trái sang phải và lưu các thuộc tính của chúng
        lines = [] # lines (list): lưu các hàng đã hoàn thành
        for line in raw_line_groups:
            line.sort(key=lambda s: s["x0"]) # sắp xếp các span lúc nãy theo x0
            raw_text = ""
            size = 0.0
            bold = False
            for s in line:
                sep = "" if (raw_text == "" or raw_text.endswith((" ", "-"))) else " "
                raw_text = raw_text + sep + s["text"]
                size = max(size, s["size"])
                bold = bold or s["bold"]
            text = _normalize(raw_text)
            if text:
                bbox = (
                    min(span["bbox"][0] for span in line),
                    min(span["bbox"][1] for span in line),
                    max(span["bbox"][2] for span in line),
                    max(span["bbox"][3] for span in line),
                )
                lines.append({
                    "raw_text": raw_text,
                    "text": text,
                    "size": size,
                    "bold": bold,
                    "x": line[0]["x0"],
                    "y": line[0]["y"],
                    "bbox": bbox,
                    "page_index": page_index,
                    "page": page_index + 1,
                    "page_label": page_label,
                    "page_height": d["height"],
                })
        lines = _sort_page_lines_reading_order(lines, d["width"])
        pages_lines.append(lines)

    # Phát hiện Header/Footer
    # tìm các dòng text lặp lại trên phần lớn số trang rồi gán cho repeated_texts.
    # Kết quả sẽ được dùng để lọc bỏ ở bước sau.
    # LƯU Ý: chỉ so khớp CHÍNH XÁC là chưa đủ -- nếu header/footer bị dính liền
    # với số trang trên cùng 1 dòng (do bước gộp cụm theo y ở B1 vô tình gộp
    # luôn số trang vào, ví dụ "GeoBase® 6", "GeoBase® 7"...), mỗi trang sẽ ra
    # 1 chuỗi khác nhau (số trang khác nhau) nên không khớp được theo cách so
    # sánh y hệt. Cần thêm 1 lớp so khớp phụ: bỏ số trang ở đầu/cuối dòng rồi
    # so lại theo "lõi" chung (dùng _strip_page_number).
    text_positions = {}
    normalized_positions = {}
    # page_index: số trang của trang đó (bắt đầu từ 0)
    # lines: các dòng trong trang đó
    for page_index, lines in enumerate(pages_lines):
        for line in lines:
            if not _is_header_footer_candidate(line):
                continue
            # text_positions = {'National Hydro Network, Data Model � Edition 1.0 2004-06': {2}}
            # text_positions = {'National Hydro Network, Data Model � Edition 1.0 2004-06': {2, 3, ...}}
            text_positions.setdefault(line["text"], set()).add(page_index)
            norm = _strip_page_number(line["text"])
            if norm:
                normalized_positions.setdefault(norm, set()).add(page_index)

    threshold = max(2, int(n_pages * 0.6))
    repeated_texts = {
        t for t, pages_seen in text_positions.items()
        if n_pages > 1 and len(pages_seen) >= threshold
    }
    repeated_normalized = {
        t for t, pages_seen in normalized_positions.items()
        if n_pages > 1 and len(pages_seen) >= threshold
    }

    def is_repeated_header_footer(line):
        if not _is_header_footer_candidate(line):
            return False
        text = line["text"]
        if text in repeated_texts:
            return True
        norm = _strip_page_number(text)
        return bool(norm) and norm in repeated_normalized

    """
    True nếu cả dòng CHỈ LÀ số trang đứng riêng lẻ — dùng để lọc bỏ, không
    coi là nội dung thật. Chấp nhận 2 dạng: số Ả Rập (có thể kèm dấu gạch
    trang trí 2 đầu, vd "1", "- 1 -") hoặc số La Mã hợp lệ có giá trị hợp lý
    cho số trang (≤ max_roman_value, tránh nhận nhầm từ như "mix" = 1009).
    """
    def is_page_number_line(text, max_roman_value=50):
        t = text.strip()
        if re.fullmatch(r"[\-–]?\s*\d+\s*[\-–]?", t):
            return True
        if ROMAN_PAGE_RE.fullmatch(t) and _roman_to_int(t) <= max_roman_value:
            return True
        return False

    size_counter = Counter()    # tìm cỡ chữ xuất hiện nhiều nhất
                                # => thường Paragraph chiếm nhiều nhất trong file
                                # => body_size => để phát hiện các heading
    x_counter = Counter()   # tìm tạo độ x xuất hiện nhiều nhất => tọa độ x đó là lề trái
                            # => body_left_x => để phát hiện indent
    for lines in pages_lines:
        for line in lines:
            if not is_repeated_header_footer(line) and not is_page_number_line(line["text"]):
                size_counter[line["size"]] += 1
                x_counter[round(line["x"])] += 1
    body_size = size_counter.most_common(1)[0][0] if size_counter else 13.0
    body_left_x = x_counter.most_common(1)[0][0] if x_counter else 0
    body_left_candidates = [
        x
        for x, count in x_counter.most_common(4)
        if count >= 2
    ] or [body_left_x]

    def classify(size, bold):
        """
        Hàm quyết định xem dòng đó là heading hay là paragraph
        Tham số:
        - size: kích cỡ của line
        - bold: boolean
        Trả về 1 tuple gồm 2 giá trị (type, level)
        """
        if size >= body_size * 1.4:
            return "heading", 1
        elif size >= body_size * 1.15:
            return "heading", 2
        return "paragraph", None

    def is_indented(x):
        """
        Xét xem một dòng có đang thụt lùi đầu dòng hay không
        """
        nearest_margin = min(body_left_candidates, key=lambda margin: abs(x - margin))
        return abs(x - nearest_margin) >= body_size * indent_threshold_factor

    # Lọc rác (header/footer, số trang, nội dung trong mục lục) + phân loại heading/paragraph
    clean_lines = []
    for lines in pages_lines:
        for line in lines:
            text = line["text"]

            # Nếu text này có trong set repeated_texts hoặc text là số trang thì bỏ qua, không phân loại heading
            if not text or is_repeated_header_footer(line) or is_page_number_line(text):
                continue

            # Nếu text là nội dung trong mục lục thì bỏ qua, không phân loại heading
            if TOC_LINE_RE.search(text):
                continue

            # etype = heading/paragraph/caption, level = số cấp của heading/None
            # do đoạn này mình có xét đoạn văn có phải là heading hay không rồi => gán etype là heading luôn
            if _looks_like_heading_start(text):
                etype, level = "heading", _infer_level_from_text(text, 1)
                # print(f"_looks_like_heading_start: {text, etype, level}")
            else:
                etype, level = classify(line["size"], line["bold"])
                # print(f"not_looks_like_heading_start: {text, etype, level}")
            clean_lines.append({
                "page_index": line["page_index"],
                "page": line["page"],
                "page_label": line["page_label"],
                "y": line["y"],
                "x": line["x"],
                "size": line["size"],
                "bbox": line["bbox"],
                "raw_text": line["raw_text"],
                "text": text,
                "type": etype,
                "level": level,
                "source_lines": [line],
            })

    # Gộp các dòng heading liên tiếp (không có paragraph xen giữa) thành 1
    # heading hoàn chỉnh, dừng lại khi gặp dòng tự bắt đầu 1 heading mới
    # vd:
    # Chapter 1
    # Introduction
    merged_lines = []
    i = 0
    while i < len(clean_lines):
        line = clean_lines[i]
        if line["type"] != "heading":
            merged_lines.append(line)
            i += 1
            continue
        cur_heading = [line] # cur_heading roup (list): tạm giữ các dòng heading nghi ngờ cùng 1 heading
        j = i + 1
        while j < len(clean_lines):
            nxt_line = clean_lines[j]

            # so sánh trang của dòng đang xét (nxt_line) với trang của phần tử mới nhất vừa được gộp vào cur_heading
            same_page = nxt_line["page"] == cur_heading[-1]["page"]

            # nếu same_page đúng, gap = khoảng cách y giữa 2 dòng;
            # nếu sai, gap = None (không tính được, vì khác trang thì so y không có ý nghĩa gì)"
            gap = nxt_line["y"] - cur_heading[-1]["y"] if same_page else None

            # lấy cỡ chữ lớn hơn trong 2 dòng đang so sánh
            # mối quan hệ giữa "cỡ chữ" và "khoảng cách dòng hợp lý" là quan hệ tỉ lệ thuận (chữ to gấp đôi => khoảng cách hợp lý cũng gấp đôi theo)
            # vd:
            # Chapter 1 (size 16pt)
            # Introduction (size 16pt)
            # khoảng cách dòng = cỡ chữ * (hệ số dòng đơn của font * n)
                # hệ số dòng đơn thường [1.15-1.3]
                # n là cách giãn dòng:
                    # giãn dòng đơn (hệ số dòng đơn * 1), giãn 1.5 (hệ số dòng đơn * 1.5), giãn dòng đôi (hệ số dòng đơn * 2.0)
            # ngưỡng cao nhất có thể là 1.3 * 2 = 2.6 => lấy hệ số "heading_merge_gap_factor" = 3.0
            max_gap = max(cur_heading[-1]["size"], nxt_line["size"]) * heading_merge_gap_factor

            # nếu cùng trang, khoảng cách không âm (dòng sau phải nằm dưới dòng trước, đúng thứ tự đọc)
            # và không vượt quá ngưỡng cho phép
            gap_ok = same_page and gap is not None and 0 <= gap <= max_gap

            if (nxt_line["type"] == "heading" and gap_ok and not _looks_like_heading_start(nxt_line["text"])):
                cur_heading.append(nxt_line)
                j += 1
            else:
                break

        source_lines = [
            source_line
            for heading_line in cur_heading
            for source_line in heading_line["source_lines"]
        ]
        _, merged_normalized, _, merged_bbox = _combine_pdf_lines(source_lines)
        merged_lines.append({
            "page_index": cur_heading[0]["page_index"],
            "page": cur_heading[0]["page"],
            "page_label": cur_heading[0]["page_label"],
            "y": cur_heading[0]["y"],
            "x": cur_heading[0]["x"],
            "size": max(g["size"] for g in cur_heading),
            "bbox": tuple(merged_bbox),
            "raw_text": "\n".join(line["raw_text"] for line in source_lines),
            "text": merged_normalized.text,
            "type": "heading", "level": min(g["level"] for g in cur_heading),
            "source_lines": source_lines,
        })
        i = j

    clean_lines = merged_lines

    # Xây dựng elements cuối cùng:
        # heading cập nhật section_path, paragraph gộp theo đoạn văn hoàn chỉnh,
        # bỏ qua nội dung thuộc section điều hướng NAV_SECTION_HEADING_RE
    elements = []   # kết quả cuối cùng
    section_path = []   # đường dẫn phân cấp ngữ cảnh
    skip_nav_section = False    # dùng để lọc nội dung điều hướng bên trong mục lục, danh mục bảng biểu/hình vẽ
                                # nếu True là đang trong nội dung của mục lục, danh mục bảng biểu/hình vẽ
                                # => bỏ qua nội dung đó => không thêm nó vào elements
    skip_level = None   # lưu level của heading hiện tại
                        # => nếu gặp heading tiếp theo, so sánh
                        # nếu level của heading đó <= skip_level
                        # => skip_nav_section = False
    i = 0
    while i < len(clean_lines):
        line = clean_lines[i]

        # Với mỗi heading gặp được:
            # 1. Cập nhật section_path để dùng cho các nội dung bên trong heading.
            # 2. Ghi heading đó vào elements.
            # 3. Quản lý trạng thái "có đang bỏ qua nav_section hay không".

        # Kiểm tra có phải heading hay không
        if line["type"] == "heading":
            level = _infer_level_from_text(line["text"], line["level"]) # lấy level của heading

            #  Kiểm tra có nên thoát khỏi chế độ skip không
            if skip_nav_section and level <= skip_level:
                skip_nav_section = False

            # Xây section_path
                # 1. giữ lại section_path có level < level hiện tại => heading cùng cấp/sâu hơn bị loại vì đã hết phạm vi
                # 2. thêm heading cha vào section_path
            section_path = [s for s in section_path if s[0] < level]
            section_path.append((level, line["text"]))

            # Thêm heading vào elements. ``section_path`` của heading chỉ chứa
            # các heading cha để giữ tương thích với schema cũ.
            heading_path = [s[1] for s in section_path[:-1]]
            elements.append(_build_pdf_element(
                element_type="heading",
                source_lines=line["source_lines"],
                section_path=heading_path,
                order=len(elements),
                document_version_id=resolved_document_version_id,
                parser_spec=parser_spec,
                generation_key=generation_key,
                level=level,
            ))

            # Xét heading để xem nó có phải nav_section hay không
            # => xuống else sẽ bỏ qua nội dung nav_section
            if NAV_SECTION_HEADING_RE.match(line["text"]):
                skip_nav_section = True
                skip_level = level
            i += 1

        # Nếu không phải là heading
        else:
            # Bỏ qua nội dung của nav_section
            if skip_nav_section:
                i += 1
                continue
            buf = [line]    # buffer (list): lưu trữ các dòng đang nghi ngờ thuộc cùng 1 đoạn văn
                            # => dùng cho việc gộp đoạn văn

            j = i + 1       # con trỏ chạy tiếp từ i+1 => dùng để xem có thể gộp đến dòng nào
            while j < len(clean_lines):
                nxt = clean_lines[j]

                # Xét xem có thể gộp đoạn văn không:
                    # 1. dòng này và dòng trước đó có cùng 1 trang không
                        # (hạn chế: đoạn văn ngắt qua trang sẽ KHÔNG được gộp, tách thành element riêng)
                    # 2. khoảng cách giữa hai dòng có nằm trong ngưỡng cho phép không
                    # 3. dòng này không bị thụt đầu dòng (thường đoạn mới sẽ thụt lùi đầu dòng)
                same_page = nxt["page"] == buf[-1]["page"]
                line_gap = nxt["y"] - buf[-1]["y"] if same_page else None
                normal_gap = buf[-1]["size"] * line_gap_factor
                gap_ok = same_page and line_gap is not None and 0 < line_gap <= normal_gap
                if nxt["type"] == "paragraph" and gap_ok and not is_indented(nxt["x"]):
                    buf.append(nxt)
                    j += 1
                else:
                    break

            # Lưu nguyên văn từng dòng với dấu xuống dòng; normalized_text mới
            # thực hiện nối dòng/dehyphenation và giữ mapping về raw_text.
            source_lines = [
                source_line
                for paragraph_line in buf
                for source_line in paragraph_line["source_lines"]
            ]
            elements.append(_build_pdf_element(
                element_type="paragraph",
                source_lines=source_lines,
                section_path=[s[1] for s in section_path],
                order=len(elements),
                document_version_id=resolved_document_version_id,
                parser_spec=parser_spec,
                generation_key=generation_key,
                dehyphenate=True,
            ))
            i = j
    doc.close()
    return elements
