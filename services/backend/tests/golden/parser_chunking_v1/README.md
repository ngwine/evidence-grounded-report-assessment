# Parser/Chunker Golden v1

Hai fixture trong manifest là dữ liệu synthetic, không chứa báo cáo thật hoặc
PII. `manifest.json` khóa checksum file và expected output đã review.

Chạy acceptance test:

```bash
./.venv/bin/python -m pytest \
  services/backend/tests/test_parser_golden_benchmark.py -q
```

Chạy benchmark lặp:

```bash
./.venv/bin/python services/backend/tests/benchmark_parser_chunking.py \
  --runs 20 --output /tmp/parser-chunker-golden-v1.json
```

Script không tự sửa expected output. Khi parser/chunker thay đổi làm snapshot
khác, reviewer phải kiểm tra element, locator, span và mapping rồi mới cập nhật
`output_sha256` hoặc các expectation liên quan. Không “regenerate cho test pass”.

Các case Unicode, duplicate locator, long paragraph/table, repeated body text
và two-column PDF nằm trong regression suite vì chúng cần fixture tạo động có
expected assertion trực tiếp. Báo cáo thật chỉ được thêm sau khi quyền sử dụng,
ẩn danh, retention và approver đã được ghi trong dataset manifest.
