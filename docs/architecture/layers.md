# Kiến trúc phân lớp – Product Layers

Các thành phần sản phẩm được tổ chức theo 4 lớp:

## 1. Document Processing Layer

Xử lý PDF/DOCX, nhận diện cấu trúc, phân đoạn và lập chỉ mục nội dung.

| Thành phần | Trách nhiệm |
|---|---|
| Parser | Bóc tách PDF/DOCX thành cấu trúc chương, mục, đoạn văn, trích dẫn |
| Structure-aware Chunking | Phân đoạn giữ metadata vị trí trong tài liệu gốc |
| Indexing | Lập chỉ mục BM25 (lexical) và Dense Vector (semantic) |

## 2. Similarity Analysis Layer

Phát hiện nội dung tương đồng (Pipeline 1).

| Thành phần | Trách nhiệm |
|---|---|
| Hybrid Retrieval | BM25 + Dense Vector Retrieval |
| RRF | Hợp nhất kết quả hai luồng retrieval |
| Semantic Re-ranking | Cross-Encoder re-ranking |
| Classifier | Phân loại dạng tương đồng (verbatim / paraphrase / summary) |
| Similarity Report | Tổng hợp kết quả cấp tài liệu |

## 3. Evidence-based Assessment Layer

Đánh giá báo cáo dựa trên bằng chứng (Pipeline 2).

| Thành phần | Trách nhiệm |
|---|---|
| Template-based Rubric | Định nghĩa rubric chuẩn hóa |
| Rubric Compiler | Chuyển rubric thành checklist truy xuất được |
| Local Evidence Retrieval | Hybrid Retrieval cho checklist LOCAL |
| Graph Evidence Retrieval | HippoRAG-style cho checklist GRAPH |
| Checklist Verification | Xác minh MET / UNMET / CANNOT_ASSESS |
| Rationale Generator | Sinh evidence-grounded rationale |
| Deterministic Scoring | Decision rules thay vì LLM scoring |

## 4. Lecturer Support Layer

Hỗ trợ giảng viên kiểm tra và tổng hợp kết quả.

| Thành phần | Trách nhiệm |
|---|---|
| Cảnh báo hỗ trợ | AI-generated detection, style anomaly, missing evidence |
| Question Generator | Sinh câu hỏi có mục tiêu từ vấn đề và evidence |
| Lecturer Review | Chấp nhận / chỉnh sửa / loại bỏ kết quả |
| Feedback Log | Ghi nhận chỉnh sửa phục vụ phân tích sai số |
| Final Report | Tổng hợp báo cáo hỗ trợ đánh giá |
