"""
Nhận danh sách "elements" (đã trích xuất từ pdf_parser.py hoặc docx_parser.py),
gom nhóm lại thành "chunks" - các khối văn bản có kích thước phù hợp để đưa vào
lập chỉ mục BM25 và tạo embedding (Dense Vector) ở bước indexing/ tiếp theo.

Vấn đề cốt lõi cần giải quyết: model embedding và BM25 đều có giới hạn về độ dài
văn bản đầu vào hợp lý (quá dài sẽ giảm chất lượng biểu diễn ngữ nghĩa, quá ngắn
lại thiếu ngữ cảnh) - nên không thể đánh index trực tiếp trên từng "element" thô
(1 heading, 1 paragraph riêng lẻ) hay trên toàn bộ tài liệu cùng lúc.
Module này đứng giữa 2 thái cực đó: gom các đoạn văn liên tiếp thuộc cùng 1 section
thành 1 chunk có kích thước hợp lý (giới hạn bởi max_tokens/min_tokens),
đồng thời giữ lại thông tin section_path để không mất ngữ cảnh
khi chunk được truy xuất riêng lẻ.
"""

import re

def approx_token_count(text):
    """
    Ước lượng số lượng token của 1 đoạn text
    (không tính chính xác tuyệt đối, mà tính gần đúng qua công thức đơn giản,
    sau khi chọn được SLM sẽ dùng tokenizer của model)
    """
    words = len(text.split())
    return max(1, int(words * 1.3))

def _format_table_text(rows):
    """
    Chuyển 1 bảng dạng danh sách lồng nhau thành một đoạn text thuần.
    """
    lines = []
    for row in rows:
        cells = [c for c in row if c]   # Lọc bỏ ô rỗng trong hàng
        if not cells:
            continue

        # Nếu có 2 cột thì lưu kiểu (key, value)
        # Nếu không (> 2 cột) thì nối toàn bộ các ô trong row thành 1 chuỗi, xen giữa mỗi ô là dấu " - "
        if len(row) == 2:
            lines.append(f"{row[0]}: {row[1]}")
        else:
            lines.append(" - ".join(row))        
    return "\n".join(lines) # Chuỗi string, nội dung giữa các hàng được ngăn cách bởi \n


def _breadcrumb(section_path):
    """
    Tạo chuỗi hiển thị dạng đường dẫn (breadcumb) từ section_path
    Ví dụ: ["Chương 1 Tổng quan", "1.1 Mô tả"] thì output là "Chương 1 Tổng quan > 1.1 Mô tả"
    """
    return " > ".join(section_path) if section_path else ""


