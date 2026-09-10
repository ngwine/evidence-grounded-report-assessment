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

Verification tách hai tầng để không đánh đồng “không tìm thấy bằng chứng” với
“có bằng chứng chứng minh claim sai”:

1. Quan hệ giữa từng claim và evidence:
   - **SUPPORTED**: evidence trực tiếp hỗ trợ claim;
   - **CONTRADICTED**: evidence trực tiếp mâu thuẫn với claim;
   - **INSUFFICIENT**: evidence thiếu, mơ hồ, khác ngữ cảnh hoặc chưa đủ thẩm
     quyền để xác định hỗ trợ hay mâu thuẫn.
2. Kết quả checklist:
   - **MET**: có đủ evidence `SUPPORTED` theo yêu cầu rubric;
   - **UNMET**: evidence đáng tin cậy cho thấy yêu cầu không đạt, bao gồm trường
     hợp claim bị `CONTRADICTED`;
   - **CANNOT_ASSESS**: chỉ có evidence `INSUFFICIENT` hoặc xung đột chưa thể
     phân xử đáng tin cậy.

Mapping mặc định:

| Claim–evidence | Checklist |
|---|---|
| `SUPPORTED` | `MET` |
| `CONTRADICTED` | `UNMET` |
| `INSUFFICIENT` | `CANNOT_ASSESS` |

Trường hợp “báo cáo nói A, tài liệu đối chứng nói B” chỉ được đánh dấu
`CONTRADICTED → UNMET` khi tài liệu đối chứng đã được duyệt cho đúng purpose,
đủ thẩm quyền và A/B nói về cùng đối tượng, thời điểm, đơn vị, dataset và điều
kiện. Nếu chưa xác định được nguồn nào đúng hoặc khác ngữ cảnh thì phải dùng
`INSUFFICIENT → CANNOT_ASSESS`, không tự chọn một phía.

Verifier phải lưu cả evidence span chứa A và B, source/version/locator và lý do
mapping. Claim gồm nhiều ý nên được compiler tách thành checklist nguyên tử;
không dùng trạng thái `PARTIALLY_SUPPORTED` để che một mâu thuẫn trực tiếp.

### Deterministic Decision Rules
Điểm đề xuất được suy ra bằng decision rules định nghĩa trong rubric, **không**
để LLM trực tiếp quyết định điểm.

### Lecturer Review
Giảng viên chấp nhận, chỉnh sửa hoặc loại bỏ nhận xét và điểm đề xuất.

### Feedback Log
Mọi thay đổi của giảng viên được lưu phục vụ phân tích sai số và cải tiến.
