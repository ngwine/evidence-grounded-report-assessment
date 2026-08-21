# WBS VÀ PHÂN CÔNG NHÂN SỰ

## Evidence-Grounded Plagiarism Checking and Student Report Assessment

| Thuộc tính | Giá trị |
|---|---|
| Phiên bản | 1.0 |
| Ngày lập/rebaseline | 21/08/2026 |
| Thời gian dự án | 08/08/2026–22/01/2027 (24 tuần) |
| Hạn nộp | 23/01/2027 |
| Thành viên 1 | Nguyễn Trần Ngọc Quý — 523H0087 — Nhóm trưởng |
| Thành viên 2 | Võ Thị Kim Yến — 52200029 |
| GVHD | Vũ Đình Hồng |
| Nguồn lịch | `Schedule_KLTN_Evidence_Grounded.xlsx`, sheet `FILE KẾ HOẠCH MẪU`; SHA-256 `548f068bdc71d022e29f8def983b10f689d14606cc0db6d33c0783189f318984` |
| Product Backlog | [`PRODUCT_BACKLOG.md`](./PRODUCT_BACKLOG.md) |

WBS này lấy thứ tự công việc và sản phẩm đầu ra trong file Excel làm baseline.
Các roadmap cũ lệch Excel ở W06–W15 không còn là nguồn lịch chuẩn. Các mốc
W01/W02 đã qua được giữ nguyên để thể hiện độ trễ; không sửa ngày nhằm làm đẹp
tiến độ.

---

## 1. Mục tiêu của WBS

- Chuyển 24 tuần trong Excel thành work package có đầu ra kiểm chứng được.
- Mỗi work package có đúng một owner và một reviewer.
- Liên kết từng work package với canonical backlog ID.
- Cân bằng tải Q/Y theo SP nhưng vẫn giữ ownership kỹ thuật rõ.
- Cung cấp dữ liệu trực tiếp để tạo issue, milestone và cập nhật cột
  `Công việc đã làm`/`% hoàn thành` trong Excel.
- Đặt dataset, metric, test và viết luận văn song song với code thay vì dồn cuối
  kỳ.

## 2. Quy ước

### 2.1. Viết tắt và ownership

| Ký hiệu | Thành viên | Ownership chính | Ownership phụ/review |
|---|---|---|---|
| Q | Nguyễn Trần Ngọc Quý | Điều phối; architecture; backend/API/MongoDB; worker; Document Processing; Similarity; integration; DevOps/release | Review data/rubric/graph/frontend/experiment và nội dung nghiên cứu |
| Y | Võ Thị Kim Yến | Data/rubric; annotation; frontend/UX; model benchmark; Evidence Assessment/Graph; question; lecturer evaluation; báo cáo | Review API/schema/retrieval, integration test và tài liệu kỹ thuật |

Ownership không tạo silo. Interface giữa hai pipeline, schema evidence, metric
và kết quả thực nghiệm bắt buộc review chéo.

### 2.2. Story point

- `1 SP`: thay đổi rất nhỏ, ít bất định.
- `2–3 SP`: work package nhỏ, có thể hoàn thành độc lập.
- `4–5 SP`: work package vừa, cần thiết kế/tích hợp/test.
- `8 SP`: quá lớn cho một work package; phải tách trước khi vào
  `IN PROGRESS`.

SP là ước lượng tương đối, không quy đổi trực tiếp thành giờ. Tổng WBS dùng để
cân bằng tải; không cộng với SP của Product Backlog.

### 2.3. Trạng thái

- `DONE`: có artifact, đạt DoD và reviewer chấp thuận.
- `IN PROGRESS`: đã có một phần artifact nhưng chưa đạt DoD.
- `TODO`: chưa có bằng chứng hoàn thành trong workspace.
- `BLOCKED`: dependency/decision bắt buộc chưa đóng.
- `CARRY-OVER`: quá hạn tuần gốc và được chuyển có kiểm soát sang cửa sổ phục
  hồi, không thay ngày baseline.

`Ready` là cột workflow, không phải giá trị trạng thái WBS. Work package ở cột
`Ready` vẫn mang `TODO` cho đến khi owner bắt đầu và có evidence đầu tiên.

## 3. Definition of Done chung

Một work package chỉ được `DONE` khi:

1. Artifact/code được commit và liên kết tới ID WBS/backlog.
2. Đầu ra/acceptance criteria riêng trong bảng đạt.
3. Test phù hợp hoặc biên bản review tồn tại; reviewer chấp thuận.
4. Schema/API/migration/tài liệu được cập nhật cùng hành vi.
5. Không còn lỗi Critical/High chưa có waiver có owner/expiry.
6. Không commit secret, PII, báo cáo thật, model weight hoặc dữ liệu không đủ
   quyền.

Đối với thực nghiệm, DoD bổ sung:

- Dataset/split/model/prompt/config/seed/hardware/commit được lưu.
- Có lệnh/script chạy lại và raw result truy vết được.
- Metric có test; final test không được dùng để chọn tham số.
- Bảng/biểu được tạo từ artifact khóa, không nhập tay số liệu.

## 4. WBS cấp cao

| WBS | Workstream | Tuần | Owner chính | Gate chính |
|---|---|---|---|---|
| 1.0 | Discovery, scope, data governance và planning | W01–W02 | Q/Y | `G-01` |
| 2.0 | Architecture, data model, API, UX và dev baseline | W02–W03 | Q/Y | `G-02` |
| 3.0 | Report lifecycle, queue, parsing, chunking và provenance | W03–W05 | Q | `G-03` |
| 4.0 | BM25, Dense, RRF, reranker và Similarity Analysis | W06–W08 | Q | `G-04` |
| 5.0 | Rubric Compiler và LOCAL Evidence Assessment | W09–W10 | Y | `G-05` |
| 6.0 | Evidence Graph, Graph Retrieval và Assessment Engine | W11–W13 | Y | `G-06` |
| 7.0 | Question, dashboard, lecturer review, feedback và export | W14–W15 | Y | Chuẩn bị `G-07` |
| 8.0 | E2E hardening và benchmark freeze | W16–W17 | Q/Y | `G-07`, `G-08` |
| 9.0 | RQ1/RQ2/support experiments | W18–W20 | Q/Y | Result freeze |
| 10.0 | Optimization, thesis, release và submission | W21–W24 | Q/Y | `G-09…G-11` |

## 5. Milestone và quality gate

Gate dùng status `OPEN`, `PASS`, `FAIL` hoặc `WAIVED`. `PASS/FAIL/WAIVED` bắt
buộc có evidence, approver và ngày quyết định ISO `YYYY-MM-DD`.

| Gate | Tuần | Điều kiện Pass | Nếu Fail | Status 21/08 | Evidence | Approver | Decision date |
|---|---:|---|---|---|---|---|---|
| `G-01 Scope/Data` | W01–W02 | Scope/RQ/actor/capacity và quyền dùng sample có quyết định | Không đưa dữ liệu chưa rõ quyền vào hệ thống; mở blocker có owner | OPEN | W1 artifacts; data-rights dossier chưa đóng | Q + Y + GVHD | — |
| `G-02 Architecture` | W02 | C4, MongoDB/index decision, schema, API, wireframe, rubric/protocol v1 được review | Chỉ dựng skeleton độc lập với decision; carry-over trừ vào capacity W03 | OPEN | `W2.2–W2.6` còn carry-over | Q + Y | — |
| `G-03 Model/Parse Feasibility` | W05 | Parser/chunk provenance đạt fixture; model/index chạy trên máy demo; JSON schema khóa | Dùng fallback model/index; cắt OCR/extension | OPEN | — | Q + Y | — |
| `G-04 Similarity v1` | W08 | BM25/Dense/RRF/reranker/classifier/report chạy và có metric sơ bộ | Giữ baseline tốt nhất; không mở extension | OPEN | — | Q + Y | — |
| `G-05 LOCAL Assessment` | W10 | Rubric→LOCAL evidence→three-state verification chạy, có ground truth pilot | Sửa protocol/retrieval trước khi dựng graph sâu | OPEN | — | Q + Y | — |
| `G-06 Graph Assessment` | W13 | Graph provenance, multi-hop retrieval, rationale và deterministic scoring đạt case test | Giữ LOCAL path làm fallback và báo limitation graph | OPEN | — | Q + Y | — |
| `G-07 RC1/Freeze` | W16 | E2E, RBAC, security, retry/failure test; không còn blocker/critical | Dừng feature, triage và cắt P1/P2 | OPEN | — | Q + Y | — |
| `G-08 Benchmark Ready` | W17 | Dataset/split/guideline/metric/manifest khóa, leakage check đạt | Không chạy bảng kết quả chính thức | OPEN | — | Q + Y + GVHD | — |
| `G-09 RC2` | W21 | Performance/security/privacy/reproducibility đạt mức demo | Tối ưu bottleneck có evidence; giữ cấu hình ổn định nhất | OPEN | — | Q + Y | — |
| `G-10 Release 1.0` | W23 | Report–code–data–result–demo nhất quán; clean install đạt | Chỉ sửa lỗi/consistency, không thêm feature | OPEN | — | Q + Y + GVHD | — |
| `G-11 Submission` | W24 + 23/01 | W24 readiness đạt; nộp trước hạn 23/01/2027; receipt ghi timestamp, kênh/người nhận, inventory/link hoặc mã biên nhận và checksum | Escalate ngay GVHD; dùng offline demo/fallback | OPEN | — | Q + Y | — |

