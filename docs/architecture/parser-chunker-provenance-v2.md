# Parser/Chunker Provenance v2

## Mục tiêu

Contract này là đầu ra triển khai của `W4.4.2`. Nó bảo đảm evidence có thể đi
ngược từ chunk về đúng document version, element và raw span; `order` chỉ dùng
hiển thị, không còn bị dùng làm định danh.

## Element schema

Parser PDF và DOCX phát ra element schema version `2` với các nhóm field:

- identity: `document_version_id`, `element_key`, `element_id`, `order`;
- content: `raw_text`, `normalized_text`, hai SHA-256 và alias `text`;
- structure: `type`, `element_type`, `section_path`, `structure_path`;
- provenance: `locator`, `normalization_map`;
- reproducibility: `parser_spec`, `generation_key`.

`document_version_id` do caller truyền vào khi đã có persistence. Prototype
offline mặc định dùng SHA-256 của file, vì vậy cùng file và parser config sinh
cùng identity. `element_key` là SHA-256 canonical từ version, loại element,
raw content hash và locator; field `order` không tham gia identity.

### Locator

- Offset text dùng Unicode code point, zero-based và half-open `[start, end)`.
- PDF lưu `page_index` zero-based, `page_number` one-based, `page_label`, bbox
  theo PDF point và các line fragment cấu thành element.
- DOCX không tự suy diễn số trang; `page_index/page_number` là `null`, locator
  dùng `block_index`, `paragraph_index` hoặc `table_index`.
- `raw_char_start/raw_char_end` trên element luôn trỏ vào `raw_text` của chính
  element đó.

### Raw–normalized mapping

`normalization_map.segments` ánh xạ từng normalized character về raw span.
Mapping ghi algorithm, config hash, coordinate system và độ dài hai phía.
Pipeline normalization hiện gồm NFKC, loại zero-width character, collapse
whitespace, giữ row boundary của table và dehyphenate PDF line wrap có kiểm
soát. Không được lấy offset trên normalized text để gán trực tiếp lên file.

## Chunk schema

Chunk schema version `2` bổ sung:

- `chunk_key` và alias `chunk_id` là stable hash; `order` tách riêng;
- `raw_text`, `normalized_text`, content hash và normalization map;
- `element_ids`/`source_element_ids`;
- `source_spans[]` chứa element-local raw/normalized span, chunk-local span và
  locator gốc;
- `chunker_spec` và `generation_key` khóa config dùng để chunk.

`source_spans[]` là nguồn chuẩn khi chunk gồm nhiều element. Top-level
`locator` chỉ là summary cho filter/hiển thị và không được dùng thay thế span.

## Invariant đã test

1. Cùng file/version/config cho JSON output giống nhau qua nhiều lần chạy.
2. Thay `order` không đổi key; duplicate text khác locator có key khác nhau.
3. Mọi normalized character resolve về raw span hợp lệ.
4. Paragraph, table và một row dài đều bị split; không chunk nào vượt
   `max_tokens` theo estimator đã version hóa.
5. Table không bị trộn với prose.
6. PDF page index là zero-based và DOCX không khai báo page giả.
7. Repeated body text không bị lọc nhầm thành header/footer.
8. PDF hai cột đủ tín hiệu được đọc column-major.
9. Legacy element vẫn chạy, nhưng locator cũ được đánh version `0` và không
   được quảng bá thành page index chính xác.

Lệnh kiểm tra:

```bash
./.venv/bin/python -m pytest services/backend/tests -q
```

## Giới hạn còn lại

- Token count hiện là estimator deterministic; tokenizer thật phải tạo
  chunker version/config mới sau khi model embedding được khóa.
- PDF layout phức tạp hơn hai cột, bảng PDF, scan/OCR, công thức và figure chưa
  được tuyên bố hỗ trợ đầy đủ.
- Bbox PDF ở cấp line/element; highlight tới glyph cần parser version sau.
- DOCX không có page locator đáng tin nếu chưa render bằng một layout engine.
- Schema persistence MongoDB và worker sandbox thuộc `W3.1/W4.1`, không nằm
  trong module thuần offline này.
