# Worker – Task handlers

Worker xử lý các tác vụ nặng không chạy trong HTTP request. Mỗi task handler
phải có checkpoint, retry, idempotency và ghi nhận kết quả trung gian.

## Task handlers theo pipeline

### Document Processing
- `parse_document` – Bóc tách PDF/DOCX thành cấu trúc chương, mục, đoạn văn.
- `index_document` – Lập chỉ mục BM25 và dense vector sau khi parse xong.

### Pipeline 1 – Similarity
- `run_similarity_check` – Orchestrate toàn bộ Pipeline 1: hybrid retrieval →
  RRF → re-ranking → classification → aggregation → Similarity Report.

### Pipeline 2 – Assessment
- `run_assessment` – Orchestrate toàn bộ Pipeline 2: rubric compile → checklist
  classify → evidence retrieval → verification → rationale → scoring.
- `verify_checklist` – Xác minh một checklist cụ thể (sub-task).
- `generate_rationale` – Sinh evidence-grounded rationale cho checklist.

### Support
- `generate_questions` – Sinh câu hỏi vấn đáp dựa trên vấn đề và evidence.
- `aggregate_report` – Tổng hợp kết quả thành báo cáo hỗ trợ đánh giá.

## Quy tắc

- Worker không có quyền tự công bố điểm hoặc bỏ qua RBAC/evidence policy.
- Mọi kết quả AI phải lưu model, prompt, config version và evidence ID.
- Task dài phải có checkpoint để resume khi lỗi.