## 6. Trạng thái và kế hoạch phục hồi tại 21/08/2026

- W01 có tài liệu review-candidate nhưng chưa phải mọi item đều `DONE`.
- W02 kết thúc ngày 21/08; mới có kiến trúc phân lớp/pipeline, các thiết kế còn
  lại chưa có artifact.
- `W2.2–W2.6` được đánh dấu `CARRY-OVER`; chốt interface chặn vertical slice
  trước, đóng phần còn lại trong W03 và không sửa ngày W02 trong lịch gốc.
- W01/W02 không được ghi `100%` trong Excel cho đến khi đạt DoD tương ứng.
- Trong recovery, Q ưu tiên quyết định/schema/API chặn code; Y ưu tiên
  wireframe/rubric/dataset protocol để hai luồng có thể phát triển song song.
- Carry-over không tạo thêm capacity. Trước khi commit W03, owner ghi
  `remaining SP`; với mỗi người, `remaining carry-over + committed W03 ≤ 13 SP`.
  Nếu vượt, defer theo P2 → P1 → P0 không chặn vertical slice; không cắt
  data-rights/security. Mọi defer phải cập nhật target week/change log.
- Chỉ làm song song skeleton thực sự độc lập với decision; work package phụ
  thuộc `G-02` chưa Pass giữ `TODO`, không chuyển toàn bộ W03 sang `Ready`.

---

## 7. WBS chi tiết theo tuần

### Tuần 1 — 08/08 đến 14/08/2026

**Milestone:** Baseline phạm vi và hồ sơ lập kế hoạch sẵn sàng review.

| ID | Backlog | Work package | Owner | Review | SP | Phụ thuộc | Đầu ra/DoD riêng | Trạng thái 21/08 |
|---|---|---|---|---|---:|---|---|---|
| `W1.1` | `EP-01-S01` | Đồng bộ mục tiêu, phạm vi, actor, Use Case, RQ và tiêu chí hoàn thành sau rebaseline | Q | Y | 3 | — | Quyết định 2 hướng chính + 1 bổ sung đã chốt; SRS/Use Case/README bỏ RQ/provider/reference feature cũ, Q/Y review và scope change có log | IN PROGRESS |
| `W1.2` | `EP-01-S05` | Khảo sát AS-IS/TO-BE và chuẩn bị xác nhận giảng viên | Y | Q | 3 | `W1.1` | Bộ câu hỏi, biên bản và bảng giả định có trạng thái/người/ngày | IN PROGRESS |
| `W1.3` | `EP-01-S01` | Khảo sát kỹ thuật plagiarism/IR/rubric/evidence/graph | Y | Q | 3 | `W1.1` | Có [khảo sát kỹ thuật](../week-01/W1-02-khao-sat-ky-thuat.md) so sánh baseline, metric, ưu/nhược điểm và nguồn nghiên cứu | DONE |
| `W1.4` | `EP-12-S01` | Lập Product Backlog, WBS và traceability ban đầu | Q | Y | 2 | `W1.1` | Hai file planning riêng; mọi tuần/outcome có owner; RQ1/RQ2/RQ3 trỏ tới epic, experiment và artifact tương ứng | IN PROGRESS |
| `W1.5` | `EP-01-S04`, `EP-02-S01` | Khởi tạo repo, cấu trúc thư mục, quy ước Git và issue board | Q | Y | 3 | `W1.4` | Capacity/máy/deadline được ghi; repo/scaffold/README/labels/milestones có bằng chứng | IN PROGRESS |
| `W1.6` | `EP-12-S01` | Viết bản nháp Chương 1 | Y | Q | 2 | `W1.1` | Bối cảnh, vấn đề, mục tiêu, phạm vi, đóng góp và bố cục | TODO |

**Tải kế hoạch:** Q = 8 SP, Y = 8 SP.

### Tuần 2 — 15/08 đến 21/08/2026

**Milestone:** Design baseline được khóa trước khi phát triển sâu.

| ID | Backlog | Work package | Owner | Review | SP | Phụ thuộc | Đầu ra/DoD riêng | Trạng thái 21/08 |
|---|---|---|---|---|---:|---|---|---|
| `W2.1` | `EP-02-S05`, `EP-02-S04` | Thiết kế C4 Context/Container/Deployment, data flow, trust boundary và threat-model/adversarial plan v1 | Q | Y | 4 | `W1.1` | C4 phản ánh Web–API–worker–DB/storage/index/local AI; có asset/trust-boundary/risk→mitigation→test mapping cho upload/parser, queue, DB, tenant retrieval, prompt injection, output sanitization và log privacy | IN PROGRESS |
| `W2.2` | `EP-02-S02`, `EP-09-S06` | Chốt MongoDB deployment/index ADR, collection, data dictionary và lifecycle fields | Q | Y | 5 | `W2.1` | Schema/reference/index/invariant/migration/rebuild rõ; purpose/rights/retention/tombstone và derived-data cascade được mô hình hóa | CARRY-OVER |
| `W2.3` | `EP-02-S06` | Viết API contract v1 và error format | Q | Y | 4 | `W2.2` | Auth/report/source/upload/job/chunk/rubric/result/review contract | CARRY-OVER |
| `W2.4` | `EP-02-S07`, `EP-02-S03` | Wireframe, navigation map và ma trận quyền các luồng P0 | Y | Q | 4 | `W1.1` | Upload/progress/evidence/review có loading/empty/error/permission | CARRY-OVER |
| `W2.5` | `EP-01-S06`, `EP-05-S01` | Rubric template v1, checklist LOCAL/GRAPH và annotation/adjudication guideline | Y | Q | 5 | `W1.2` | Criterion/evidence/weight/level/rule có example; người gán nhãn, vòng review và cách giải quyết bất đồng rõ | CARRY-OVER |
| `W2.6` | `EP-01-S02`, `EP-04-S01`, `EP-09-S06`, `EP-10-S01` | Lập data/rubric/model inventory, hồ sơ rights–purpose–retention và dataset/benchmark/sample-corpus plan v1 | Y | Q | 4 | `W1.2`, `W2.5`, nguồn dữ liệu/GVHD | Mỗi nguồn có owner/license-or-consent/allowed purpose/classification/anonymization/retention/approver/date; deny-by-default nếu chưa duyệt; đơn vị mẫu/nhãn/split/metric/provenance và sample không nhạy cảm rõ | CARRY-OVER |

**Tải kế hoạch:** Q = 13 SP, Y = 13 SP.

**Recovery:** chốt interface chặn code trước 23/08; hoàn tất `W2.2–W2.6` và
review `G-02` theo bảng recovery (mục tiêu 25/08, closure/rebaseline 28/08).

### Tuần 3 — 22/08 đến 28/08/2026

**Milestone:** Platform core chạy từ UI qua API đến MongoDB và tạo được job upload.

| ID | Backlog | Work package | Owner | Review | SP | Phụ thuộc | Đầu ra/DoD riêng | Trạng thái |
|---|---|---|---|---|---:|---|---|---|
| `W3.1` | `EP-02-S01/02/06`, `EP-11-S01` | Dựng FastAPI, settings, MongoDB init/migration, Compose và CI quality/security baseline | Q | Y | 5 | `W2.2/3` | Healthcheck và DB/index init đạt; lint/type/test, SAST, secret và dependency scan chạy CI; High/Critical fail gate hoặc có waiver owner/expiry | TODO |
| `W3.2` | `EP-02-S03/08` | Backend auth/session, RBAC và audit events nền | Q | Y | 5 | `W3.1`, `W2.4` | Ma trận role/ownership và negative authorization tests đạt | TODO |
| `W3.3` | `EP-03-S01`, `EP-10-S01`, `EP-11-S02` | Chuẩn bị report/source metadata examples, safe-upload fixtures và validation/contract tests | Y | Q | 3 | `W2.3/6` | Fixture PDF/DOCX hợp lệ/lỗi có rights state và expected metadata; bao phủ MIME/size/path/duplicate; không chứa dữ liệu nhạy cảm | TODO |
| `W3.4` | `EP-02-S07/03` | Dựng React/Vite, routing, auth state và UI đăng nhập/quản lý quyền tối thiểu | Y | Q | 5 | `W2.3/4`, `W3.2` | Success/loading/error/forbidden state và smoke test | TODO |
| `W3.5` | `EP-03-S01` | UI quản lý báo cáo/kho nguồn, upload và theo dõi version/status | Y | Q | 5 | `W3.3/6` | Upload/list/detail/status chạy với fixture hoặc API thật | TODO |
| `W3.6` | `EP-03-S01/06`, `EP-09-S01/04` | Backend upload API, queue/worker skeleton, job-state contract và correlation logging | Q | Y | 3 | `W3.1/2/3` | Upload lưu version/hash/status; job queued/processing/failed/completed; `request_id→job_id→run_id` truyền qua API/worker/log và log không lộ PII; contract test đạt | TODO |

