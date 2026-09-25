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

Ground truth end-to-end bắt buộc là dữ liệu trong miền: report version + rubric
version + checklist nguyên tử, nhãn MET/UNMET/CANNOT_ASSESS, quan hệ
SUPPORTED/CONTRADICTED/INSUFFICIENT và exact evidence span. Mọi report thật chỉ
được xử lý sau consent/authority, anonymization, retention và approver gate.

MMDocIR, HoVer và HARMOGEN-R chỉ kiểm thử thành phần tương ứng long-document
retrieval, multi-hop verification và rubric-grading/agreement; không dataset nào
trong ba nguồn này được dùng thay kết quả end-to-end report–rubric trong miền.

Xem `research/datasets/assessment/`.
