# ADR-002 — Parser baseline cho PDF/DOCX

| Thuộc tính | Giá trị |
|---|---|
| Trạng thái | Accepted for current baseline; review required for replacement |
| Ngày | 19/10/2026 |
| WBS | `W4.1`, `W4.6`, `G-03` |

## Bối cảnh

Hệ thống cần parser chạy local, giữ page/span và tạo đầu vào deterministic cho
chunking. MVP hiện xử lý PDF có text layer và DOCX. OCR, công thức, figure và
bảng PDF phức tạp không nằm trong baseline này.

## Quyết định

- Dùng **PyMuPDF** cho PDF và **python-docx** cho DOCX.
- Parser sinh normalized elements nhưng giữ raw text, locator và mapping để
  chunk/evidence mở ngược về nguồn.
- Parser failure phải trả lỗi; không tạo artifact giả hay âm thầm bỏ qua file.
- Docling/GROBID chỉ là candidate. Chỉ thay baseline khi benchmark trên corpus
  được duyệt chứng minh lợi ích và regression provenance vẫn đạt.

## Bằng chứng

Golden fixture tổng hợp khóa checksum cho cả PDF và DOCX tại
`services/backend/tests/golden/parser_chunking_v1/manifest.json`. Benchmark kiểm
tra element/chunk count, type, heading, page, output digest, token limit, 100%
normalized-span coverage và determinism qua nhiều lần chạy. Báo cáo hiện tại ở
`docs/benchmarks/parser-chunker-golden-v1.md`.

Các test bổ sung bao phủ raw–normalized mapping, stable ID, long paragraph/table,
header/footer lặp và reading order hai cột. Đây là bằng chứng regression trên
fixture an toàn, không phải accuracy benchmark đại diện cho mọi luận văn.

## Hệ quả và giới hạn

- Ưu điểm: ít phụ thuộc, chạy local trên máy 16 GB, provenance đã có test.
- Giới hạn: PDF scan/OCR, equation, image-only diagram, complex table/layout và
  hơn hai cột chưa có cam kết chất lượng.
- Timeout/resource isolation ở worker và benchmark corpus thực tế đã duyệt
  quyền vẫn còn thiếu; vì vậy `W4.1` chưa thể đóng toàn bộ chỉ bằng ADR này.