**Tải kế hoạch:** Q = 13 SP, Y = 13 SP.

### Tuần 4 — 29/08 đến 04/09/2026

**Milestone:** Document Processing Pipeline v1 tạo chunk truy vết về đúng tài liệu/trang.

| ID | Backlog | Work package | Owner | Review | SP | Phụ thuộc | Đầu ra/DoD riêng | Trạng thái |
|---|---|---|---|---|---:|---|---|---|
| `W4.1` | `EP-03-S02`, `EP-11-S02` | Tích hợp Docling parser trong worker có timeout/resource limit | Q | Y | 5 | `W3.3/6` | PDF/DOCX parse qua adapter; lỗi/timeout không tạo artifact giả | TODO |
| `W4.2` | `EP-03-S02` | Normalized document schema và mapping section/page/table/reference vào MongoDB | Q | Y | 5 | `W4.1`, `W2.2` | Schema/version/provenance và idempotent persistence được test | TODO |
| `W4.3` | `EP-03-S06`, `EP-09-S01` | Parse job handler, checkpoint, retry và failure reporting | Q | Y | 3 | `W4.1/2` | Retry không nhân đôi document/chunk; UI/API thấy lỗi có mã | TODO |
| `W4.4` | `EP-03-S03` | Cleaner và structure-aware chunker | Y | Q | 5 | `W4.2` | Chunk theo section/paragraph; overlap/order/span hợp lệ; giữ raw/normalized text | TODO |
| `W4.5` | `EP-03-S07` | GROBID quote/citation/reference marker-to-span mapping và fixture nhiều style | Y | Q | 3 | `W4.1/2` | Marker/entry/ngữ cảnh liên kết đúng page/span/chunk; raw/confidence lưu được; failure là unknown | TODO |
| `W4.6` | `EP-03-S08` | Golden corpus và benchmark parser/chunk provenance | Y | Q | 5 | `W4.1–5` | Expected structure/page mapping; coverage/error/latency report và test fixture | TODO |

**Tải kế hoạch:** Q = 13 SP, Y = 13 SP.

### Tuần 5 — 05/09 đến 11/09/2026

**Milestone:** Khóa cấu hình AI cục bộ, embedding/reranker và output contract.

| ID | Backlog | Work package | Owner | Review | SP | Phụ thuộc | Đầu ra/DoD riêng | Trạng thái |
|---|---|---|---|---|---:|---|---|---|
| `W5.1` | `EP-03-S04`, `EP-09-S04` | Local AI/embedding service, model loader và inference telemetry | Q | Y | 5 | `W4.4/6` | Health/inference chạy trên máy demo; timeout, batch và model/config provenance rõ | TODO |
| `W5.2` | `EP-03-S04` | Vector index adapter, upsert/search/version/rebuild | Q | Y | 5 | `W5.1`, `W2.2` | Vector liên kết đúng chunk/version; indexing idempotent; rebuild được test | TODO |
| `W5.3` | `EP-04-S04`, `EP-05-S04` | Reranker contract và JSON Schema validators dùng chung | Q | Y | 3 | `W5.1` | Batch rerank và schema similarity/evidence/rationale có test lỗi/timeout | TODO |
| `W5.4` | `EP-10-S06` | Benchmark local LLM trên structured-output fixture | Y | Q | 5 | `W2.6`, `W5.1` | So chất lượng schema, latency, RAM/VRAM trên cùng hardware/config | TODO |
| `W5.5` | `EP-04-S03/04`, `EP-10-S06` | Benchmark embedding và reranker | Y | Q | 5 | `W5.2/3`, sample corpus | Cùng corpus/query/protocol; lưu model/version/config và bảng quality–resource | TODO |
| `W5.6` | `EP-10-S06` | Model-selection report, fallback và gate `G-03` | Y | Q | 3 | `W5.4/5`, `W4.6` | Quyết định có artifact hỗ trợ; cấu hình/fallback/limitation được khóa | TODO |

**Tải kế hoạch:** Q = 13 SP, Y = 13 SP.

### Tuần 6 — 12/09 đến 18/09/2026

**Milestone:** BM25 và Dense Retrieval baseline chạy tái lập được.

| ID | Backlog | Work package | Owner | Review | SP | Phụ thuộc | Đầu ra/DoD riêng | Trạng thái |
|---|---|---|---|---|---:|---|---|---|
| `W6.1` | `EP-03-S04`, `EP-04-S02` | Source lexical index và BM25 Retrieval v1 | Q | Y | 5 | `W4.4`, `W5.2` | Index rebuild/idempotency đạt; Top-K có score/source/page/section; tokenizer/config/index versioned | TODO |
| `W6.2` | `EP-04-S03` | Dense Retrieval v1 | Q | Y | 5 | `W5.2` | Dùng cùng candidate schema/filter/corpus với BM25; model/normalization lưu | TODO |
| `W6.3` | `EP-04-S02/03`, `EP-10-S06` | Dual-retrieval runner và candidate persistence | Q | Y | 3 | `W6.1/2` | Một run tạo hai ranking kèm config/timing/run ID, không trộn index version | TODO |
| `W6.4` | `EP-04-S01` | Gán nhãn seed query–source passages | Y | Q | 5 | `W2.6`, `W4.4` | Có positive/negative và verbatim/paraphrase/summary/none; provenance đầy đủ | TODO |
| `W6.5` | `EP-04-S01`, `EP-10-S01/06` | Query-passage policy và metric Recall@K/MRR/nDCG | Y | Q | 3 | `W6.4` | Quy tắc query khóa trước test; metric unit test bằng ví dụ biết trước | TODO |
| `W6.6` | `EP-04-S02/03` | Audit retrieval và báo cáo baseline BM25/Dense | Y | Q | 5 | `W6.3–5` | Cùng split/hardware; missed evidence, duplicate, latency và lỗi provenance được phân tích | TODO |

**Tải kế hoạch:** Q = 13 SP, Y = 13 SP.

### Tuần 7 — 19/09 đến 25/09/2026

**Milestone:** Hybrid Retrieval v1 và cấu hình quality–latency đề xuất.

| ID | Backlog | Work package | Owner | Review | SP | Phụ thuộc | Đầu ra/DoD riêng | Trạng thái |
|---|---|---|---|---|---:|---|---|---|
| `W7.1` | `EP-04-S04` | Reciprocal Rank Fusion | Q | Y | 3 | `W6.3` | Duplicate/tie xử lý ổn định; `k`/weight configurable và có unit test | TODO |
| `W7.2` | `EP-04-S04` | Cross-Encoder reranker integration | Q | Y | 5 | `W5.3`, `W7.1` | Rerank top-N→top-K; lưu pre/post score, model/config; timeout fallback | TODO |
| `W7.3` | `EP-04-S04`, `EP-09-S04` | Hybrid pipeline và stage-latency instrumentation | Q | Y | 5 | `W7.1/2` | BM25+Dense→RRF→rerank chạy một lệnh; stage failure không mất baseline | TODO |
| `W7.4` | `EP-04-S01` | Hard-negative/error set cho retrieval | Y | Q | 5 | `W6.4/6` | Có lexical false positive, paraphrase khó, citation và none; review chéo nhãn | TODO |
| `W7.5` | `EP-10-S06` | Protocol và run so sánh BM25/Dense/Hybrid | Y | Q | 3 | `W7.3/4` | Cùng corpus/split/top-k/hardware; run manifest và raw result đầy đủ | TODO |
| `W7.6` | `EP-04-S04` | Error analysis và chọn cấu hình Hybrid | Y | Q | 5 | `W7.5` | Bảng quality–latency, taxonomy lỗi và quyết định có run ID hỗ trợ | TODO |

