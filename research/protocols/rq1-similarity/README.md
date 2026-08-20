# RQ1 – Phát hiện và truy xuất nội dung tương đồng

## Mô tả

Nghiên cứu kiến trúc phát hiện nội dung tương đồng nhiều tầng, trong đó Hybrid
Retrieval được sử dụng để tăng khả năng tìm kiếm cả trường hợp trùng khớp từ
vựng và tương đồng ngữ nghĩa.

## Các thành phần khảo sát

- BM25 Retrieval
- Dense Vector Retrieval
- Reciprocal Rank Fusion (RRF)
- Semantic Re-ranking (Cross-Encoder)
- Mô hình phân loại dạng tương đồng (verbatim / paraphrase / summary / none)
- Phương pháp tổng hợp similarity từ cấp đoạn lên cấp tài liệu

## Cấu hình so sánh

1. BM25
2. Dense Retrieval
3. BM25 + Dense + RRF
4. BM25 + Dense + RRF + Semantic Re-ranking
5. Pipeline nhiều tầng hoàn chỉnh

## Chỉ số đánh giá

- Recall@K, MRR, nDCG
- Precision, Recall, F1-score
- F1 theo từng loại tương đồng
- Thời gian truy xuất và xử lý

## Dataset

Dataset trong miền gồm các cặp đoạn văn được gán nhãn:
`verbatim`, `paraphrase`, `summary`, `none`.

Xem `research/datasets/similarity/`.
