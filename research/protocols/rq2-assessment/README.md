# RQ2 – Đánh giá báo cáo dựa trên bằng chứng và quan hệ tri thức

## Mô tả

Nghiên cứu phương pháp chuyển rubric thành các checklist có thể kiểm chứng và
lựa chọn chiến lược truy xuất evidence phù hợp với từng loại checklist.

## Chiến lược retrieval khảo sát

- **Local Evidence Retrieval**: Hybrid Retrieval + reranker cho bằng chứng cục bộ.
- **Graph-based Evidence Retrieval**: đồ thị biểu diễn claim, concept, entity và
  relation để truy xuất bằng chứng nhiều bước (HippoRAG-style).

## Phương pháp nghiên cứu

- Xác minh claim và evidence
- Phát hiện nội dung thiếu bằng chứng
- Phát hiện không nhất quán giữa mục tiêu, phương pháp, kết quả, kết luận
- Xác định checklist: MET / UNMET / CANNOT_ASSESS
- Sinh rationale bám sát evidence
- Suy ra mức đánh giá bằng decision rules của rubric

## Cấu hình so sánh

1. LLM không dùng retrieval (baseline)
2. Local Evidence Retrieval
3. Kết hợp có chọn lọc Local + Graph-based Retrieval

## Chỉ số đánh giá

- Evidence Recall@K, Evidence Precision
- Accuracy MET / UNMET / CANNOT_ASSESS
- Mức phù hợp giữa điểm đề xuất và đánh giá giảng viên
- Tỷ lệ rationale được evidence hỗ trợ
- Tỷ lệ CANNOT_ASSESS nhận biết chính xác

## Dataset

Dataset gồm báo cáo + rubric, checklist gán nhãn MET/UNMET/CANNOT_ASSESS kèm
evidence. Xem `research/datasets/assessment/`.