**Tải kế hoạch:** Q = 13 SP, Y = 13 SP.

### Tuần 8 — 26/09 đến 02/10/2026

**Milestone:** Similarity Analysis Pipeline v1 có evidence viewer và metric sơ bộ.

| ID | Backlog | Work package | Owner | Review | SP | Phụ thuộc | Đầu ra/DoD riêng | Trạng thái |
|---|---|---|---|---|---:|---|---|---|
| `W8.1` | `EP-04-S09/11` | Similarity orchestration/API và classification-result persistence | Q | Y | 5 | `W7.3`, `W5.3` | Run liên kết query/candidate/model/config/label; rerun/version không ghi đè | TODO |
| `W8.2` | `EP-04-S10/11` | Span alignment, unique coverage và weighted document aggregation | Q | Y | 5 | `W8.1` | Span hợp lệ; overlap không tính hai lần; công thức/version/threshold rõ | TODO |
| `W8.3` | `EP-04-S07` | Similarity Report API và export fixture | Q | Y | 3 | `W8.1/2` | Report truy vết pair/source/page/run; ghi rõ similarity không đồng nghĩa đạo văn | TODO |
| `W8.4` | `EP-04-S09` | Classifier, calibration và ground-truth guideline bốn nhãn | Y | Q | 5 | `W7.2/4` | VERBATIM/PARAPHRASE/SUMMARY/NONE; confidence/ambiguous case; F1 từng lớp | TODO |
| `W8.5` | `EP-04-S10` | Quote/citation context rule và test cases | Y | Q | 3 | `W4.5`, `W8.4` | Quote/citation đánh dấu riêng, không tự kết luận gian lận; case khó có expected output | TODO |
| `W8.6` | `EP-04-S07` | Side-by-side evidence/highlight UI và integration test | Y | Q | 5 | `W8.2/3` | Hai đoạn/nguồn/type/score/location hiển thị; empty/error/review state và E2E fixture đạt | TODO |

**Tải kế hoạch:** Q = 13 SP, Y = 13 SP.

### Tuần 9 — 03/10 đến 09/10/2026

**Milestone:** Rubric Compiler v1 sinh checklist thực thi được.

| ID | Backlog | Work package | Owner | Review | SP | Phụ thuộc | Đầu ra/DoD riêng | Trạng thái |
|---|---|---|---|---|---:|---|---|---|
| `W9.1` | `EP-05-S01` | Rubric persistence, immutable version và API | Q | Y | 5 | `W2.2/3/5` | Draft/clone/publish/version lifecycle, order/weight và quyền sửa được test | TODO |
| `W9.2` | `EP-05-S09` | Compiler execution/persistence và validation error mapping | Q | Y | 5 | `W9.1`, `W9.4` | Compile deterministic; invalid rule/reference báo đúng field; output versioned | TODO |
| `W9.3` | `EP-05-S01/09` | Rubric API/compiler test suite | Q | Y | 3 | `W9.1/2` | Test lifecycle, total weight, rule conflict và reproducible compile output | TODO |
| `W9.4` | `EP-05-S01/09` | Rubric domain model và template library | Y | Q | 5 | `W2.5` | Criterion–checklist–evidence–level–rule có định nghĩa và rubric mẫu thực tế | TODO |
| `W9.5` | `EP-05-S09` | LOCAL/GRAPH assignment và deterministic decision-rule spec | Y | Q | 5 | `W9.4` | Mỗi checklist có mode, evidence requirement và three-state decision table | TODO |
| `W9.6` | `EP-05-S01` | Rubric management UI | Y | Q | 3 | `W9.1/2` | Tạo/sửa/preview/publish; validation và version history hiển thị đúng | TODO |

**Tải kế hoạch:** Q = 13 SP, Y = 13 SP.

### Tuần 10 — 10/10 đến 16/10/2026

**Milestone:** LOCAL Evidence Assessment v1 đạt `G-05`.

| ID | Backlog | Work package | Owner | Review | SP | Phụ thuộc | Đầu ra/DoD riêng | Trạng thái |
|---|---|---|---|---|---:|---|---|---|
| `W10.1` | `EP-05-S02/03/04` | LOCAL assessment orchestration và API | Q | Y | 5 | `W7.3`, `W9.2`, `W10.4` | Criterion chạy retrieval→pack→verification; liên kết run/checklist/rubric/report version | TODO |
| `W10.2` | `EP-05-S04` | Evidence Pack persistence và evidence validator | Q | Y | 3 | `W10.1/5` | Bắt buộc chunk/page/section/relevance/provenance; dangling/cross-report evidence bị loại | TODO |
| `W10.3` | `EP-05-S03/04`, `EP-11-S02` | Authorization, no-evidence, timeout và integration tests | Q | Y | 5 | `W10.1/2` | Tenant/report isolation, stale version, retry và prompt-injection fixture đạt | TODO |
| `W10.4` | `EP-05-S02` | Criterion query strategy và LOCAL Evidence Retrieval | Y | Q | 5 | `W7.3`, `W9.5` | Checklist query tạo Top-K evidence đúng report; config/run truy vết được | TODO |
| `W10.5` | `EP-05-S03` | Three-state verification baseline | Y | Q | 5 | `W5.3/6`, `W10.4` | MET/UNMET/CANNOT_ASSESS đúng JSON Schema và chỉ dựa Evidence Pack | TODO |
| `W10.6` | `EP-05-S05` | Ground-truth cases và pilot LOCAL assessment | Y | Q | 3 | `W10.4/5` | Case đủ/thiếu/mâu thuẫn; báo label metric, evidence recall và lỗi sơ bộ | TODO |

**Tải kế hoạch:** Q = 13 SP, Y = 13 SP.

### Tuần 11 — 17/10 đến 23/10/2026

**Milestone:** Evidence Graph v1 có provenance đầy đủ.

| ID | Backlog | Work package | Owner | Review | SP | Phụ thuộc | Đầu ra/DoD riêng | Trạng thái |
|---|---|---|---|---|---:|---|---|---|
| `W11.1` | `EP-05-S06` | Graph persistence, index và version/rebuild strategy | Q | Y | 5 | `W2.2`, `W4.4`, `W11.4` | Node/edge versioned; index report/type/relation; rebuild/cleanup được test | TODO |
| `W11.2` | `EP-05-S06` | Graph provenance/query API | Q | Y | 5 | `W11.1` | Node/edge mở ngược tới chunk/span/run; API không trả graph ngoài quyền | TODO |
| `W11.3` | `EP-05-S06` | Graph build worker và integration tests | Q | Y | 3 | `W11.1/2`, `W11.5` | Re-extraction idempotent; version không trộn; dangling/cross-report edge bị phát hiện | TODO |
| `W11.4` | `EP-05-S06` | Claim/entity/relation schema và ontology mapping | Y | Q | 5 | `W4.2`, `W9.5` | Claim/concept/method/result/conclusion/source và relation có định nghĩa/ví dụ | TODO |
| `W11.5` | `EP-05-S06` | Claim/entity/relation extraction pipeline | Y | Q | 5 | `W5.1/3`, `W11.4` | Structured output validate; confidence/model/prompt/source span được lưu | TODO |
| `W11.6` | `EP-05-S06` | Sample graph QA và extraction error analysis | Y | Q | 3 | `W11.2/5` | Graph mẫu review thủ công; precision sample và taxonomy lỗi extraction | TODO |

**Tải kế hoạch:** Q = 13 SP, Y = 13 SP.

### Tuần 12 — 24/10 đến 30/10/2026

**Milestone:** GRAPH Retrieval và LOCAL/GRAPH Router v1 hoàn tất.

| ID | Backlog | Work package | Owner | Review | SP | Phụ thuộc | Đầu ra/DoD riêng | Trạng thái |
|---|---|---|---|---|---:|---|---|---|
| `W12.1` | `EP-05-S07` | Graph retrieval service | Q | Y | 5 | `W11.1`, `W12.4` | Nhận seed/config và trả ranked evidence path có provenance | TODO |
| `W12.2` | `EP-05-S07` | Router service integration và LOCAL fallback | Q | Y | 5 | `W10.4`, `W12.1/5` | LOCAL/GRAPH/SELECTIVE có reason; graph lỗi fail-safe sang LOCAL/CANNOT_ASSESS | TODO |
| `W12.3` | `EP-05-S07`, `EP-09-S04` | Graph performance, cache và regression tests | Q | Y | 3 | `W12.1/2` | Đo size/latency; cache version-aware; stale/cross-report graph test đạt | TODO |
| `W12.4` | `EP-05-S07` | Seed selection và Personalized PageRank | Y | Q | 5 | `W11.4–6` | Seed từ checklist/claim; PPR deterministic theo config; lưu node contribution | TODO |
| `W12.5` | `EP-05-S07` | Multi-hop evidence ranking và path constraints | Y | Q | 5 | `W12.4` | Path giới hạn hop/không lặp; rank kết hợp relevance/path/provenance rõ | TODO |
| `W12.6` | `EP-05-S07` | Graph cases và router-policy evaluation | Y | Q | 3 | `W9.5`, `W12.2/5` | Tiêu chí nhiều phần; so LOCAL/GRAPH; ghi routing error và latency | TODO |