def chunk_elements(elements, max_tokens=400, min_tokens=40):
    """
    Nhận elements từ pdf_parser và docx_parser để gom thành chunks
    (các khối văn bản có kích thước phù hợp để đưa vào BM25/embedding).

    Quy tắc gom nhóm:
    1. Gom các đoạn văn/caption liên tiếp cùng section_path vào 1 chunk;
    cắt tiếp nếu vượt max_tokens, luôn cắt tại ranh giới đoạn văn.

    2. Bảng luôn tách thành 1 chunk riêng, không gộp chung với đoạn văn,
    chuyển từ dạng danh sách lồng từ elements sang text thuần thông qua _format_table_text
    
    3. Sau khi có chunks thô, chunk nào quá nhỏ (< min_tokens)
    sẽ được gộp chung vào chunk liền trước, nếu cùng thuộc 1 chương lớn (section_path cấp cao nhất giống nhau)
    và tổng kích thước sau khi gộp vẫn không vượt max_tokens.
    
    4. Mỗi chunk lưu section_path (section sâu nhất, dùng làm breadcrumb hiển thị)
    lẫn section_paths (danh sách đầy đủ mọi section đã góp
    phần vào chunk đó, kể cả sau khi gộp) - để không mất thông tin
    nguồn gốc khi 1 chunk được gộp từ nhiều section khác nhau.
    """

    raw_chunks = [] # chứa các chunk đã cắt đúng max_tokens,
                    # nhưng chưa qua bước gộp chunk quá nhỏ

    def flush_buffer(buf_texts, section_path, source_refs):
        """
        Nhận toàn bộ đoạn văn đã tích lũy (cùng thuộc 1 section_path),
        cắt thành 1 hoặc nhiều chunks (nếu tổng độ dài > max_tokens),
        rồi thêm vào raw_chunks.
        Các bước:
        1. Nếu buf_texts rỗng, return
        2. Gom các đoạn văn vào 1 cụm đang xây (cur), mỗi cụm không được phép vượt quá max_tokens,
        nếu thêm đoạn tiếp theo mà khiến cur vượt ngưỡng thì thêm cụm hiện tại vào pieces,
        tiếp tục xây cụm mới.
        3. Sau vòng lặp, cụm cuối đang xây dang đc được thêm vào pieces
        (kiểu không có đoạn tiếp theo để xét max_tokens)
        4. Chạy vòng lặp trong pieces, nối các đoạn văn thành 1 chuỗi hoàn chỉnh,
        đóng gói thành 1 dict chunk và thêm vào raw_chunks
        """
        if not buf_texts:
            return
        # pieces: kết quả cuối cùng trong hàm này, dùng để tạo thành 1 chunk hoàn chỉnh ở bước sau
        # cur: cụm text đang xây, dùng để tích lũy các đoạn văn cho tới khi vượt max_tokens thì thêm vào pieces
        # cur_refs: danh sách vị trí gốc (para_index/page) song song với cur, là nguồn gốc của đúng phần tử cùng vị trí trong cur
        pieces, cur, cur_refs = [], [], []
        for t, ref in zip(buf_texts, source_refs):
            # Tích lũy token của các đoạn văn
            trial = cur + [t]
            trial_tokens = approx_token_count(" ".join(trial))

            # Xét cụm đang xây có vượt ngưỡng max_tokens không
            # => Vượt ngưỡng thì chốt cụm đó, gán lại []
            # => Chưa vượt thì xây tiếp cụm hiện tại
            if cur and trial_tokens > max_tokens:
                pieces.append((cur, cur_refs))
                cur, cur_refs = [], []

            # Xây cụm
            cur.append(t)
            cur_refs.append(ref)
        # Cụm cuối cùng
        if cur:
            pieces.append((cur, cur_refs))
        # Chạy vòng lặp để thêm các cụm đã xây vào raw_chunks, dùng cho các bước xử lý tiếp theo
        for texts, refs in pieces:
            joined = " ".join(texts)
            raw_chunks.append({
                "type": "text",
                "section_path": list(section_path),
                "section_paths": [list(section_path)],
                "text": joined,
                "text_with_context": (f"[{_breadcrumb(section_path)}] " if section_path else "") + joined,
                "source_refs": refs,
                "token_count": approx_token_count(joined),
            })

    # buf_texts: gom nội dung text của các đoạn văn/caption liên tiếp, miễn là chúng cùng section_path
    # buf_section: ghi nhớ section_path hiện tại đang gom, ùng để phát hiện khi nào chuyển sang section khác
    # buf_refs: song song với buf_texts, giữ vị trí gốc (para_index/page)
    buf_texts, buf_section, buf_refs = [], None, []

    def ref_of(el):
        """
        Lấy "vị trí gốc" của 1 element - trả về para_index nếu có (element từ DOCX),
        nếu không có thì lấy page thay thế (element từ PDF).
        Nhờ vậy chunking.py không cần biết element đến từ PDF hay DOCX, luôn dùng
        ref_of() để lấy đúng vị trí tương ứng.
        """
        return el.get("para_index", el.get("page"))

    for el in elements:
        # Bỏ qua Heading 
        # heading chỉ có tác dụng cung cấp ngữ cảnh cho các đoạn văn phía sau nó
        if el["type"] == "heading":
            continue

        # Nhánh paragraph/caption/reference — phát hiện đổi section
        if el["type"] in ("paragraph", "caption", "reference"):
            sp = tuple(el["section_path"])
            # So sánh section của element hiện tại với section đang gom
            # => Nếu khác nhau => section đã đổi => buffer cũ phải được chốt (đi lên hàm flush_buffer để xây cụm, xét tokens các thứ) => buf_section đi gom section mới
            if buf_section is not None and sp != buf_section:
                flush_buffer(buf_texts, buf_section, buf_refs)
                buf_texts, buf_refs = [], []
            buf_section = sp
            buf_texts.append(el["text"])
            buf_refs.append(ref_of(el))

        # Nhánh table
        # tách riêng để đảm bảo bảng không bao giờ bị trộn lẫn vào cùng 1 chunk với đoạn văn xung quanh nó
        # cần xem xét nếu bảng có lượng tokens quá lớn
        elif el["type"] == "table":
            # Xét trước để đảm bảo không gộp nội dung bảng với nội dung khác
            if buf_texts:
                flush_buffer(buf_texts, buf_section, buf_refs)
                buf_texts, buf_refs = [], []
            table_text = _format_table_text(el["rows"])
            sp = el["section_path"]

            # Thêm nội dung bảng vào raw_chunks
            raw_chunks.append({
                "type": "table",
                "section_path": list(sp),
                "section_paths": [list(sp)],
                "text": table_text,
                "text_with_context": (f"[{_breadcrumb(sp)}] " if sp else "") + table_text,
                "source_refs": [ref_of(el)],    # list chỉ có 1 phần tử
                                                # vì bảng không bao giờ được gộp với gì khác
                "token_count": approx_token_count(table_text),
            })

    if buf_texts:
        flush_buffer(buf_texts, buf_section, buf_refs)

    merged = []
    for ch in raw_chunks:
        # Xét điều kiện để 1 chunk được gộp vào chunk trước
        # => Thỏa điều kiện thì thử nối text và tính token trước

        if (
                merged                                # 1. đã có chunk trước đó được gộp vào rồi        
                and ch["type"] == "text"              # 2. chunk hiện tại phải là text
                and merged[-1]["type"] == "text"      # 3. chunk trước đó cũng phải là text
                and ch["token_count"] < min_tokens    # 4. chunk hiện tại quá nhỏ
                and merged[-1]["section_path"][:1] == ch["section_path"][:1]    # 5. cùng chương lớn nhất
            ):
            prev = merged[-1]
            trial_text = prev["text"] + " " + ch["text"]
            trial_tokens = approx_token_count(trial_text)

            # Không vượt ngưỡng max_tokens => gộp chunk hiện tại vào chunk trước đó
            if trial_tokens <= max_tokens:
                prev["text"] = trial_text   # chunk trước đó = đoạn nối chunk trước đó + chunk hiện tại
                prev["text_with_context"] = prev["text_with_context"] + " " + ch["text"]    # nối thêm text của chunk hiện tại vào, vì context 2 đoạn giống nhau gần như giống nhau
                                                                                            # Thêm ngữ cảnh giúp model hiểu chunk đang nói về chủ đề gì, đặc biệt quan trọng với chunk NGẮN như "Câu ngắn." — tự nó gần như vô nghĩa, nhưng thêm breadcrumb vào giúp vector tạo ra có ý nghĩa hơn hẳn
                prev["source_refs"] += ch["source_refs"]
                prev["token_count"] = trial_tokens
                # Cập nhật section_paths (thêm nếu chưa có)
                if ch["section_path"] not in prev["section_paths"]:
                    prev["section_paths"].append(ch["section_path"])
                # Cập nhật section_path (đổi nếu sâu hơn)
                if len(ch["section_path"]) > len(prev["section_path"]):
                    prev["section_path"] = ch["section_path"]
                continue
        merged.append(dict(ch))

    # Đánh stt cho chunk => làm ID cho chunk => sau này dùng
    for i, ch in enumerate(merged):
        ch["chunk_id"] = i

    return merged