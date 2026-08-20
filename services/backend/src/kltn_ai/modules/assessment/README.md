# Assessment – Đánh giá báo cáo dựa trên bằng chứng (Pipeline 2)

Module nghiệp vụ cho **Pipeline 2 – Phân tích và đánh giá báo cáo dựa trên
bằng chứng**.

## Trách nhiệm

- Orchestrate luồng đánh giá dựa trên rubric:
  Rubric Definition → Rubric Compiler → Checklist Classification (LOCAL / GRAPH)
  → Evidence Retrieval → Evidence Verification → MET / UNMET / CANNOT_ASSESS
  → Evidence-grounded Rationale → Deterministic Decision Rules → Proposed Score.
- Quản lý schema cho checklist verification result, rationale và proposed score.
- Phân loại checklist thành LOCAL (bằng chứng cục bộ) hoặc GRAPH (cần đối chiếu
  quan hệ nhiều phần).
- Xác minh từng checklist ở một trong ba trạng thái: `MET`, `UNMET`,
  `CANNOT_ASSESS`.
- Sinh rationale bám sát evidence và liên kết với vị trí cụ thể trong báo cáo.
- Suy ra điểm đề xuất bằng decision rules của rubric, **không** để LLM trực tiếp
  quyết định điểm.
- Bổ sung cảnh báo: nội dung thiếu bằng chứng, không nhất quán, dấu hiệu AI-generated.

## Ranh giới

- Gọi `integrations/retrieval` cho Local Evidence Retrieval.
- Gọi `integrations/graph` cho Graph-based Evidence Retrieval (HippoRAG-style).
- Gọi `integrations/local_ai` cho LLM verification và rationale generation.
- Nhận rubric đã compile từ module `rubrics`.
- Có thể sử dụng kết quả từ module `similarity` như evidence bổ sung.

## Cấu trúc dự kiến

```
assessment/
├── schemas.py          # ChecklistResult, Rationale, ProposedScore, AssessmentReport
├── service.py          # AssessmentService – orchestrate pipeline
├── compiler.py         # RubricCompiler – chuyển rubric thành checklist truy xuất được
├── classifier.py       # Checklist classifier: LOCAL vs GRAPH
├── verifier.py         # Evidence verification logic
├── scorer.py           # Deterministic scoring rules
├── repository.py       # CRUD assessment results
└── policy.py           # Evidence policy, CANNOT_ASSESS thresholds
```
