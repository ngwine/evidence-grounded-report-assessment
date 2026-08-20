# Pipeline 2 – Phân tích và đánh giá báo cáo dựa trên bằng chứng

## Tổng quan

Pipeline đánh giá bắt đầu bằng **Template-based Rubric Definition** nhằm chuẩn
hóa đầu vào rubric trước khi thực hiện phân tích.

## Luồng xử lý

```
Template-based Rubric Definition
→ Rubric Compiler
→ Checklist Classification: LOCAL / GRAPH
→ Evidence Retrieval
→ Evidence Verification
→ MET / UNMET / CANNOT_ASSESS
→ Evidence-grounded Rationale
→ Deterministic Decision Rules
→ Proposed Score
→ Lecturer Review
→ Feedback Log
```

## Chi tiết

### Rubric Compiler
Rubric được chuẩn hóa theo cấu trúc gồm tiêu chí, checklist, yêu cầu bằng
chứng, mức đánh giá, trọng số và quy tắc quyết định. Compiler chuyển thông tin
này thành các checklist có thể truy xuất và kiểm chứng.

### Checklist Classification
Mỗi checklist được xác định thuộc một trong hai nhóm:
- **LOCAL**: có thể đánh giá dựa trên một hoặc một số đoạn nội dung cụ thể.
- **GRAPH**: cần đối chiếu thông tin và quan hệ giữa nhiều phần của báo cáo
  hoặc nhiều nguồn dữ liệu.

### Evidence Retrieval

**LOCAL checklist**: Hybrid Retrieval kết hợp BM25, embedding và reranker.

**GRAPH checklist**: Evidence Graph biểu diễn claim, concept, entity và quan hệ.
Graph-based retrieval theo hướng HippoRAG-style truy xuất bằng chứng nhiều bước.

Các dạng quan hệ cần kiểm tra:
- Mục tiêu ↔ Kết quả
- Phương pháp ↔ Thực nghiệm
- Kết luận ↔ Dữ liệu hỗ trợ
- Claim ↔ Evidence từ tài liệu đối chứng

### Evidence Verification
Mỗi checklist có một trong ba trạng thái:
- **MET**: có đủ bằng chứng cho thấy yêu cầu được đáp ứng
- **UNMET**: bằng chứng cho thấy yêu cầu chưa được đáp ứng
- **CANNOT_ASSESS**: không đủ bằng chứng để đưa ra đánh giá đáng tin cậy

### Deterministic Decision Rules
Điểm đề xuất được suy ra bằng decision rules định nghĩa trong rubric, **không**
để LLM trực tiếp quyết định điểm.

### Lecturer Review
Giảng viên chấp nhận, chỉnh sửa hoặc loại bỏ nhận xét và điểm đề xuất.

### Feedback Log
Mọi thay đổi của giảng viên được lưu phục vụ phân tích sai số và cải tiến.
