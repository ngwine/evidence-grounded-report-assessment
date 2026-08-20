# Pipeline 1 – Phát hiện và truy xuất nội dung tương đồng

## Tổng quan

Pipeline sử dụng chiến lược **Hybrid Retrieval**, kết hợp tìm kiếm từ vựng và
tìm kiếm ngữ nghĩa ngay từ bước truy xuất ứng viên.

## Luồng xử lý

```
Report Passage
→ BM25 Retrieval + Dense Vector Retrieval
→ Reciprocal Rank Fusion (RRF)
→ Top-K Candidates
→ Cross-Encoder Re-ranking
→ Similarity / Plagiarism Classification
→ Document-level Aggregation
→ Similarity Report
```

## Chi tiết

### BM25 Retrieval
Tìm các đoạn có mức độ trùng khớp từ vựng cao, phù hợp với sao chép gần
nguyên văn.

### Dense Vector Retrieval
Sử dụng embedding để bổ sung khả năng tìm kiếm các đoạn có nội dung gần nhau
về mặt ngữ nghĩa nhưng ít trùng khớp từ vựng.

### Reciprocal Rank Fusion (RRF)
Hợp nhất kết quả từ hai luồng retrieval thành tập ứng viên chung.

### Cross-Encoder Re-ranking
Xếp hạng lại các ứng viên bằng Cross-Encoder hoặc reranker tương đương để tăng
chất lượng xếp hạng trước phân tích chi tiết.

### Similarity Classification
Xác định các dạng tương đồng:
- **Verbatim**: sao chép gần nguyên văn
- **Paraphrase**: diễn giải lại
- **Summary**: tóm tắt
- **None**: không có mức tương đồng đáng kể

### Document-level Aggregation
Tổng hợp kết quả từ cấp đoạn lên cấp tài liệu.

### Similarity Report
Gồm tỷ lệ tương đồng, đoạn nghi vấn, vị trí, loại tương đồng và tài liệu
nguồn để giảng viên kiểm tra.

> **Lưu ý**: Tỷ lệ tương đồng **không** đồng nghĩa với tỷ lệ đạo văn. Hệ thống
> cung cấp bằng chứng và nguồn đối chứng để giảng viên đưa ra kết luận.