**Tải kế hoạch:** Q = 13 SP, Y = 13 SP.

### Tuần 13 — 31/10 đến 06/11/2026

**Milestone:** Evidence-grounded Assessment Engine v1 đạt `G-06`.

| ID | Backlog | Work package | Owner | Review | SP | Phụ thuộc | Đầu ra/DoD riêng | Trạng thái |
|---|---|---|---|---|---:|---|---|---|
| `W13.1` | `EP-05-S08/04` | Assessment orchestration, result persistence và review API | Q | Y | 5 | `W10.1`, `W12.2`, `W13.4` | Chạy rubric version cố định; lưu checklist/evidence/rationale/score proposal | TODO |
| `W13.2` | `EP-05-S08` | Consistency validator và CANNOT_ASSESS manual route | Q | Y | 5 | `W13.1/5` | Bắt status–score/rule conflict; insufficient evidence vào hàng review | TODO |
| `W13.3` | `EP-05-S08/04` | Assessment integration, deterministic rerun và RBAC tests | Q | Y | 3 | `W13.1/2` | Partial failure, stale version, rerun và authorization được test | TODO |
| `W13.4` | `EP-05-S08` | Evidence-grounded verifier và rationale | Y | Q | 5 | `W10.5`, `W12.5` | Rationale dẫn đúng evidence ID; unsupported claim bị validator chặn | TODO |
| `W13.5` | `EP-05-S08` | Deterministic criterion/overall scoring rules | Y | Q | 5 | `W9.5`, `W13.4` | Cùng input cho cùng score; weight/rounding/missing-evidence rule rõ | TODO |
| `W13.6` | `EP-05-S05/08` | Evaluation sample và consistency analysis | Y | Q | 3 | `W13.1–5` | So lecturer label; báo status metric, score difference và lỗi rationale | TODO |

**Tải kế hoạch:** Q = 13 SP, Y = 13 SP.

### Tuần 14 — 07/11 đến 13/11/2026

**Milestone:** Targeted Question Generation v1 được giảng viên kiểm duyệt.

| ID | Backlog | Work package | Owner | Review | SP | Phụ thuộc | Đầu ra/DoD riêng | Trạng thái |
|---|---|---|---|---|---:|---|---|---|
| `W14.1` | `EP-08-S01` | Findings adapter từ similarity/rubric/evidence | Q | Y | 5 | `W8.3`, `W13.1` | Chuẩn hóa issue/criterion/evidence/severity/source cho generator | TODO |
| `W14.2` | `EP-08-S01/02` | Question API, provenance, version và audit | Q | Y | 5 | `W14.1/4` | Câu liên kết issue/evidence/purpose; create/edit/approve audit đầy đủ | TODO |
| `W14.3` | `EP-01-S04` | Go/no-go decision cho auxiliary style/AI-writing warning | Q | Y | 3 | `G-04`, `G-06` | Ghi capacity/data/ethics decision; `EP-06-S03` vẫn ICEBOX nếu không Go; nếu mở phải tách khỏi điểm, có disclaimer và limitation | TODO |
| `W14.4` | `EP-08-S01` | Grounded question schema/prompt và generation | Y | Q | 5 | `W5.1/3`, `W14.1` | Câu có purpose/answerability/evidence; output ngoài schema bị loại | TODO |
| `W14.5` | `EP-08-S02` | Lecturer question review/edit UI | Y | Q | 5 | `W14.2/4` | Xem căn cứ, edit/reject/approve; draft chưa duyệt không được dùng | TODO |
| `W14.6` | `EP-08-S02`, `EP-10-S04` | Question quality test set và pilot | Y | Q | 3 | `W14.4/5` | Chấm relevance/grounding/answerability/usefulness; lưu accept/edit/reject | TODO |

**Tải kế hoạch:** Q = 13 SP, Y = 13 SP.

### Tuần 15 — 14/11 đến 20/11/2026

**Milestone:** Human-in-the-loop dashboard, Feedback Log và export v1.

| ID | Backlog | Work package | Owner | Review | SP | Phụ thuộc | Đầu ra/DoD riêng | Trạng thái |
|---|---|---|---|---|---:|---|---|---|
| `W15.1` | `EP-09-S02/07` | Unified result API và Feedback Log | Q | Y | 5 | `W8.3`, `W13.1`, `W14.2` | Tổng hợp module output; edit giữ original/before-after/actor/time/reason | TODO |
| `W15.2` | `EP-09-S03` | Final report/export service | Q | Y | 5 | `W15.1` | HTML/PDF/JSON có version/evidence/review/disclaimer; fixture ổn định | TODO |
| `W15.3` | `EP-02-S08`, `EP-09-S02/03/06/07` | Lecturer workflow RBAC/audit và lifecycle archive/delete orchestration | Q | Y | 3 | `W2.6`, `W15.1/2` | Accept/Edit/Reject/publish/archive/delete đúng quyền và audit; purpose/retention/approver gate được enforce; cascade job file/chunk/vector/graph/result/cache idempotent; giữ AI suggestion gốc | TODO |
| `W15.4` | `EP-09-S02` | Evaluation Dashboard UI | Y | Q | 5 | `W15.1` | Similarity/rubric/evidence/rationale/score/question nhất quán | TODO |
| `W15.5` | `EP-05-S04`, `EP-09-S02` | Accept/Edit/Reject interactions và concurrent-state handling | Y | Q | 5 | `W15.3/4` | Review từng finding/checklist; xử lý unsaved/error/concurrent edit | TODO |
| `W15.6` | `EP-09-S02`, `EP-10-S04` | Usability/accessibility smoke và export-view test | Y | Q | 3 | `W15.4/5` | Lecturer flow hoàn tất; keyboard/focus/empty/error và rendered export được kiểm | TODO |

**Tải kế hoạch:** Q = 13 SP, Y = 13 SP.

### Tuần 16 — 21/11 đến 27/11/2026

**Milestone:** Release Candidate 1 và feature freeze.

| ID | Backlog | Work package | Owner | Review | SP | Phụ thuộc | Đầu ra/DoD riêng | Trạng thái |
|---|---|---|---|---|---:|---|---|---|
| `W16.1` | `EP-11-S05` | E2E orchestration upload→reviewed final report | Q | Y | 5 | `G-04`, `G-06`, `W15.2/5` | Một run tạo parse, similarity, assessment, question và reviewed export | TODO |
| `W16.2` | `EP-09-S01`, `EP-11-S05` | Retry/cache/progress/error hardening | Q | Y | 3 | `W16.1` | Retry idempotent; cache version-aware; partial failure/resume được test | TODO |
| `W16.3` | `EP-11-S01/02/05` | Backend/system/RBAC/security test suite | Q | Y | 5 | `W16.1/2` | Happy/error/cross-role/upload/parser/model/graph; không còn Critical mở | TODO |
| `W16.4` | `EP-11-S04`, `EP-12-S02` | RC1 deployment và operations guide | Q | Y | 3 | `W16.3` | Clean install, healthcheck, backup/rollback, known issues | TODO |
| `W16.5` | `EP-11-S05` | E2E/UAT scenario suite cho ba actor | Y | Q | 5 | `W16.1` | Bao phủ no-evidence, partial failure và manual review | TODO |
| `W16.6` | `EP-11-S01/02` | AI/retrieval/graph regression và adversarial suite | Y | Q | 5 | `W16.1` | Fixed dataset bắt schema/provenance/quality regression ngoài tolerance | TODO |
| `W16.7` | `EP-11-S05` | Defect triage và feature-freeze evidence | Y | Q | 3 | `W16.3/5/6` | Lỗi có severity/owner; P1/P2 defer bằng quyết định | TODO |
| `W16.8` | `EP-12-S01` | Bản nháp chương hiện thực và kiểm thử | Y | Q | 3 | `W16.1–7` | Mô tả khớp code, diagram, test report và RC1 thực tế | TODO |

**Tải kế hoạch:** Q = 16 SP, Y = 16 SP.

### Tuần 17 — 28/11 đến 04/12/2026

**Milestone:** Dataset, ground truth và protocol thực nghiệm được freeze (`G-08`).

