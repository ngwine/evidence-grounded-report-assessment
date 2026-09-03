# Xây dựng hệ thống hỗ trợ kiểm tra đạo văn và đánh giá báo cáo sinh viên dựa trên bằng chứng

**Development of an Evidence-Grounded System for Plagiarism Checking and Student
Report Assessment**

Hệ thống hỗ trợ giảng viên kiểm tra tính tương đồng và đánh giá báo cáo sinh
viên theo hướng **local-first**, **evidence-first** và **human-in-the-loop**.

## Chức năng chính

1. **Xử lý và quản lý báo cáo** – Upload PDF/DOCX, nhận diện cấu trúc chương/
   mục/đoạn văn, chuẩn hóa và lập chỉ mục phục vụ truy xuất.
2. **Kiểm tra nội dung tương đồng** – Hybrid Retrieval (BM25 + Dense), RRF,
   re-ranking, phân loại dạng tương đồng (verbatim / paraphrase / summary) và
   Similarity Report.
3. **Đánh giá báo cáo dựa trên bằng chứng** – Rubric → Checklist → Evidence
   Retrieval (Local + Graph) → Verification → Rationale → Deterministic Scoring.
4. **Hỗ trợ giảng viên** – Sinh câu hỏi vấn đáp, Lecturer Review, Feedback Log
   và báo cáo tổng hợp.

> Kết quả AI chỉ là đề xuất hỗ trợ. Hệ thống không tự kết luận đạo văn và
> không tự công bố điểm.

## Trạng thái

Project hiện ở giai đoạn **scaffold**, chưa phải MVP chạy được.

| Hạng mục                                  | Trạng thái                                                                                                      |
| ------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| Phạm vi đề tài                          | Đã chốt: 2 hướng chính (Similarity, Evidence-grounded Assessment) + 1 hướng bổ sung (Targeted Questions) |
| SRS/Use Case tuần 1                        | `Review candidate`; cần đồng bộ bỏ các RQ/feature cũ không còn trong phạm vi                          |
| Product Backlog/WBS                         | Baseline v1.1 cập nhật actual/reforecast ngày 03/09/2026; chờ Q/Y review/ký                                      |
| Cơ sở dữ liệu                           | Đã chọn MongoDB                                                                                                |
| MongoDB deployment và Search/Vector Search | Chờ `W2.2`/`G-02`                                                                                                 |
| Frontend, API, worker                       | Mới tạo cấu trúc                                                                                              |
| Parser và chunking | Prototype PDF/DOCX đã merge vào `main`; chờ worker integration, stable provenance, real/golden corpus và benchmark chất lượng |
| Model local | Chờ benchmark tại `G-03` |
| Search Provider bên ngoài                 | `OUT OF SCOPE`; chỉ mở lại bằng change request được Q/Y/GVHD duyệt                                      |

## Kiến trúc dự kiến

```mermaid
flowchart LR
    U[Người dùng] --> WEB[React + Vite]
    WEB --> API[FastAPI]
    API --> DB[(MongoDB)]
    API --> FS[(File storage)]
    API --> Q[Job queue]
    Q --> WK[Worker]
    WK --> PARSER[Parser sandbox]
    WK --> IDX[Indexing – BM25 + Dense]
    WK --> P1[Pipeline 1 – Similarity]
    WK --> P2[Pipeline 2 – Assessment]
    WK --> GRAPH[Evidence Graph]
    WK --> DB
    WK --> AI[Local AI runtime]
    WK -. chỉ sau change request .-> SP[Extension boundary – OUT OF SCOPE]
```

- Frontend không kết nối trực tiếp MongoDB.
- API xử lý xác thực, phân quyền, nghiệp vụ ngắn và trả `run_id` cho tác vụ dài.
- Worker xử lý parse, indexing, retrieval, AI và thực nghiệm; không chạy model lớn trong HTTP request.
- **Pipeline 1** (Similarity): BM25 + Dense → RRF → Re-ranking → Classification → Similarity Report.
- **Pipeline 2** (Assessment): Rubric Compile → Checklist Classify → Evidence Retrieval (Local/Graph) → Verification → Rationale → Scoring.
- MongoDB là source of truth. Lexical/vector index là dữ liệu dẫn xuất có thể dựng lại.
- Search Provider không thuộc WBS 24 tuần và luôn `disabled`; boundary chỉ được
  giữ làm extension placeholder, không phải feature đang chờ triển khai.

## Cấu trúc thư mục

