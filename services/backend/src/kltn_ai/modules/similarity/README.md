# Similarity – Phát hiện nội dung tương đồng (Pipeline 1)

Module nghiệp vụ cho **Pipeline 1 – Phát hiện và truy xuất nội dung tương đồng**.

## Trách nhiệm

- Orchestrate luồng kiểm tra tương đồng cho một báo cáo:
  Report passage → Hybrid Retrieval (BM25 + Dense) → RRF → Top-K → Re-ranking
  → Similarity Classification → Document-level Aggregation → Similarity Report.
- Quản lý schema và repository cho kết quả tương đồng:
  đoạn nghi vấn, loại tương đồng (verbatim / paraphrase / summary / none),
  nguồn đối chứng, vị trí và confidence.
- Tổng hợp tỷ lệ tương đồng cấp tài liệu từ kết quả cấp đoạn.
- Cung cấp dữ liệu cho Similarity Report ở frontend.

## Ranh giới

- **Không** chứa logic retrieval/re-ranking/embedding thuần tuý; gọi qua
  `integrations/retrieval` và `integrations/indexing`.
- **Không** tự kết luận đạo văn; chỉ cung cấp bằng chứng để giảng viên phán xét.
- Kết quả tương đồng có thể được module `assessment` sử dụng như evidence bổ sung.

## Cấu trúc dự kiến

```
similarity/
├── schemas.py        # SimilarityResult, SimilarityMatch, SimilarityType enum
├── service.py        # SimilarityService – orchestrate pipeline
├── repository.py     # CRUD similarity results trong MongoDB
└── policy.py         # Ngưỡng, quy tắc aggregation, access control
```
