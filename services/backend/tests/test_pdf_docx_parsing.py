"""
Test tự động cho pipeline Extract -> Chunking (PDF và DOCX).

Dùng file mẫu trong tests/fixtures/cho các test chính
để chạy được ở mọi máy (đồng đội, CI),
không phụ thuộc vào tests/local_test_data/ (bị .gitignore, chỉ tồn tại trên máy người test thủ công).

Riêng test_docx_real_report_smoke() dùng file báo cáo thật - tự động bỏ qua
(skip, không báo lỗi) nếu máy đang chạy không có sẵn file đó.

Lệnh chạy: từ thư mục evidence-grounded-report-assessment
python -m pytest services/backend/tests/test_pdf_docx_parsing.py -v 
"""
import json
from pathlib import Path
import pytest
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.kltn_ai.integrations.parsing.pdf_parser import extract_pdf_elements
from src.kltn_ai.integrations.parsing.docx_parser import extract_docx_elements
from src.kltn_ai.integrations.indexing.chunking import chunk_elements

FIXTURES_DIR = Path(__file__).parent / "fixtures"
LOCAL_DATA_DIR = Path(__file__).parent / "local_test_data"

# Các trường bắt buộc phải có trong MỌI chunk -- thiếu trường nào là lỗi thật
REQUIRED_CHUNK_KEYS = {
    "type", "section_path", "section_paths", "text",
    "text_with_context", "source_refs", "token_count", "chunk_id",
}


def _assert_chunks_valid(chunks, max_tokens):
    """Kiểm tra chung, dùng lại cho cả PDF và DOCX: chunks không rỗng, đủ
    trường, token_count hợp lý, và không có chunk vượt max_tokens DO GỘP
    NHIỀU NGUỒN (bug thật) -- chỉ chấp nhận vượt nếu là 1 đoạn văn dài tự nhiên."""
    assert len(chunks) > 0, "Không sinh ra chunk nào"
    for chunk in chunks:
        missing = REQUIRED_CHUNK_KEYS - chunk.keys()
        assert not missing, f"Chunk thiếu trường {missing}: {chunk}"
        assert chunk["token_count"] > 0, f"token_count không hợp lệ: {chunk}"
        assert chunk["text"].strip(), f"Chunk có text rỗng: {chunk}"
        assert chunk["source_refs"], f"Chunk không có source_refs, không truy vết được: {chunk}"

        if chunk["token_count"] > max_tokens:
            assert len(chunk["source_refs"]) <= 1, (
                f"Chunk vượt max_tokens NHƯNG gộp nhiều nguồn -- nghi là bug "
                f"đếm token/gộp chunk, không phải đoạn văn dài tự nhiên: {chunk}"
            )


def test_pdf_extract_and_chunk_pipeline():
    """Pipeline PDF: extract_pdf_elements() -> chunk_elements() phải chạy
    hết, không lỗi, và sinh ra chunks hợp lệ trên file mẫu an toàn."""
    pdf_path = FIXTURES_DIR / "sample_thesis.pdf"
    elements = extract_pdf_elements(str(pdf_path))
    assert len(elements) > 0, "extract_pdf_elements() không trích được gì từ file mẫu"

    chunks = chunk_elements(elements, max_tokens=400, min_tokens=40)
    _assert_chunks_valid(chunks, max_tokens=400)


def test_docx_extract_and_chunk_pipeline():
    """Pipeline DOCX: extract_docx_elements() -> chunk_elements() phải chạy
    hết, không lỗi, và sinh ra chunks hợp lệ trên file mẫu an toàn."""
    docx_path = FIXTURES_DIR / "sample_thesis.docx"
    elements = extract_docx_elements(str(docx_path))
    assert len(elements) > 0, "extract_docx_elements() không trích được gì từ file mẫu"

    chunks = chunk_elements(elements, max_tokens=400, min_tokens=40)
    _assert_chunks_valid(chunks, max_tokens=400)


@pytest.mark.skipif(
    not (LOCAL_DATA_DIR / "5_52200229_BaoCao.docx").exists(),
    reason="Cần file báo cáo thật trong tests/local_test_data/ (không commit, chỉ có ở máy local)",
)

def test_docx_real_report_smoke():
    """Test bổ sung trên file báo cáo THẬT -- kiểm tra pipeline vẫn chạy ổn
    trên dữ liệu thực tế phức tạp hơn nhiều so với file mẫu. Tự động bỏ qua
    (không báo lỗi) trên máy/CI không có sẵn file này."""
    docx_path = LOCAL_DATA_DIR / "5_52200229_BaoCao.docx"
    elements = extract_docx_elements(str(docx_path))
    chunks = chunk_elements(elements, max_tokens=400, min_tokens=40)
    _assert_chunks_valid(chunks, max_tokens=400)

def test_pdf_real_report_smoke():
    """Test bổ sung trên file PDF lấy từ fixtures/, kiểm tra pipeline vẫn
    chạy ổn trên dữ liệu phức tạp hơn nhiều so với file mẫu tự tạo. Không
    cần skipif vì file luôn có sẵn (đã commit vào fixtures/, không phải
    local_test_data/)."""
    pdf_path = FIXTURES_DIR / "Report.pdf"
    elements = extract_pdf_elements(str(pdf_path))
    chunks = chunk_elements(elements, max_tokens=400, min_tokens=40)
    _assert_chunks_valid(chunks, max_tokens=400)