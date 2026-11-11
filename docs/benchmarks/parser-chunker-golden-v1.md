# Kết quả golden benchmark parser/chunker v1

## Cấu hình chạy

| Thuộc tính | Giá trị |
|---|---|
| Ngày chạy | 23/09/2026 |
| Benchmark | `parser-chunker-golden-v1` |
| Số lần lặp | 20 lần/fixture |
| Chunk config | `max_tokens=400`, `min_tokens=40` |
| Máy | Apple arm64, macOS 15.7.9 |
| Python | 3.14.3 |
| PyMuPDF | 1.28.2 |
| python-docx | 1.2.0 |
| Fixture | PDF/DOCX synthetic, checksum khóa trong golden manifest |

Lệnh chạy:

```bash
./.venv/bin/python services/backend/tests/benchmark_parser_chunking.py \
  --runs 20 --output /tmp/parser-chunker-golden-v1.json
```

## Kết quả

| Fixture | Elements | Chunks | Coverage normalized span | Determinism | p50 | p95 | Peak memory cao nhất |
|---|---:|---:|---:|---:|---:|---:|---:|
| Synthetic PDF | 8 | 3 | 443/443 (100%) | 20/20 cùng digest | 11.72 ms | 13.37 ms | 1.13 MiB |
| Synthetic DOCX | 11 | 5 | 512/512 (100%) | 20/20 cùng digest | 22.32 ms | 26.67 ms | 2.34 MiB |

Golden output digest:

- PDF: `9aa94c314b9bbf3027291dfcfeaa2941ae3f2f1f702dc9ae560da56d46a559a2`;
- DOCX: `174b250be750abc8e358eba63e6ee3962d797066bc9c5d1142cf630352a5b807`.

Benchmark kiểm tra checksum trước khi parse, so element/chunk count, loại
element/chunk, heading, page index, maximum token count, full JSON digest và
100% normalized-span coverage. Chỉ cần một raw/normalized span bị hở, chồng,
vượt biên hoặc output thay đổi giữa các lần chạy thì benchmark fail.

## Regression đi kèm

Tại thời điểm tạo benchmark, test backend đạt `17 passed, 1 skipped`. Sau khi
tích hợp thêm app/upload contract tests ngày 19/10/2026, toàn bộ backend suite
đạt `26 passed, 1 skipped`; benchmark golden vẫn pass. Các case ngoài hai
binary fixture gồm:

- NFKC ligature, zero-width character và whitespace mapping;
- duplicate text ở locator khác nhau;
- stable key không phụ thuộc display order;
- split paragraph, table và một row dài;
- PDF page/bbox/line fragment;
- repeated body text không bị xóa nhầm như header/footer;
- reading order PDF hai cột;
- legacy element fail-safe và mixed document version fail-closed.

Test bị skip là smoke test dùng báo cáo thật trong `local_test_data`; file này
không được commit và không được xem là evidence benchmark khi chưa có hồ sơ
quyền dữ liệu.

## Kết luận và giới hạn

Golden pilot đủ để khóa behavior provenance v2 trên fixture an toàn: output ổn
định, source span phủ toàn bộ content element và long element không vượt ngưỡng
estimator. Kết quả latency chỉ mô tả hai fixture nhỏ trên máy ghi ở trên, không
được dùng để suy rộng hiệu năng trên báo cáo dài.

Chưa thể gọi `W4.6` là benchmark chất lượng parser cuối cùng cho corpus thực tế.
Bước còn lại là thêm tập báo cáo đã được duyệt quyền/ẩn danh, phân tầng layout
và lỗi, rồi báo coverage/error/latency theo từng nhóm. OCR, bảng PDF phức tạp,
công thức, figure và layout hơn hai cột vẫn là limitation công khai.