```text
.
├── apps/
│   └── web/                      # React + Vite + TypeScript
│       ├── src/
│       │   ├── app/              # Router, provider, bootstrap
│       │   ├── features/         # Auth, reports, similarity, rubrics,
│       │   │                     # analysis, review, questions, feedback
│       │   ├── components/       # UI dùng chung
│       │   ├── lib/              # API client, helpers
│       │   └── types/
│       └── tests/
├── services/
│   └── backend/                  # Một Python codebase, hai tiến trình
│       ├── src/kltn_ai/
│       │   ├── api/              # FastAPI routes/dependencies/errors
│       │   ├── core/             # Config, auth, logging, security
│       │   ├── db/               # Mongo client, validators, indexes
│       │   ├── modules/          # Nghiệp vụ theo feature
│       │   │   ├── auth/
│       │   │   ├── reports/
│       │   │   ├── references/  # quote/citation span core; DOI checker ngoài scope
│       │   │   ├── similarity/   # Pipeline 1 – tương đồng
│       │   │   ├── rubrics/
│       │   │   ├── assessment/   # Pipeline 2 – đánh giá bằng chứng
│       │   │   ├── reviews/
│       │   │   ├── questions/
│       │   │   ├── feedback/     # Feedback Log
│       │   │   ├── datasets/     # Metadata dataset thực nghiệm
│       │   │   └── analysis/     # Shared analysis logic
│       │   ├── integrations/     # Adapter parser, indexing, retrieval,
│       │   │   │                 # graph, local AI, storage, provider
│       │   │   ├── parsing/
│       │   │   ├── indexing/     # BM25 + Dense Vector indexing
│       │   │   ├── retrieval/    # Hybrid Retrieval, RRF, re-ranking
│       │   │   ├── graph/        # Evidence Graph (HippoRAG-style)
│       │   │   ├── local_ai/
│       │   │   ├── storage/
│       │   │   └── search_provider/ # extension placeholder – OUT OF SCOPE
│       │   └── worker/           # Task handlers, checkpoint, retry
│       └── tests/
├── research/                     # Nghiên cứu và thực nghiệm
│   ├── protocols/
│   │   ├── rq1-similarity/       # RQ1: Phát hiện tương đồng
│   │   ├── rq2-assessment/       # RQ2: Đánh giá dựa bằng chứng
│   │   └── rq3-questions/        # RQ3: Sinh câu hỏi
│   ├── datasets/
│   │   ├── similarity/           # Cặp đoạn gán nhãn
│   │   ├── assessment/           # Báo cáo + rubric + labels
│   │   └── questions/            # Câu hỏi đánh giá
│   ├── configs/
│   ├── scripts/
│   ├── notebooks/
│   └── results/
├── tests/e2e/                    # Kiểm thử xuyên web–API–worker
├── infra/                        # Docker/MongoDB
├── docs/
│   ├── architecture/             # Kiến trúc phân lớp
│   ├── pipelines/                # Pipeline 1 & 2
│   ├── adr/
│   ├── data/
│   ├── threat-model/
│   └── week-01/                  # Hồ sơ tuần 1
├── scripts/                      # Bootstrap, lint, test, migration
├── var/                          # Upload, model, cache, log; không commit
├── .env.example
├── .editorconfig
└── .gitignore
```

## Thiết lập

Hiện chưa có manifest cho toàn bộ ứng dụng hoặc `compose.yaml`. Riêng prototype
Parsing/Chunking có dependency phát triển tại
`services/backend/requirements-dev.txt`. Bước cấu hình đầu tiên:

```bash
cp .env.example .env
python3 -m venv .venv
./.venv/bin/pip install -r services/backend/requirements-dev.txt
./.venv/bin/python -m pytest services/backend/tests/test_pdf_docx_parsing.py -v
```

Sau khi hoàn thành scaffold tiếp theo, phần này sẽ có các lệnh đã kiểm thử để:

1. khởi động MongoDB và dịch vụ nền;
2. chạy FastAPI và worker;
3. chạy React/Vite;
4. kiểm tra health endpoint và smoke test.

## Quy ước chính

- Không commit `.env`, secret, báo cáo thật, PII, model weight, cache hoặc log.
- File upload và nội dung web luôn được xem là dữ liệu không tin cậy.
- Mọi kết quả AI phải lưu model/prompt/config version và evidence ID.
- Chỉ giảng viên có quyền mới được duyệt hoặc công bố kết quả.
- Logic thực nghiệm chính đặt trong script/config có version; notebook chỉ dùng khám phá.
- Thay đổi DB, provider, rubric, RQ hoặc phạm vi phải có ADR/change record.
- Branch, commit, pull request và review tuân theo
  [`CONTRIBUTING.md`](CONTRIBUTING.md); thay đổi vào `main` qua PR và cần thành
  viên còn lại approve.

## Tài liệu

- [Quy ước Git và review](CONTRIBUTING.md)
- [Product Backlog](docs/planning/PRODUCT_BACKLOG.md)
- [WBS và phân công theo 24 tuần](docs/planning/WBS_VA_PHAN_CONG.md)
- [Hồ sơ tuần 1](docs/week-01/README.md)
- [Đặc tả yêu cầu](docs/week-01/W1-03-dac-ta-yeu-cau-v1.md)
- [Bộ Use Case](docs/week-01/W1-04-bo-use-case.md)
- [Snapshot Backlog/WBS tuần 1 (lịch sử)](docs/week-01/W1-05-backlog-wbs.md)
- [Pipeline 1 – Similarity](docs/pipelines/pipeline-1-similarity.md)
- [Pipeline 2 – Assessment](docs/pipelines/pipeline-2-assessment.md)
- [Kiến trúc phân lớp](docs/architecture/layers.md)
