# Research

Thư mục nghiên cứu và thực nghiệm cho 3 hướng nghiên cứu.

## Cấu trúc

- `protocols/` – Protocol khóa trước khi chạy test chính.
  - `rq1-similarity/` – RQ1: Phát hiện và truy xuất nội dung tương đồng
  - `rq2-assessment/` – RQ2: Đánh giá báo cáo dựa trên bằng chứng
  - `rq3-questions/` – RQ3: Sinh câu hỏi có mục tiêu
- `datasets/` – Dataset trong miền do nhóm xây dựng.
  - `similarity/` – Cặp đoạn gán nhãn (verbatim / paraphrase / summary / none)
  - `assessment/` – Báo cáo + rubric + checklist labels + evidence
  - `questions/` – Câu hỏi đánh giá
- `configs/` – Baseline, model, prompt, index config có version.
- `offline_retrieval/` – Fixed-window, BM25, Dense, RRF, metric và run manifest
  chạy độc lập với MongoDB/API.
- `scripts/` – Experiment runner, metrics và tạo bảng/biểu.
- `notebooks/` – Khám phá; không chứa logic duy nhất để tạo kết quả luận văn.
- `results/` – Output được sinh lại từ artifact, mặc định không commit.

## Quy tắc

Mỗi run phải truy được về code commit, dataset manifest, model, prompt/config,
seed, môi trường máy và metric script.

Dataset chưa có governance state `APPROVED`, allowed purpose, checksum và split
hợp lệ bị từ chối trước khi index hoặc chạy experiment.
