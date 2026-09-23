# Indexing – BM25 và Dense Vector indexing

Adapter lập chỉ mục nội dung phục vụ Hybrid Retrieval trong cả hai pipeline.

## Trách nhiệm

- Lập chỉ mục BM25 (lexical) cho tìm kiếm trùng khớp từ vựng.
- Lập chỉ mục Dense Vector (embedding) cho tìm kiếm ngữ nghĩa.
- Hỗ trợ cập nhật chỉ mục khi có tài liệu mới hoặc xoá.
- Chỉ mục là dữ liệu dẫn xuất, có thể dựng lại từ MongoDB source of truth.
- Chunker v2 tạo stable key và `source_spans` để mọi passage trong index có thể
  resolve về raw element; contract nằm tại
  [`docs/architecture/parser-chunker-provenance-v2.md`](../../../../../../docs/architecture/parser-chunker-provenance-v2.md).

## Ranh giới

- Adapter thuần tuý; quyết định dùng index nào nằm ở `integrations/retrieval`
  và `modules/similarity` hoặc `modules/assessment`.
- BM25 có thể dùng Elasticsearch, MongoDB Atlas Search, hoặc in-process.
- Dense Vector có thể dùng MongoDB Atlas Vector Search, FAISS, hoặc tương đương.
  Quyết định engine cụ thể sau benchmark.