| ID | Backlog | Work package | Owner | Review | SP | Phụ thuộc | Đầu ra/DoD riêng | Trạng thái |
|---|---|---|---|---|---:|---|---|---|
| `W17.1` | `EP-01-S02`, `EP-10-S01` | Dataset manifest, version, checksum, rights state và split | Y | Q | 5 | `W2.6`, `W6.4`, `W10.6` | Train/validation/test có provenance và approval state; split theo document/source; validator loại sample chưa duyệt | TODO |
| `W17.2` | `EP-10-S06` | Metric/statistics scripts và unit tests | Q | Y | 5 | `W17.1` | Recall/MRR/nDCG/P/R/F1/evidence/agreement chạy tự động và đúng case biết trước | TODO |
| `W17.3` | `EP-10-S01/06` | Leakage, duplicate và label-quality audit | Q | Y | 3 | `W17.1/2` | Near-duplicate/overlap được báo; final test khóa trước run chính | TODO |
| `W17.4` | `EP-10-S05` | Clean reproduction dry run | Q | Y | 3 | `W17.1–3` | Từ manifest/config sinh lại một bảng pilot trên môi trường sạch | TODO |
| `W17.5` | `EP-04-S01`, `EP-10-S01` | Similarity ground-truth QA, adjudication và freeze | Q | Y | 5 | `W6.4`, `W8.4`, `W17.1` | Bốn nhãn/source span đầy đủ; duplicate/leakage flags xử lý; ambiguous case có adjudication; reviewer Y ký freeze | TODO |
| `W17.6` | `EP-10-S01` | Hoàn tất report–rubric–checklist annotation | Y | Q | 5 | `W10.6`, `W13.6` | MET/UNMET/CANNOT_ASSESS, evidence span và lecturer note đầy đủ | TODO |
| `W17.7` | `EP-10-S01` | Annotation guideline, QA và inter-rater review | Y | Q | 3 | `W17.5/6` | Guideline có example; agreement và cách xử lý bất đồng được báo | TODO |
| `W17.8` | `EP-01-S02`, `EP-10-S01` | Dataset card, rights/ethics và limitations | Y | Q | 3 | `W17.1`, `W17.5–7` | Nguồn/quyền/population/bias/retention/giới hạn rõ | TODO |

**Tải kế hoạch:** Q = 16 SP, Y = 16 SP.

### Tuần 18 — 05/12 đến 11/12/2026

**Milestone:** Kết quả thực nghiệm RQ1 được freeze.

| ID | Backlog | Work package | Owner | Review | SP | Phụ thuộc | Đầu ra/DoD riêng | Trạng thái |
|---|---|---|---|---|---:|---|---|---|
| `W18.1` | `EP-10-S02` | Chạy BM25, Dense và Hybrid locked experiments | Q | Y | 5 | `G-08`, `W17.1–4` | Cùng split/hardware/config; raw result và stage latency có run ID | TODO |
| `W18.2` | `EP-10-S02` | Chạy reranker/full detection và ablation | Q | Y | 5 | `W18.1` | So RRF/reranker/classifier/quote handling; không tune trên test | TODO |
| `W18.3` | `EP-10-S02/05` | Statistics, latency/resource và error artifact RQ1 | Q | Y | 3 | `W18.1/2` | Recall@K/MRR/nDCG/F1 từng lớp, latency/RAM và taxonomy lỗi | TODO |
| `W18.4` | `EP-10-S02/05` | Independent result/reproduction audit | Y | Q | 5 | `W18.1–3` | Đối chiếu manifest–raw–table; rerun sample và ghi sai khác | TODO |
| `W18.5` | `EP-10-S02` | Bảng/biểu và qualitative success/failure examples | Y | Q | 5 | `W18.3/4` | Hình/bảng sinh từ script; ví dụ ẩn danh và truy vết được | TODO |
| `W18.6` | `EP-12-S01` | Viết kết quả/thảo luận RQ1 | Y | Q | 3 | `W18.4/5` | Claim không vượt dữ liệu; nêu uncertainty, limitation và config đề xuất | TODO |

**Tải kế hoạch:** Q = 13 SP, Y = 13 SP.

### Tuần 19 — 12/12 đến 18/12/2026

**Milestone:** Kết quả thực nghiệm RQ2 được freeze.

| ID | Backlog | Work package | Owner | Review | SP | Phụ thuộc | Đầu ra/DoD riêng | Trạng thái |
|---|---|---|---|---|---:|---|---|---|
| `W19.1` | `EP-10-S03` | Locked assessment runner và performance capture | Q | Y | 5 | `G-06`, `G-08`, `W17.1–4` | Cùng report/rubric/model; prompt/config/evidence/run/latency/resource đầy đủ | TODO |
| `W19.2` | `EP-10-S03` | Evidence metric và score/agreement implementation | Q | Y | 5 | `W17.2`, `W19.1` | Evidence Recall/Precision, three-state metric và agreement có test | TODO |
| `W19.3` | `EP-10-S03/05` | Independent consistency/error audit | Q | Y | 3 | `W19.1/2` | Kiểm evidence–rationale–status–score và lỗi LOCAL/GRAPH/router | TODO |
| `W19.4` | `EP-10-S03` | Chạy No Retrieval và LOCAL locked configurations | Y | Q | 5 | `W17.6`, `W19.1` | Cùng sample; lưu unsupported rationale, score và evidence outcome | TODO |
| `W19.5` | `EP-10-S03` | Chạy selective LOCAL/GRAPH và ablation | Y | Q | 5 | `W12.6`, `W19.4` | Báo graph gain/latency/routing failure trên cùng protocol | TODO |
| `W19.6` | `EP-12-S01` | Viết kết quả/thảo luận RQ2 | Y | Q | 3 | `W19.2–5` | Metric/agreement/error/limitation đầy đủ; không overclaim tác động | TODO |

**Tải kế hoạch:** Q = 13 SP, Y = 13 SP.

### Tuần 20 — 19/12 đến 25/12/2026

**Milestone:** Đánh giá câu hỏi, Feedback Log và tính hữu ích hệ thống hoàn tất.

| ID | Backlog | Work package | Owner | Review | SP | Phụ thuộc | Đầu ra/DoD riêng | Trạng thái |
|---|---|---|---|---|---:|---|---|---|
| `W20.1` | `EP-10-S04`, `EP-09-S07` | Study tooling, telemetry export và privacy controls | Q | Y | 5 | `W15.1`, `W17.8` | Form/rating/log dùng participant/sample ID ẩn danh; consent/access rõ | TODO |
| `W20.2` | `EP-08-S02`, `EP-10-S04` | Quantitative question/support evaluation pipeline | Q | Y | 5 | `W20.1/4` | Tính relevance/evidence-grounding/answerability/usefulness, A/E/R và usability từ raw artifact | TODO |
| `W20.3` | `EP-08-S02`, `EP-09-S07`, `EP-10-S04/05` | Question/support regression và reproducible artifact package | Q | Y | 3 | `W14.6`, `W15.6`, `W20.2` | Question/evidence/feedback provenance giữ nguyên; raw→table/plot tái sinh; cảnh báo hỗ trợ tách theo trạng thái đã/không triển khai | TODO |
| `W20.4` | `EP-08-S02`, `EP-10-S04` | Lecturer expert/usability evaluation | Y | Q | 5 | `W14.6`, `W15.6`, `W20.1` | Protocol cố định; người đánh giá làm task/rating trên sample | TODO |
| `W20.5` | `EP-09-S07`, `EP-10-S04` | Feedback Log và qualitative thematic analysis | Y | Q | 5 | `W20.4` | Lý do accept/edit/reject được mã hóa; example ẩn danh/review chéo | TODO |
| `W20.6` | `EP-12-S01` | Viết kết quả hỗ trợ, hạn chế và hướng cải tiến | Y | Q | 3 | `W20.2/5` | Phân biệt kết quả đo, cảm nhận người dùng và phần chưa đủ evidence | TODO |

**Tải kế hoạch:** Q = 13 SP, Y = 13 SP.

### Tuần 21 — 26/12/2026 đến 01/01/2027

**Milestone:** Release Candidate 2 đạt ngưỡng hiệu năng, bảo mật và tái lập (`G-09`).

