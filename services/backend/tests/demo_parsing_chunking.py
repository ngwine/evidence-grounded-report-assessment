"""
demo_parsing_chunking.py

Script DEMO -- chạy thử pipeline Extract -> Chunking trên file PDF/DOCX thật,
in ra kết quả rõ ràng để xem (không phải test tự động kiểu pass/fail).

Khác với test_pdf_docx_parsing.py (kiểm tra Đúng/Sai bằng assert),
file này dùng để trực quan hóa kết quả cho người xem (in ra elements, chunks thật, kèm thống kê tổng quan).

Lệnh chạy: từ thư mục evidence-grounded-report-assessment
python services/backend/tests/demo_parsing_chunking.py
"""
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.kltn_ai.integrations.parsing.pdf_parser import extract_pdf_elements
from src.kltn_ai.integrations.parsing.docx_parser import extract_docx_elements
from src.kltn_ai.integrations.indexing.chunking import chunk_elements

FIXTURES_DIR = Path(__file__).parent / "fixtures"
LOCAL_DATA_DIR = Path(__file__).parent / "local_test_data"
OUTPUT_DIR = Path(__file__).parent / "demo_output"


def _print_summary(label, elements, chunks):
    """In thống kê tổng quan: số lượng, token trung bình, min-max."""
    token_counts = [c["token_count"] for c in chunks]
    print(f"\n{'=' * 60}")
    print(f"  {label}")
    print(f"{'=' * 60}")
    print(f"  Số elements trích xuất được : {len(elements)}")
    print(f"  Số chunks sau khi gom       : {len(chunks)}")
    if token_counts:
        print(f"  Token trung bình / chunk    : {sum(token_counts) / len(token_counts):.1f}")
        print(f"  Token min - max             : {min(token_counts)} - {max(token_counts)}")


def _print_sample_chunks(chunks, n=3):
    """In ra n chunk đầu tiên để xem trực tiếp nội dung thật."""
    print(f"\n  --- {min(n, len(chunks))} chunk đầu tiên ---")
    for c in chunks[:n]:
        print(f"\n  [chunk_id={c['chunk_id']}] type={c['type']}, token_count={c['token_count']}")
        print(f"  section_path: {c['section_path']}")
        preview = c["text"][:150] + ("..." if len(c["text"]) > 150 else "")
        print(f"  text: {preview}")


def _run_demo(label, extract_fn, file_path, output_name):
    if not file_path.exists():
        print(f"\n[Bỏ qua] Không tìm thấy file: {file_path}")
        return

    elements = extract_fn(str(file_path))
    chunks = chunk_elements(elements, max_tokens=400, min_tokens=40)

    _print_summary(label, elements, chunks)
    _print_sample_chunks(chunks)

    OUTPUT_DIR.mkdir(exist_ok=True)
    with open(OUTPUT_DIR / f"{output_name}_elements.json", "w", encoding="utf-8") as f:
        json.dump(elements, f, ensure_ascii=False, indent=2)
    with open(OUTPUT_DIR / f"{output_name}_chunks.json", "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)
    print(f"\n  Đã lưu đầy đủ vào: {OUTPUT_DIR}/{output_name}_elements.json")
    print(f"  Đã lưu đầy đủ vào: {OUTPUT_DIR}/{output_name}_chunks.json")

if __name__ == "__main__":
    _run_demo(
        "PDF - file mẫu (fixtures)",
        extract_pdf_elements,
        FIXTURES_DIR / "sample_thesis.pdf",
        "pdf_fixture",
    )
    _run_demo(
        "DOCX - file mẫu (fixtures)",
        extract_docx_elements,
        FIXTURES_DIR / "sample_thesis.docx",
        "docx_fixture",
    )
