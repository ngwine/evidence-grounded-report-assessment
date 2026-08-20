# Graph – Evidence Graph adapter

Adapter cho **Evidence Graph** phục vụ Graph-based Evidence Retrieval trong
Pipeline 2 (checklist loại GRAPH).

## Trách nhiệm

- Biểu diễn claim, concept, entity và relation từ báo cáo dưới dạng đồ thị.
- Hỗ trợ graph-based retrieval theo hướng HippoRAG-style để truy xuất bằng
  chứng có quan hệ nhiều bước.
- Các dạng quan hệ cần biểu diễn:
  - Mục tiêu ↔ Kết quả
  - Phương pháp ↔ Thực nghiệm
  - Kết luận ↔ Dữ liệu hỗ trợ
  - Claim ↔ Evidence
  - Concept ↔ Reference

## Ranh giới

- Adapter thuần tuý; business logic nằm ở `modules/assessment`.
- Có thể dùng MongoDB, Neo4j hoặc in-memory graph tuỳ benchmark.
  Quyết định engine cụ thể sau prototype.