| ID | Backlog | Work package | Owner | Review | SP | Phụ thuộc | Đầu ra/DoD riêng | Trạng thái |
|---|---|---|---|---|---:|---|---|---|
| `W21.1` | `EP-11-S03` | Profiling latency/throughput/RAM/VRAM theo stage | Q | Y | 5 | `G-07`, `W18.3`, `W19.3`, `W20.3` | p50/p95 và bottleneck có profile; hardware/workload ghi rõ | TODO |
| `W21.2` | `EP-11-S03` | Tối ưu local AI, lexical/vector và reranker | Q | Y | 5 | `W21.1` | Cải thiện metric/resource; quality regression trong tolerance | TODO |
| `W21.3` | `EP-11-S03` | Tối ưu graph/cache/queue và resilience | Q | Y | 3 | `W21.1` | Cache/version/retry không đổi result; benchmark trước/sau truy vết | TODO |
| `W21.4` | `EP-09-S06`, `EP-11-S01/02/03` | Lifecycle cascade, security/privacy và backup/restore closeout | Q | Y | 3 | `W15.3`, `W16.3`, `W17.8` | Archive/delete E2E loại file/chunk/vector/graph/result/cache khỏi active store theo policy; tombstone/audit không chứa nội dung; backup expiry/restore diễn tập; upload/isolation/log review đạt, không còn Critical/High mở | TODO |
| `W21.5` | `EP-11-S03` | Quality regression trên RC2 | Y | Q | 5 | `W21.2/3` | Parser/similarity/assessment/question fixed suite đạt threshold | TODO |
| `W21.6` | `EP-09-S04`, `EP-11-S03` | Resource benchmark và configuration recommendation | Y | Q | 5 | `W21.1–3` | Bảng latency/throughput/RAM/VRAM; khóa config demo/experiment | TODO |
| `W21.7` | `EP-11-S04` | Defect verification và known-issues review | Y | Q | 3 | `W21.4/5` | Lỗi có evidence đóng hoặc mức chấp nhận/workaround | TODO |
| `W21.8` | `EP-10-S05`, `EP-11-S04` | Reproducibility/configuration freeze | Y | Q | 3 | `W21.5–7` | Khóa commit/dependency/model/index/config; rerun trong tolerance | TODO |

**Tải kế hoạch:** Q = 16 SP, Y = 16 SP.

### Tuần 22 — 02/01 đến 08/01/2027

**Milestone:** Luận văn đầy đủ phiên bản 1 gửi GVHD.

| ID | Backlog | Work package | Owner | Review | SP | Phụ thuộc | Đầu ra/DoD riêng | Trạng thái |
|---|---|---|---|---|---:|---|---|---|
| `W22.1` | `EP-12-S01` | Viết chương kiến trúc, hiện thực và tích hợp | Q | Y | 5 | `G-07`, `G-09` | Khớp code/diagram/API hiện hành; decision có lý do | TODO |
| `W22.2` | `EP-12-S01` | Viết phần thực nghiệm Similarity và hiệu năng | Q | Y | 5 | `W18.3–5`, `G-09` | Bảng/claim liên kết raw artifact; protocol/ablation đủ tái lập | TODO |
| `W22.3` | `EP-12-S01` | Đồng bộ UML, architecture, schema và API | Q | Y | 3 | `W22.1` | Không còn tên/state/relation lỗi thời so với RC2 | TODO |
| `W22.4` | `EP-12-S02` | Hướng dẫn cài đặt, triển khai và API | Q | Y | 3 | `W21.8` | Người mới dựng môi trường sạch và chạy fixture/demo | TODO |
| `W22.5` | `EP-12-S01` | Hoàn thiện tổng quan, cơ sở lý thuyết và phương pháp | Y | Q | 5 | `W1.3`, `G-08` | Citation đầy đủ; phương pháp/data/ethics khớp protocol freeze | TODO |
| `W22.6` | `EP-12-S01` | Viết kết quả Assessment và Lecturer Support | Y | Q | 5 | `W19.3–5`, `W20.2–5` | Bảng/error/feedback/limitation truy vết artifact | TODO |
| `W22.7` | `EP-10-S05`, `EP-12-S01` | Editorial, references và reproducibility appendix | Y | Q | 3 | `W22.1–6` | Thuật ngữ/số/citation/caption thống nhất; appendix map manifest/config | TODO |
| `W22.8` | `EP-12-S02` | Hướng dẫn sử dụng | Y | Q | 3 | `W15.4–6`, `G-09` | Upload/analysis/review/export/failure recovery có hướng dẫn/ảnh | TODO |

**Tải kế hoạch:** Q = 16 SP, Y = 16 SP.

### Tuần 23 — 09/01 đến 15/01/2027

**Milestone:** Release 1.0 và bộ bảo vệ bản nháp hoàn chỉnh (`G-10`).

| ID | Backlog | Work package | Owner | Review | SP | Phụ thuộc | Đầu ra/DoD riêng | Trạng thái |
|---|---|---|---|---|---:|---|---|---|
| `W23.1` | `EP-11-S04` | Xử lý feedback code/sản phẩm | Q | Y | 5 | `EXT:GVHD feedback`, `W22.1–8` | Mỗi góp ý có commit/status hoặc lý do; không mở scope mới | TODO |
| `W23.2` | `EP-11-S04` | Đóng gói Release 1.0 | Q | Y | 5 | `W21`, `W23.1` | Tag/source/migration/config/docs/checksum/release notes; không dữ liệu cấm | TODO |
| `W23.3` | `EP-12-S02` | Demo environment và demo script | Q | Y | 3 | `W23.2` | Chạy từ sạch, đúng thời lượng và dùng fixture hợp lệ | TODO |
| `W23.4` | `EP-10-S05`, `EP-12-S01` | Audit báo cáo–code–data–số liệu | Q | Y | 3 | `W22.7`, `W23.2` | Model/config/data/metric/số liệu khớp artifact khóa | TODO |
| `W23.5` | `EP-12-S01` | Xử lý feedback và hoàn thiện luận văn gần cuối | Y | Q | 5 | `EXT:GVHD feedback`, `W22.7` | Comment resolve/truy vết; số liệu chỉ đổi từ script/artifact | TODO |
| `W23.6` | `EP-12-S01` | Hoàn thiện contribution, kết luận và future work | Y | Q | 5 | `W18.6`, `W19.6`, `W20.6` | Không overclaim; phân biệt prototype/result/extension | TODO |
| `W23.7` | `EP-12-S02` | Slide bảo vệ bản nháp | Y | Q | 3 | `W23.5/6` | Problem–method–demo–result–limitation; số liệu thống nhất | TODO |
| `W23.8` | `EP-12-S02` | Video demo và bộ câu hỏi phản biện | Y | Q | 3 | `W23.3/7` | Không lộ secret/data; Q&A phủ contribution/metric/error/ethics | TODO |

**Tải kế hoạch:** Q = 16 SP, Y = 16 SP.

### Tuần 24 — 16/01 đến 22/01/2027

**Milestone:** Submission readiness; không mở feature mới (`G-11`).

| ID | Backlog | Work package | Owner | Review | SP | Phụ thuộc | Đầu ra/DoD riêng | Trạng thái |
|---|---|---|---|---|---:|---|---|---|
| `W24.1` | `EP-11-S04` | Final functional/regression test | Q | Y | 5 | `W23.2` | Demo/fixed suite đạt; chỉ sửa defect | TODO |
| `W24.2` | `EP-11-S03`, `EP-12-S03` | Backup/restore và checksum verification | Q | Y | 5 | `W24.1` | Backup độc lập; restore thử thành công; checksum khớp | TODO |
| `W24.3` | `EP-12-S03` | Submission/release package | Q | Y | 3 | `W24.1/2` | Gói mở được, quyền/link đúng, loại dữ liệu không được phép | TODO |
| `W24.4` | `EP-12-S02/03` | Offline demo/fallback readiness | Q | Y | 3 | `W24.1–3` | Có demo offline và phương án khi model/service lỗi | TODO |
| `W24.5` | `EP-12-S01/03` | Final formatting, citation và similarity review | Y | Q | 5 | `W23.5` | Đúng mẫu Khoa; citation hợp lệ; xử lý đoạn trùng không hợp lệ | TODO |
| `W24.6` | `EP-12-S02/03` | Hoàn thiện báo cáo, slide và video cuối | Y | Q | 5 | `W24.5`, `W23.7/8` | Ba artifact dùng cùng số liệu/version và mở/chạy được | TODO |
| `W24.7` | `EP-12-S03` | Forms, inventory và submission checklist | Y | Q | 3 | `W24.2/6` | Đủ biểu mẫu/xác nhận/tên file/danh mục thành phần | TODO |
| `W24.8` | `EP-12-S02/03` | Rehearsal, Q&A và defense handoff | Y | Q | 3 | `W24.4/6` | Đúng thời lượng; phân vai; lỗi rehearsal được ghi và sửa | TODO |

**Tải kế hoạch:** Q = 16 SP, Y = 16 SP.

**Closure 23/01/2027:** Q lưu submission receipt gồm timestamp, kênh/người
nhận, inventory/link hoặc mã biên nhận và checksum; Y đối soát artifact. Chỉ
sau bước này `G-11=PASS`.

---

## 8. Tổng hợp tải kế hoạch

| Tuần | Q (SP) | Y (SP) | Milestone/Gate |
|---:|---:|---:|---|
| 1 | 8 | 8 | Scope/planning baseline |
| 2 | 13 | 13 | `G-02` Architecture/Data baseline |
| 3 | 13 | 13 | Platform core |
| 4 | 13 | 13 | Document Processing v1 |
| 5 | 13 | 13 | `G-03` Model/parse feasibility |
| 6 | 13 | 13 | BM25/Dense baselines |
| 7 | 13 | 13 | Hybrid Retrieval v1 |
| 8 | 13 | 13 | `G-04` Similarity v1 |
| 9 | 13 | 13 | Rubric Compiler v1 |
| 10 | 13 | 13 | `G-05` LOCAL Assessment |
| 11 | 13 | 13 | Evidence Graph v1 |
| 12 | 13 | 13 | Graph Retrieval v1 |
| 13 | 13 | 13 | `G-06` Assessment Engine |
| 14 | 13 | 13 | Question Generation v1 |
| 15 | 13 | 13 | Human-in-the-loop v1 |
| 16 | 16 | 16 | `G-07` RC1/Feature freeze |
| 17 | 16 | 16 | `G-08` Dataset freeze |
| 18 | 13 | 13 | RQ1 result freeze |
| 19 | 13 | 13 | RQ2 result freeze |
| 20 | 13 | 13 | Support evaluation freeze |
| 21 | 16 | 16 | `G-09` RC2 |
| 22 | 16 | 16 | Thesis v1 |
| 23 | 16 | 16 | `G-10` Release 1.0 |
| 24 | 16 | 16 | `G-11` Submission readiness |
| **Tổng** | **325** | **325** | Cân bằng tuyệt đối theo SP |

W16–W17 và W21–W24 là tuần gate/release nên tải cao hơn. Đây không phải lý do
để chuyển feature mới vào các tuần đó. P1/P2 ngoài WBS không giải phóng tải
325 SP; nếu velocity thấp, phải nhập remaining SP và rebaseline. Có thể
timebox/defer auxiliary-warning decision, UI polish hoặc export variant không
chặn vertical slice; không cắt data-rights, security, provenance, hai thực
nghiệm chính hay submission artifact.

## 9. Critical path và dependency rule

```text
W01 Scope/data
→ W02 Architecture/schema/API
→ W03 Upload/queue
→ W04 Parse/chunk/provenance
→ W05 Model/index
→ W06–08 Similarity
→ W09–10 LOCAL Assessment
→ W11–13 Graph Assessment
→ W14–15 Lecturer Support
→ W16 RC1
→ W17 Dataset freeze
→ W18–20 Experiments
→ W21 RC2
→ W22 Thesis v1
→ W23 Release 1.0
→ W24 Submission readiness → 23/01 receipt/closure
```

Dependency mặc định là `AND`; lựa chọn thay thế phải ghi rõ `OR`.

- Dạng rút gọn dùng chung prefix: `W2.2/3` = `W2.2 AND W2.3`;
  `EP-02-S01/04` = `EP-02-S01 AND EP-02-S04`.
- Dấu `–` là dải inclusive và chỉ dùng giữa ID cùng loại. Dependency rộng như
  `W03–W15`, `Core epics` hoặc `model gate` phải thay bằng gate/ID cụ thể trước
  khi work package vào `Ready`.
- Dependency ngoài repository ghi `EXT:<tên>` và phải có owner/evidence trong
  issue tương ứng.

- Không bắt đầu experiment chính thức trước `G-08`.
- Không bắt đầu Graph Retrieval nếu graph provenance W11 chưa đạt.
- Không để UI chờ backend: dùng fixture bám API contract; contract thay đổi phải
  cập nhật cả fixture và consumer trong cùng tuần.
- Item bị block quá một ngày phải ghi nguyên nhân và chuyển sang task không phụ
  thuộc; không âm thầm đổi status/date.

### 9.1. Traceability câu hỏi nghiên cứu

| Hướng/RQ | Product Backlog | Build/Evaluate | Evidence chính |
|---|---|---|---|
| RQ1 — Similarity Retrieval/Detection | `EP-04-S01–04`, `EP-04-S09–11`, `EP-10-S02` | W06–W08; W18 | Recall@K, MRR/nDCG, F1 theo loại, latency/RAM, ablation/error analysis |
| RQ2 — Evidence-grounded Assessment | `EP-05-S01–09`, `EP-10-S03` | W09–W13; W19 | Evidence Recall/Precision, MET/UNMET/CANNOT_ASSESS, score agreement, rationale support |
| RQ3 — Targeted Questions (bổ sung) | `EP-08-S01/02`, `EP-09-S07`, `EP-10-S04` | W14–W15; W20 | Relevance, evidence-grounding, answerability, usefulness và Accept/Edit/Reject |

## 10. Quy tắc phối hợp và cập nhật tiến độ

1. Mỗi người giữ tối đa một work package chính `IN PROGRESS` tại một thời điểm.
2. Owner mở PR/artifact; reviewer còn lại duyệt. Không tự merge task 5 SP.
3. Mỗi đầu tuần chọn task theo WBS/dependency; mỗi cuối tuần demo artifact và
   cập nhật actual/blocker.
4. Cột `% hoàn thành` trong Excel tính theo output weight:
   `0%` chưa có; `25%` draft/skeleton; `50%` main flow chạy; `75%` có test và
   review nhưng còn lỗi/xác nhận; `100%` đạt DoD/gate.
5. Mọi model/index/prompt/rubric/dataset thay đổi phải lưu version; bảng kết quả
   chỉ sinh từ run artifact.
6. Dữ liệu thật, PII, secret, model weight và log không commit.
7. Viết chương liên quan trong cùng tuần tạo artifact; W22 là tích hợp/chỉnh sửa,
   không phải lần đầu viết toàn bộ luận văn.
8. Sau W16 chỉ sửa lỗi, thực nghiệm, tối ưu và tài liệu; extension cần change
   decision rõ.

## 11. Việc cần làm ngay để đóng recovery W01–W02

| Thứ tự | Work package | Owner | Deadline recovery | Kết quả bắt buộc |
|---:|---|---|---|---|
| 1 | Review hai file planning và ghi `remaining SP` cho W01–W03 | Q + Y | 22/08 | Q/Y xác nhận owner/reviewer; tổng carry-over + W03 commit không vượt 13 SP/người |
| 2 | `W2.2` MongoDB/index ADR + data/lifecycle model | Q | 23/08 | ADR, collection/schema/index/data dictionary và lifecycle fields đủ mở vertical slice |
| 3 | `W2.5` Rubric Template + guideline v1 | Y | 23/08 | Template, rubric/checklist example, annotation/adjudication roles |
| 4 | `W2.3` API contract v1 | Q | 25/08 | Contract cho vertical slice W03–W04 |
| 5 | `W2.4` Wireframe/permission | Y | 25/08 | Upload→analysis→review cùng loading/error/permission states |
| 6 | `W2.6` Rights dossier + dataset/protocol/sample corpus | Y | 25/08 | Quyền/purpose/retention cùng label/split/metric/provenance và sample hợp lệ |
| 7 | Review `G-02`; chỉ pull phần W03 còn vừa capacity | Q + Y | 25/08 | Decision log; dependency Pass mới chuyển `Ready`; skeleton độc lập có thể chạy trước |
| 8 | Đồng bộ `W1.1`, đóng `W1.2/W1.5/W1.6` theo evidence thật | Q + Y | 28/08 | SRS/UC/README đúng scope; biên bản/board/runtime-or-status/Chương 1 có review |
| 9 | Đóng phần carry-over còn lại hoặc lập rebaseline | Q + Y | 28/08 | Artifact đạt DoD; phần chưa đạt có blocker/new target/change log, không ghi hoàn thành giả |

## 12. Change Log và phê duyệt

| Phiên bản | Ngày | Thay đổi |
|---|---|---|
| 1.0 | 21/08/2026 | Tách WBS khỏi Product Backlog; phân rã đúng 24 tuần Excel/phạm vi 2 hướng chính + 1 bổ sung; gán owner/reviewer Q/Y; recovery trừ carry-over vào capacity; bổ sung gate evidence, data-rights/security/lifecycle và closure 23/01; cân bằng 325 SP/người |

| Vai trò | Họ tên | Quyết định | Ngày |
|---|---|---|---|
| Nhóm trưởng | Nguyễn Trần Ngọc Quý | Chờ review/ký |  |
| Thành viên | Võ Thị Kim Yến | Chờ review/ký |  |
| GVHD | Vũ Đình Hồng | Chờ xác nhận baseline |  |
