# WBS VÀ PHÂN CÔNG NHÂN SỰ

## Evidence-Grounded Plagiarism Checking and Student Report Assessment

| Thuộc tính | Giá trị |
|---|---|
| Phiên bản | 1.7 |
| Ngày lập baseline | 21/08/2026 |
| Ngày cập nhật tiến độ/reforecast | 19/10/2026 |
| Thời gian dự án | 08/08/2026–22/01/2027 (24 tuần) |
| Hạn nộp | 23/01/2027 |
| Thành viên 1 | Nguyễn Trần Ngọc Quý — 523H0087 — Nhóm trưởng |
| Thành viên 2 | Võ Thị Kim Yến — 52200229 |
| GVHD | Vũ Đình Hồng |
| Nguồn lịch | `Schedule_KLTN_Evidence_Grounded.xlsx`, sheet `FILE KẾ HOẠCH MẪU`; SHA-256 `548f068bdc71d022e29f8def983b10f689d14606cc0db6d33c0783189f318984` |
| Product Backlog | [`PRODUCT_BACKLOG.md`](./PRODUCT_BACKLOG.md) |
| Actual W1–W11 | [`W1-W11_STATUS_2026-10-19.md`](./W1-W11_STATUS_2026-10-19.md) |

WBS này lấy thứ tự công việc và sản phẩm đầu ra trong file Excel làm baseline.
Các roadmap cũ lệch Excel ở W06–W15 không còn là nguồn lịch chuẩn. Các mốc đã
qua được giữ nguyên để thể hiện độ trễ; không sửa ngày nhằm làm đẹp tiến độ.
Phiên bản 1.1 ghi nhận actual đến hết ngày 03/09/2026 và bổ sung reforecast;
phiên bản 1.2 bổ sung evidence kiến trúc `W2.1` ở trạng thái chờ review; phiên
bản 1.3 ghi nhận PR `W2.1` và design artifact `W2.2`; phiên bản 1.4–1.5 ghi
nhận API Contract `W2.3` và việc approve/merge design baseline `W2.2`; phiên
bản 1.6 đối chiếu lại toàn bộ repository ngày 12/10/2026 và reforecast W10–W17
để hoàn thành hai pipeline chính; phiên bản 1.7 ghi nhận technical slice chạy
được của cả hai pipeline, app local, output contract, golden benchmark và các
artifact thiết kế đã tích hợp vào working tree ngày 19/10/2026. Baseline ngày
21/08/2026 vẫn được giữ để đối chiếu schedule variance.

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
- `CONDITIONAL`: nằm trong scope bổ sung nhưng chỉ được hoán đổi vào capacity
  khi gate/cut-line cho phép; không cộng thêm trên trần tuần.
- `CARRY-OVER`: quá hạn tuần gốc và được chuyển có kiểm soát sang cửa sổ phục
  hồi, không thay ngày baseline.

`Ready` là cột workflow, không phải giá trị trạng thái WBS. Work package ở cột
`Ready` vẫn mang `TODO` cho đến khi owner bắt đầu và có evidence đầu tiên.

### 2.4. Hardware baseline

| Thành viên/mục đích | Thiết bị | CPU/SoC | Bộ nhớ | GPU | Hệ điều hành | Trạng thái |
|---|---|---|---:|---|---|---|
| Q — phát triển/tích hợp | MacBook Pro 14-inch (11/2024) | Apple M4 | 16 GB unified memory | Apple integrated GPU; không có card rời | macOS Sequoia 15.6.1 | Đã xác nhận 21/08/2026 |
| Y — phát triển và benchmark local sơ bộ | Không yêu cầu ở W01 | Không yêu cầu ở W01 | 16 GB | Không có card rời | Không yêu cầu ở W01 | Đã xác nhận cấu hình tối thiểu 21/08/2026; benchmark thực tế tại W05 |
| Máy demo/benchmark chính thức | Chưa chốt | — | — | — | — | Khóa tại `G-03` sau benchmark thực tế |

Không lưu serial number hoặc định danh thiết bị trong repository. Với máy M4
16 GB, lựa chọn model/quantization/context chỉ được chốt sau benchmark W05;
không suy ra khả năng chạy model từ tên chip.

### 2.5. GitHub workflow baseline

| Artifact | Evidence | Trạng thái cập nhật |
|---|---|---|
| Quy ước branch/commit/PR/review | [`CONTRIBUTING.md`](../../CONTRIBUTING.md) và [PR template](../../.github/pull_request_template.md) | Đã tạo và merge qua PR #2; PR chưa có approval chéo nên chưa đạt DoD `W1.5` |
| Issue board | [KLTN Evidence-Grounded Delivery](https://github.com/users/ngwine/projects/2) | Đã liên kết repository; có 6 trạng thái và field truy vết |
| Labels | [Danh sách labels](https://github.com/ngwine/evidence-grounded-report-assessment/labels) | Đã tạo type/component/priority/risk |
| Milestones | [W01–W24](https://github.com/ngwine/evidence-grounded-report-assessment/milestones) | Đã tạo theo ngày kết thúc từng tuần trong WBS |
| Review/closure `W1.5` | [Issue #1](https://github.com/ngwine/evidence-grounded-report-assessment/issues/1), [PR #2](https://github.com/ngwine/evidence-grounded-report-assessment/pull/2) | Issue đã đóng và PR đã merge; còn thiếu approval/comment xác nhận của Y nên giữ `CARRY-OVER` |

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

| Gate | Tuần baseline | Forecast v1.7 | Điều kiện Pass | Nếu Fail | Status cập nhật | Evidence hiện tại | Approver | Decision date |
|---|---:|---:|---|---|---|---|---|---|
| `G-01 Scope/Data` | W01–W02 | EXT:GVHD/data owner | Scope/RQ/actor/capacity và quyền dùng sample có quyết định | Không đưa dữ liệu chưa rõ quyền vào hệ thống; mở blocker có owner | OPEN | Scope/SRS/Use Case đã đồng bộ qua PR #8; quyền dùng PAN theo mục đích, consent/ẩn danh/retention cho báo cáo in-domain và xác nhận GVHD chưa đóng | Q + Y + GVHD | — |
| `G-02 Architecture` | W02 | 23/10 | C4, MongoDB/index decision, schema, API, wireframe, rubric/protocol v1 được review | Chỉ dựng skeleton độc lập với decision; carry-over trừ vào capacity tuần recovery | OPEN | `W2.1` và `W2.2` đã merge; API/OpenAPI, UX P0 và rubric/annotation v1 đã được tích hợp vào working tree. Còn review chéo/merge và governance `W2.6` | Q + Y | — |
| `G-03 Model/Parse Feasibility` | W05 | 23/10 | Parser/chunk provenance đạt fixture; model/index chạy trên máy demo; JSON schema khóa | Dùng fallback model/index; cắt OCR/extension | OPEN | Stable provenance, golden parser benchmark, Parser ADR, output JSON Schema/runtime validators và model-selection ADR đã có; còn review/clean-run evidence, resource limit và vector-index adapter | Q + Y | — |
| `G-04 Similarity v1` | W08 | 30/10 | BM25/Dense/RRF/reranker/classifier/report chạy và có metric sơ bộ | Giữ baseline tốt nhất; không mở extension | OPEN | Technical slice chạy một lệnh và tạo exact spans, unique coverage, aggregation, Similarity Report; semantic candidates được giữ ở review queue. Còn classifier bốn nhãn và validation trên split được duyệt | Q + Y | — |
| `G-05 LOCAL Assessment` | W10 | 30/10 | Rubric→LOCAL evidence→three-state verification chạy, có ground truth pilot | Sửa protocol/retrieval trước khi dựng graph sâu | OPEN | Compiler deterministic, LOCAL retrieval, Evidence Pack validation, three-state verifier/scoring và report đã chạy; private pilot pack có một lượt nhãn nhưng thiếu gán nhãn độc lập, adjudication và metric | Q + Y | — |
| `G-06 Graph Assessment` | W13 | 20/11 | Graph provenance, multi-hop retrieval, rationale và deterministic scoring đạt case test | Giữ LOCAL path làm fallback và báo limitation graph | OPEN | Có ontology draft và structure/term PPR baseline deterministic dùng trong assessment; chưa có claim/entity extraction, graph persistence/versioning hoặc graph QA trên gold cases | Q + Y | — |
| `G-07 RC1/Freeze` | W16 | 27/11 | E2E, RBAC, security, retry/failure test; không còn blocker/critical | Dừng feature, triage và cắt P1/P2 | OPEN | Mốc 27/11 được dùng cho Research RC1/offline E2E. Nếu chưa có production RBAC/API/security đầy đủ thì gate gốc phải ghi `WAIVED` có lý do, không được ghi `PASS` | Q + Y | — |
| `G-08 Benchmark Ready` | W17 | 04/12 | Dataset/split/guideline/metric/manifest khóa, leakage check đạt | Không chạy bảng kết quả chính thức | OPEN | DEV0 chỉ dùng chẩn đoán; DEV1/TEST0 đã được tạo cục bộ, không overlap nhưng governance còn `PENDING`. TEST0 phải tiếp tục sealed | Q + Y + GVHD | — |
| `G-09 RC2` | W21 | 01/01/2027 | Performance/security/privacy/reproducibility đạt mức demo | Tối ưu bottleneck có evidence; giữ cấu hình ổn định nhất | OPEN | Giữ mốc baseline | Q + Y | — |
| `G-10 Release 1.0` | W23 | 15/01/2027 | Report–code–data–result–demo nhất quán; clean install đạt | Chỉ sửa lỗi/consistency, không thêm feature | OPEN | Giữ mốc baseline | Q + Y + GVHD | — |
| `G-11 Submission` | W24 + 23/01 | 23/01/2027 | W24 readiness đạt; nộp trước hạn 23/01/2027; receipt ghi timestamp, kênh/người nhận, inventory/link hoặc mã biên nhận và checksum | Escalate ngay GVHD; dùng offline demo/fallback | OPEN | Giữ mốc nộp cứng | Q + Y | — |

## 6. Actual và kế hoạch phục hồi — cập nhật 19/10/2026

### 6.1. Kết quả đã xác minh

- Phạm vi/SRS/Use Case đã được đồng bộ và merge qua PR #8. C4/threat model
  `W2.1` đã merge qua PR #5; MongoDB/provenance design baseline `W2.2` đã được
  Y approve và merge qua PR #6.
- API Contract/OpenAPI `W2.3`, UX P0 `W2.4` và rubric/annotation spec `W2.5`
  đã được tích hợp, đối chiếu với code hiện hành trong working tree. Chúng chưa
  được tính `DONE` vì còn thiếu commit/PR và review chéo của owner/reviewer.
- Parser/chunker đã có stable chunk ID, exact span, raw–normalized mapping và
  deterministic split trên `main` qua PR #9. Golden parser corpus/benchmark và
  Parser ADR đã được tích hợp vào working tree, chạy lặp lại được trên fixture.
- Offline retrieval runner đã merge qua PR #11; PAN pilot pack và protocol đã
  merge qua PR #12. Branch thực nghiệm hiện có A1–A5 gồm BM25, Dense, RRF và
  Cross-Encoder, kèm run manifest, raw predictions, metric và error analysis.
  Các contract test mới khóa rubric compiler, graph baseline, exact-span
  coverage, output schema và upload validation. Số test chính thức chỉ được ghi
  vào gate sau khi chạy từ clean commit.
- A1–A5 mới là diagnostic trên `DEV0` gồm 30 parent annotations; không phải kết
  quả chính thức. Kết quả hiện cho thấy reranker v1 làm giảm Recall@10 do
  candidate gating, passage mismatch và truncation, nên chưa được chọn làm
  proposed configuration. DEV1/TEST0 đã được dẫn xuất không overlap nhưng vẫn
  `PENDING`; không được chạy trước governance approval và TEST0 phải giữ kín.
- Pipeline 1 technical slice hiện đã có orchestration, exact text alignment,
  unique coverage, source aggregation và Similarity Report. Nó chưa có bộ phân
  loại semantic bốn nhãn đã được đánh giá; semantic candidate chỉ là hàng chờ
  review, không được tính thành similarity đã xác nhận.
- Pipeline 2 technical slice hiện đã có Rubric Compiler, LOCAL retrieval,
  structure/term GRAPH baseline, Evidence Pack validator, three-state verifier,
  deterministic scorer và Assessment Report. Nó chưa phải claim/entity
  evidence graph hoàn chỉnh và chưa có gold pilot hai người đã adjudicate.
- App local đã chạy luồng upload report/source/rubric → file-backed queue/worker
  → hai report → lecturer review trên React. Đây chưa phải production stack:
  còn thiếu MongoDB/index, auth/RBAC, retry/checkpoint và security hardening.

### 6.2. Snapshot theo output/DoD

`Actual %` dùng quy tắc tại mục 10: 25% có draft/fixture, 50% main flow chạy,
75% đã test/review nhưng còn điều kiện, 100% chỉ khi đạt DoD. `CARRY-OVER`
giữ dấu vết trễ lịch dù task đã có một phần artifact.

| ID/nhóm | Status cập nhật | Actual % | Evidence hiện tại | Phần còn thiếu để đóng |
|---|---|---:|---|---|
| `W1.1` | DONE | 100% | SRS/Use Case/README đã đồng bộ; Y đã approve và PR #8 đã merge | Theo dõi thay đổi phạm vi mới bằng change request, không mở lại baseline cũ |
| `W1.2` | CARRY-OVER | 50% | Có AS-IS/TO-BE, bộ câu hỏi và giả định | Biên bản phản hồi thực tế có người/ngày |
| `W1.3` | IN PROGRESS | 75% | Khảo sát similarity/Rubric-RAG, baseline, metric và nguồn nghiên cứu đã có | Đồng bộ lại phần reference/AI detector đã ra khỏi scope; bổ sung Evidence Graph và literature matrix hiện hành |
| `W1.4` | CARRY-OVER | 75% | Hai file planning và RQ traceability đã có | Q/Y review và xác nhận baseline hiện hành |
| `W1.5` | CARRY-OVER | 75% | Repo/board/labels/milestones/workflow và PR #2 đã merge | Approval/comment xác nhận của reviewer Y |
| `W1.6` | CARRY-OVER | 25% | Báo cáo tiến độ có nội dung nền | Chương 1 riêng và review chéo |
| `W2.1` | DONE | 100% | [C4](../architecture/c4.md), [data flow/trust boundary](../architecture/data-flow.md) và [threat model](../threat-model/threat-model-v1.md) đã merge qua PR #5; scope đã đồng bộ qua PR #8 | Review lại threat model tại W16 theo kế hoạch |
| `W2.2` | DONE | 100% | [ADR-001](../adr/ADR-001-mongodb-provenance-storage.md) và [data dictionary](../architecture/data-dictionary.md) đã được Y approve/merge qua PR #6 | Runtime MongoDB/persistence thuộc `W3.1/W4.2`, không mở lại design task này |
| `W2.3` | IN PROGRESS | 75% | [API Contract](../api/API_CONTRACT_V1.md) và OpenAPI v1 đã tích hợp vào working tree | Commit, review cuối và merge |
| `W2.4` | IN PROGRESS | 75% | [UX P0](../ux/p0-local-flow.md) có navigation, wireframe, state và ma trận quyền; app local hiện thực luồng chính | Y/Q review; auth/permission runtime thuộc W3.2/W3.4 |
| `W2.5` | IN PROGRESS | 75% | [Rubric v1](../rubric/rubric-v1.md) đã khớp compiler hiện hành: authored atomic checklist, LOCAL/GRAPH, three-state và adjudication | Y/Q review, chốt example thật và merge |
| `W2.6` | CARRY-OVER | 75% | Dataset-role mapping, PAN pilot pack, manifest gate và leakage-safe split derivation đã có | Rights/access/retention/approver; regenerate DEV1/TEST0 từ clean commit rồi mới xin duyệt |
| `W3.1` | CARRY-OVER | 50% | Backend package, dependency manifests và CI test/build workflow đã có | MongoDB/Compose, healthcheck và security scan gates |
| `W3.2` | CARRY-OVER | 0% | Chưa có auth/session/RBAC production | Identity provider, tenant/ownership enforcement, audit và negative auth tests |
| `W3.3` | IN PROGRESS | 75% | Fixture PDF/DOCX an toàn; duplicate/self/invalid PDF-DOCX/NUL/rubric/config validation tests đã có | Rights metadata và malicious-content corpus mở rộng; review chéo |
| `W3.4` | IN PROGRESS | 50% | React/Vite app hiển thị local workflow và states | Routing/auth/forbidden state và frontend test suite |
| `W3.5` | IN PROGRESS | 50% | Upload report/source/rubric, job status và result review chạy local | Report/source lifecycle, immutable version list và API production |
| `W3.6` | IN PROGRESS | 75% | Local API + file-backed queue/worker có queued/running/completed/failed và run artifact | Correlation log, retry/idempotency test và durable production queue |
| `W4.1` | IN PROGRESS | 75% | Parser baseline PDF/DOCX, worker adapter local, tests và [ADR-002](../adr/ADR-002-parser-baseline.md) đã có | Timeout/resource limit và review benchmark trên corpus được phép |
| `W4.2` | IN PROGRESS | 50% | Normalized element/chunk schema và provenance mapping đã có | MongoDB persistence/idempotency test; không còn block bởi `W2.2` |
| `W4.3` | IN PROGRESS | 50% | Worker local có job state/failure output | Checkpoint, bounded retry và idempotent recovery |
| `W4.4` | IN PROGRESS | 75% | Stable ID, exact span, raw–normalized mapping, long-element split và deterministic output đã merge qua PR #9 | Merge golden regression branch và lưu reviewer evidence để đóng parent task |
| `W4.5` | TODO | 0% | Chưa có | Core marker-to-span, citation fixture; GROBID nâng cao chỉ làm nếu cần |
| `W4.6` | IN PROGRESS | 75% | Golden manifest, expected mapping, test và benchmark report đã tích hợp vào working tree | Review/merge; bổ sung corpus thật chỉ khi có quyền |
| `W5.1` | IN PROGRESS | 50% | Local model loader/config và run manifest ghi model/hardware/timing | Tách service/health, timeout, memory và batch telemetry |
| `W5.2` | TODO | 0% | Chưa có vector-index adapter | Upsert/search/version/rebuild và idempotency test |
| `W5.3` | IN PROGRESS | 75% | Cross-Encoder adapter/test, ba JSON Schema và runtime validators cho similarity/evidence/assessment | Timeout/fallback contract và review chéo |
| `W5.4` | TODO | 0% | Chưa có benchmark local LLM có gold structured output | Chốt model/fixture/hardware sau governance |
| `W5.5–W5.6` | IN PROGRESS | 75% | Embedding/reranker diagnostics A1–A5 và [ADR-003](../adr/ADR-003-provisional-model-selection.md) đã có | Chạy DEV1 được duyệt; khóa quality–resource decision và reviewer |
| `W6.1–W6.3`, `W6.5` | IN PROGRESS | 75% | Offline BM25, Dense, dual runner, metrics và run manifest đã chạy; runner đã merge qua PR #11 | Tách rõ offline research DoD với product index/persistence; review và khóa config |
| `W6.4`, `W7.4` | TODO | 0% | PAN qrels mới cung cấp source positives; chưa phải bộ bốn nhãn/hard negatives của hệ thống | Tạo positive/negative, VERBATIM/PARAPHRASE/SUMMARY/NONE, citation và no-source cases có review |
| `W6.6`, `W7.1–W7.3`, `W7.5–W7.6` | IN PROGRESS | 75% | DEV0 A1–A5, paired error analysis và Cross-Encoder diagnostics có trên branch thực nghiệm | Tích hợp branch; sửa candidate/reranker design; validation trên DEV1 được duyệt; không tune tiếp trên DEV0 |
| `W8.1–W8.3` | IN PROGRESS | 75% | Pipeline 1 chạy offline/app local, giữ exact spans, unique coverage, source aggregation và Similarity Report có disclaimer | Commit/review; persistence Mongo; semantic gold evaluation |
| `W8.4` | IN PROGRESS | 25% | Có guideline và blinded annotation workflow; chưa tự gán PARAPHRASE/SUMMARY | Hai người gán nhãn, adjudicate, train/calibrate/evaluate classifier |
| `W8.5` | IN PROGRESS | 50% | Synthetic quote/generic/no-source/hard-negative fixtures và regression có | Chốt citation policy và expected output qua review chéo |
| `W8.6` | IN PROGRESS | 50% | App local hiển thị evidence/result/review | Side-by-side span UX, empty/error/forbidden và E2E frontend test |
| `W9.1` | IN PROGRESS | 25% | Rubric JSON được upload/lưu trong local job | Draft/clone/publish/immutable version lifecycle và RBAC |
| `W9.2–W9.3` | IN PROGRESS | 75% | Compiler deterministic, stable hash/ID, field-specific validation và contract tests | Persistence/API error mapping, review và merge |
| `W9.4–W9.5` | IN PROGRESS | 75% | Rubric domain/template, authored atomic checklist, LOCAL/GRAPH mode và decision rules đã có | Review trên rubric môn học thật được phép |
| `W9.6` | CONDITIONAL | 0% | Chưa có rubric management UI | Làm sau core pipeline nếu capacity cho phép |
| `W10.1–W10.2` | IN PROGRESS | 75% | LOCAL assessment, Evidence Pack và scope/version/source-span validators chạy offline/app local | Mongo persistence, immutable run linking và API production |
| `W10.3` | IN PROGRESS | 50% | Có no-evidence, negation, conflicting evidence, dangling/cross-report/version tests | Auth isolation, timeout/retry và prompt-injection integration tests |
| `W10.4–W10.5` | IN PROGRESS | 75% | Checklist query→BM25/Dense/RRF/rerank và SUPPORTED/CONTRADICTED/INSUFFICIENT→MET/UNMET/CANNOT_ASSESS chạy | Gold validation, semantic NLI/contradiction study và review |
| `W10.6` | IN PROGRESS | 50% | Private pack 26 cases có một lượt nhãn, phiếu blind và adjudication template | Xác minh report/version/quyền; Q gán độc lập, adjudicate và tính metric |
| `W11.1–W11.3` | TODO | 0% | Structure/term graph hiện chỉ in-memory, không phải Evidence Graph persistence/API | Graph version/index/rebuild/query/worker và provenance tests |
| `W11.4` | IN PROGRESS | 50% | [Ontology v0](../assessment/evidence-graph-ontology-v0.md) định nghĩa node/edge/invariant/example | Y/Q review và map vào extraction schema versioned |
| `W11.5` | TODO | 0% | Chưa có claim/entity/relation extraction | Structured extraction kèm model/prompt/confidence/source span |
| `W11.6` | TODO | 0% | Structure/term PPR hiện chỉ kiểm thử thuật toán xếp hạng, chưa tạo sample claim graph | Chờ `W11.2/W11.5`, sau đó manual QA, precision sample và extraction error analysis |

### 6.3. Quy tắc recovery v1.7

- Không cộng carry-over vào tuần mới mà vẫn giữ nguyên 13 SP/người. Owner phải
  ước lượng `remaining SP`; `remaining carry-over + committed work ≤ 13 SP`.
- Ưu tiên tuyệt đối theo thứ tự: đóng Pipeline 1 research-core → Rubric
  Compiler/LOCAL → GRAPH/router → verifier/scoring → E2E/freeze. Không mở thêm
  feature khi một mắt xích bắt buộc của hai pipeline còn thiếu.
- `DEV0` chỉ dùng để chẩn đoán. `DEV1` chỉ được dùng chọn phương pháp sau khi
  governance được duyệt; `TEST0` giữ sealed đến khi phương pháp/config đã khóa.
- OCR, AI-writing, cross-language, Targeted Questions, cohort dashboard, full
  Docling/GROBID, Neo4j optimization, PDF export và UI polish nằm dưới cut-line.
  Chỉ giữ export/review fixture tối thiểu cho E2E.
- Không được cắt provenance, rights/consent, negative/no-source cases,
  annotation/adjudication, leakage audit, reproducibility hoặc human review.
- Nếu GRAPH trễ sau W14, LOCAL vẫn phải hoàn chỉnh; GRAPH thu hẹp thành pilot
  component có limitation thay vì hy sinh verifier/scorer, W16 E2E hay W17
  dataset freeze.

---

## 7. WBS chi tiết theo tuần

### Tuần 1 — 08/08 đến 14/08/2026

**Milestone:** Baseline phạm vi và hồ sơ lập kế hoạch sẵn sàng review.

| ID | Backlog | Work package | Owner | Review | SP | Phụ thuộc | Đầu ra/DoD riêng | Trạng thái cập nhật |
|---|---|---|---|---|---:|---|---|---|
| `W1.1` | `EP-01-S01` | Đồng bộ mục tiêu, phạm vi, actor, Use Case, RQ và tiêu chí hoàn thành sau rebaseline | Q | Y | 3 | — | Quyết định 2 hướng chính + 1 bổ sung đã chốt; SRS/Use Case/README bỏ RQ/provider/reference feature cũ, Q/Y review và scope change có log | DONE |
| `W1.2` | `EP-01-S05` | Khảo sát AS-IS/TO-BE và chuẩn bị xác nhận giảng viên | Y | Q | 3 | `W1.1` | Bộ câu hỏi, biên bản và bảng giả định có trạng thái/người/ngày | CARRY-OVER |
| `W1.3` | `EP-01-S01` | Khảo sát kỹ thuật plagiarism/IR/rubric/evidence/graph | Y | Q | 3 | `W1.1` | Có [khảo sát kỹ thuật](../week-01/W1-02-khao-sat-ky-thuat.md) so sánh baseline, metric, ưu/nhược điểm và nguồn nghiên cứu | IN PROGRESS |
| `W1.4` | `EP-12-S01` | Lập Product Backlog, WBS và traceability ban đầu | Q | Y | 2 | `W1.1` | Hai file planning riêng; mọi tuần/outcome có owner; RQ1/RQ2/RQ3 trỏ tới epic, experiment và artifact tương ứng | CARRY-OVER |
| `W1.5` | `EP-01-S04`, `EP-02-S01` | Khởi tạo repo, cấu trúc thư mục, quy ước Git và issue board | Q | Y | 3 | `W1.4` | Capacity/máy/deadline được ghi; repo/scaffold/README, [workflow](../../CONTRIBUTING.md), [board](https://github.com/users/ngwine/projects/2), [labels](https://github.com/ngwine/evidence-grounded-report-assessment/labels), [milestones](https://github.com/ngwine/evidence-grounded-report-assessment/milestones) và [issue review](https://github.com/ngwine/evidence-grounded-report-assessment/issues/1) có bằng chứng | CARRY-OVER |
| `W1.6` | `EP-12-S01` | Viết bản nháp Chương 1 | Y | Q | 2 | `W1.1` | Bối cảnh, vấn đề, mục tiêu, phạm vi, đóng góp và bố cục | CARRY-OVER |

**Tải kế hoạch:** Q = 8 SP, Y = 8 SP.

### Tuần 2 — 15/08 đến 21/08/2026

**Milestone:** Design baseline được khóa trước khi phát triển sâu.

| ID | Backlog | Work package | Owner | Review | SP | Phụ thuộc | Đầu ra/DoD riêng | Trạng thái cập nhật |
|---|---|---|---|---|---:|---|---|---|
| `W2.1` | `EP-02-S05`, `EP-02-S04` | Thiết kế C4 Context/Container/Deployment, data flow, trust boundary và threat-model/adversarial plan v1 | Q | Y | 4 | `W1.1` | [C4](../architecture/c4.md) phản ánh Web–API–worker–DB/storage/index/local AI; [data flow/trust boundary](../architecture/data-flow.md) và [threat model](../threat-model/threat-model-v1.md) có asset/risk→mitigation→test mapping cho upload/parser, queue, DB, tenant retrieval, prompt injection, output sanitization và log privacy | DONE |
| `W2.2` | `EP-02-S02`, `EP-09-S06` | Chốt MongoDB deployment/index ADR, collection, data dictionary và lifecycle fields | Q | Y | 5 | `W2.1` | [ADR-001](../adr/ADR-001-mongodb-provenance-storage.md) và [data dictionary](../architecture/data-dictionary.md) mô tả schema/reference/index/invariant/migration/rebuild, purpose/rights/retention/tombstone và derived-data cascade | DONE |
| `W2.3` | `EP-02-S06` | Viết API contract v1 và error format | Q | Y | 4 | `W2.2` | Auth/report/source/upload/job/chunk/rubric/result/review contract | IN PROGRESS |
| `W2.4` | `EP-02-S07`, `EP-02-S03` | Wireframe, navigation map và ma trận quyền các luồng P0 | Y | Q | 4 | `W1.1` | Upload/progress/evidence/review có loading/empty/error/permission | IN PROGRESS |
| `W2.5` | `EP-01-S06`, `EP-05-S01` | Rubric template v1, checklist LOCAL/GRAPH và annotation/adjudication guideline | Y | Q | 5 | `W1.2` | Criterion/evidence/weight/level/rule có example; người gán nhãn, vòng review và cách giải quyết bất đồng rõ | IN PROGRESS |
| `W2.6` | `EP-01-S02`, `EP-04-S01`, `EP-09-S06`, `EP-10-S01` | Lập data/rubric/model inventory, hồ sơ rights–purpose–retention và dataset/benchmark/sample-corpus plan v1 | Y | Q | 4 | `W1.2`, `W2.5`, nguồn dữ liệu/GVHD | Mỗi nguồn có owner/license-or-consent/allowed purpose/classification/anonymization/retention/approver/date; deny-by-default nếu chưa duyệt; đơn vị mẫu/nhãn/split/metric/provenance và sample không nhạy cảm rõ | CARRY-OVER |

**Tải kế hoạch:** Q = 13 SP, Y = 13 SP.

**Phân rã `W2.6`, không cộng thêm SP:**

| Child ID | Đầu ra | Status cập nhật | Evidence/điều kiện đóng |
|---|---|---|---|
| `W2.6.1` | Dataset-task mapping, core/supplementary/backup selection và in-domain schema | DONE | Quyết định nhóm 03/09 tại báo cáo tiến độ mục 4–4.2: PAN-PC-11/PAN13 cho P1 retrieval/alignment; PlagBench bổ sung classification; MMDocIR/HoVer/HARMOGEN-R cho P2; in-domain bắt buộc end-to-end |
| `W2.6.2` | Download, format, license, checksum, official split và access verification | IN PROGRESS | PAN pilot/DEV0 và leakage-safe DEV1/TEST0 derivation đã có; vẫn phải regenerate từ clean commit và xác minh quyền/allowed purpose trước approval |
| `W2.6.3` | Rights/consent/anonymization/retention và annotation/adjudication protocol in-domain | CARRY-OVER | Cần data owner/GVHD approver, bản ẩn danh, reviewer/adjudication record và ngày quyết định |

**Recovery v1.7:** parent `W2.6` chỉ `DONE` khi cả ba child đạt DoD. Đóng
`W2.2–W2.6` và review `G-02` theo forecast tại mục 11; không sửa ngày baseline
W02.

### Tuần 3 — 22/08 đến 28/08/2026

**Milestone:** Platform core chạy từ UI qua API đến MongoDB và tạo được job upload.

| ID | Backlog | Work package | Owner | Review | SP | Phụ thuộc | Đầu ra/DoD riêng | Trạng thái |
|---|---|---|---|---|---:|---|---|---|
| `W3.1` | `EP-02-S01/02/06`, `EP-11-S01` | Dựng FastAPI, settings, MongoDB init/migration, Compose và CI quality/security baseline | Q | Y | 5 | `W2.2/3` | Healthcheck và DB/index init đạt; lint/type/test, SAST, secret và dependency scan chạy CI; High/Critical fail gate hoặc có waiver owner/expiry | IN PROGRESS |
| `W3.2` | `EP-02-S03/08` | Backend auth/session, RBAC và audit events nền | Q | Y | 5 | `W3.1`, `W2.4` | Ma trận role/ownership và negative authorization tests đạt | CARRY-OVER |
| `W3.3` | `EP-03-S01`, `EP-10-S01`, `EP-11-S02` | Chuẩn bị report/source metadata examples, safe-upload fixtures và validation/contract tests | Y | Q | 3 | `W2.3/6` | Fixture PDF/DOCX hợp lệ/lỗi có rights state và expected metadata; bao phủ MIME/size/path/duplicate; không chứa dữ liệu nhạy cảm | IN PROGRESS |
| `W3.4` | `EP-02-S07/03` | Dựng React/Vite, routing, auth state và UI đăng nhập/quản lý quyền tối thiểu | Y | Q | 5 | `W2.3/4`, `W3.2` | Success/loading/error/forbidden state và smoke test | IN PROGRESS |
| `W3.5` | `EP-03-S01` | UI quản lý báo cáo/kho nguồn, upload và theo dõi version/status | Y | Q | 5 | `W3.3/6` | Upload/list/detail/status chạy với fixture hoặc API thật | IN PROGRESS |
| `W3.6` | `EP-03-S01/06`, `EP-09-S01/04` | Backend upload API, queue/worker skeleton, job-state contract và correlation logging | Q | Y | 3 | `W3.1/2/3` | Upload lưu version/hash/status; job queued/processing/failed/completed; `request_id→job_id→run_id` truyền qua API/worker/log và log không lộ PII; contract test đạt | IN PROGRESS |

**Tải kế hoạch:** Q = 13 SP, Y = 13 SP.

### Tuần 4 — 29/08 đến 04/09/2026

**Milestone:** Document Processing Pipeline v1 tạo chunk truy vết về đúng tài liệu/trang.

| ID | Backlog | Work package | Owner | Review | SP | Phụ thuộc | Đầu ra/DoD riêng | Trạng thái |
|---|---|---|---|---|---:|---|---|---|
| `W4.1` | `EP-03-S02`, `EP-11-S02` | Tích hợp parser adapter PDF/DOCX đã được benchmark vào worker; PyMuPDF/python-docx là baseline, Docling là candidate có điều kiện | Q | Y | 5 | Fixture subset `W3.3`; `W3.6` cho worker | PDF/DOCX parse qua adapter; timeout/resource limit; lỗi không tạo artifact giả; Parser ADR ghi quyết định trước `G-03` | IN PROGRESS |
| `W4.2` | `EP-03-S02` | Normalized document schema và mapping section/page/table/reference vào MongoDB | Q | Y | 5 | `W2.2`, `W4.1.1` | Schema/version/provenance và idempotent persistence được test | IN PROGRESS |
| `W4.3` | `EP-03-S06`, `EP-09-S01` | Parse job handler, checkpoint, retry và failure reporting | Q | Y | 3 | `W3.6`, `W4.1.2`, `W4.2` | Retry không nhân đôi document/chunk; UI/API thấy lỗi có mã | IN PROGRESS |
| `W4.4` | `EP-03-S03` | Cleaner và structure-aware chunker | Y | Q | 5 | `W4.1.1`; `W4.2` cho provenance hardening | Chunk theo section/paragraph; deterministic stable ID; document/version/order/exact span hợp lệ; giữ raw/normalized text; paragraph/bảng dài được split có kiểm soát | IN PROGRESS |
| `W4.5` | `EP-03-S07` | Core quote/citation/reference marker-to-span mapping; GROBID nâng cao là conditional | Y | Q | 3 | `W4.1.1`, `W4.2` | Marker/entry/ngữ cảnh liên kết đúng page/span/chunk; raw/confidence lưu được; failure là unknown | TODO |
| `W4.6` | `EP-03-S08` | Golden corpus và benchmark parser/chunk provenance | Y | Q | 5 | `W4.1.1`, `W4.4.1`; `W4.4.2` cho final report | Expected structure/page/span mapping; coverage/error/latency report; gồm case header/footer, multi-column, long paragraph/table và fixture hợp lệ | IN PROGRESS |

**Tải kế hoạch:** Q = 13 SP, Y = 13 SP.

**Phân rã evidence, không cộng thêm SP:**

| Child ID | Parent | Dependency | Đầu ra | Status cập nhật | Evidence/điều kiện đóng |
|---|---|---|---|---|---|
| `W4.1.1` | `W4.1` | Fixture subset đã có | PyMuPDF/python-docx parsing prototype và fixture tests | DONE | Commit `3c1c133`; PDF/DOCX smoke test pass |
| `W4.1.2` | `W4.1` | `W3.6`, `W4.1.1` | Worker adapter, timeout/resource limit và failure contract | IN PROGRESS | Worker/upload local đã chạy; còn timeout/resource limit và retry |
| `W4.1.3` | `W4.1` | `W4.6.2` | Benchmark baseline với Docling và Parser ADR | IN PROGRESS | ADR-002 đã khóa PyMuPDF/python-docx làm baseline; Docling chỉ benchmark khi fixture cho thấy cần |
| `W4.4.1` | `W4.4` | `W4.1.1` | Section-aware chunker prototype | DONE | Commit `3c1c133`; chunk JSON và test schema cơ bản |
| `W4.4.2` | `W4.4` | `W4.2`, `W4.4.1` | Stable provenance và hardening chunk | DONE | PR #9: document/version/span/raw-normalized/stable ID và long-element split; regression mở rộng nằm ở `W4.6` |
| `W4.6.1` | `W4.6` | Fixture subset đã có | Synthetic fixtures và smoke tests | DONE | Hai fixture an toàn; `2 passed` |
| `W4.6.2` | `W4.6` | `W4.1.1`, `W4.4.1`; quyền dữ liệu nếu dùng report thật | Golden corpus và expected mapping | IN PROGRESS | Artifact đã tích hợp vào working tree; chờ commit/review/merge |
| `W4.6.3` | `W4.6` | `W4.1.3`, `W4.4.2`, `W4.6.2` | Final parser/chunk quality và latency report | IN PROGRESS | Benchmark report và ADR-002 đã có; còn clean-run/reviewer evidence |

### Tuần 5 — 05/09 đến 11/09/2026

**Milestone:** Khóa cấu hình AI cục bộ, embedding/reranker và output contract.

| ID | Backlog | Work package | Owner | Review | SP | Phụ thuộc | Đầu ra/DoD riêng | Trạng thái |
|---|---|---|---|---|---:|---|---|---|
| `W5.1` | `EP-03-S04`, `EP-09-S04` | Local AI/embedding service, model loader và inference telemetry | Q | Y | 5 | `W4.4/6` | Health/inference chạy trên máy demo; timeout, batch và model/config provenance rõ | IN PROGRESS |
| `W5.2` | `EP-03-S04` | Vector index adapter, upsert/search/version/rebuild | Q | Y | 5 | `W5.1`, `W2.2` | Vector liên kết đúng chunk/version; indexing idempotent; rebuild được test | TODO |
| `W5.3` | `EP-04-S04`, `EP-05-S04` | Reranker contract và JSON Schema validators dùng chung | Q | Y | 3 | `W5.1` | Batch rerank và schema similarity/evidence/rationale có test lỗi/timeout | IN PROGRESS |
| `W5.4` | `EP-10-S06` | Benchmark local LLM trên structured-output fixture | Y | Q | 5 | `W2.6`, `W5.1` | So chất lượng schema, latency, RAM/VRAM trên cùng hardware/config | TODO |
| `W5.5` | `EP-04-S03/04`, `EP-10-S06` | Benchmark embedding và reranker | Y | Q | 5 | `W5.2/3`, sample corpus | Cùng corpus/query/protocol; lưu model/version/config và bảng quality–resource | IN PROGRESS |
| `W5.6` | `EP-10-S06` | Model-selection report, fallback và gate `G-03` | Y | Q | 3 | `W5.4/5`, `W4.6` | Quyết định có artifact hỗ trợ; cấu hình/fallback/limitation được khóa | IN PROGRESS |

**Tải kế hoạch:** Q = 13 SP, Y = 13 SP.

### Tuần 6 — 12/09 đến 18/09/2026

**Milestone:** BM25 và Dense Retrieval baseline chạy tái lập được.

| ID | Backlog | Work package | Owner | Review | SP | Phụ thuộc | Đầu ra/DoD riêng | Trạng thái |
|---|---|---|---|---|---:|---|---|---|
| `W6.1` | `EP-03-S04`, `EP-04-S02` | Source lexical index và BM25 Retrieval v1 | Q | Y | 5 | `W4.4`, `W5.2` | Index rebuild/idempotency đạt; Top-K có score/source/page/section; tokenizer/config/index versioned | IN PROGRESS |
| `W6.2` | `EP-04-S03` | Dense Retrieval v1 | Q | Y | 5 | `W5.2` | Dùng cùng candidate schema/filter/corpus với BM25; model/normalization lưu | IN PROGRESS |
| `W6.3` | `EP-04-S02/03`, `EP-10-S06` | Dual-retrieval runner và candidate persistence | Q | Y | 3 | `W6.1/2` | Một run tạo hai ranking kèm config/timing/run ID, không trộn index version | IN PROGRESS |
| `W6.4` | `EP-04-S01` | Gán nhãn seed query–source passages | Y | Q | 5 | `W2.6`, `W4.4` | Có positive/negative và verbatim/paraphrase/summary/none; provenance đầy đủ | TODO |
| `W6.5` | `EP-04-S01`, `EP-10-S01/06` | Query-passage policy và metric Recall@K/MRR/nDCG | Y | Q | 3 | `W6.4` | Quy tắc query khóa trước test; metric unit test bằng ví dụ biết trước | IN PROGRESS |
| `W6.6` | `EP-04-S02/03` | Audit retrieval và báo cáo baseline BM25/Dense | Y | Q | 5 | `W6.3–5` | Cùng split/hardware; missed evidence, duplicate, latency và lỗi provenance được phân tích | IN PROGRESS |

**Tải kế hoạch:** Q = 13 SP, Y = 13 SP.

### Tuần 7 — 19/09 đến 25/09/2026

**Milestone:** Hybrid Retrieval v1 và cấu hình quality–latency đề xuất.

| ID | Backlog | Work package | Owner | Review | SP | Phụ thuộc | Đầu ra/DoD riêng | Trạng thái |
|---|---|---|---|---|---:|---|---|---|
| `W7.1` | `EP-04-S04` | Reciprocal Rank Fusion | Q | Y | 3 | `W6.3` | Duplicate/tie xử lý ổn định; `k`/weight configurable và có unit test | IN PROGRESS |
| `W7.2` | `EP-04-S04` | Cross-Encoder reranker integration | Q | Y | 5 | `W5.3`, `W7.1` | Rerank top-N→top-K; lưu pre/post score, model/config; timeout fallback | IN PROGRESS |
| `W7.3` | `EP-04-S04`, `EP-09-S04` | Hybrid pipeline và stage-latency instrumentation | Q | Y | 5 | `W7.1/2` | BM25+Dense→RRF→rerank chạy một lệnh; stage failure không mất baseline | IN PROGRESS |
| `W7.4` | `EP-04-S01` | Hard-negative/error set cho retrieval | Y | Q | 5 | `W6.4/6` | Có lexical false positive, paraphrase khó, citation và none; review chéo nhãn | TODO |
| `W7.5` | `EP-10-S06` | Protocol và run so sánh BM25/Dense/Hybrid | Y | Q | 3 | `W7.3/4` | Cùng corpus/split/top-k/hardware; run manifest và raw result đầy đủ | IN PROGRESS |
| `W7.6` | `EP-04-S04` | Error analysis và chọn cấu hình Hybrid | Y | Q | 5 | `W7.5` | Bảng quality–latency, taxonomy lỗi và quyết định có run ID hỗ trợ | IN PROGRESS |

**Tải kế hoạch:** Q = 13 SP, Y = 13 SP.

### Tuần 8 — 26/09 đến 02/10/2026

**Milestone:** Similarity Analysis Pipeline v1 có evidence viewer và metric sơ bộ.

| ID | Backlog | Work package | Owner | Review | SP | Phụ thuộc | Đầu ra/DoD riêng | Trạng thái |
|---|---|---|---|---|---:|---|---|---|
| `W8.1` | `EP-04-S09/11` | Similarity orchestration/API và classification-result persistence | Q | Y | 5 | `W7.3`, `W5.3` | Run liên kết query/candidate/model/config/label; rerun/version không ghi đè | IN PROGRESS |
| `W8.2` | `EP-04-S10/11` | Span alignment, unique coverage và weighted document aggregation | Q | Y | 5 | `W8.1` | Span hợp lệ; overlap không tính hai lần; công thức/version/threshold rõ | IN PROGRESS |
| `W8.3` | `EP-04-S07` | Similarity Report API và export fixture | Q | Y | 3 | `W8.1/2` | Report truy vết pair/source/page/run; ghi rõ similarity không đồng nghĩa đạo văn | IN PROGRESS |
| `W8.4` | `EP-04-S09` | Classifier, calibration và ground-truth guideline bốn nhãn | Y | Q | 5 | `W7.2/4` | VERBATIM/PARAPHRASE/SUMMARY/NONE; confidence/ambiguous case; F1 từng lớp | IN PROGRESS |
| `W8.5` | `EP-04-S10` | Quote/citation context rule và test cases | Y | Q | 3 | `W4.5`, `W8.4` | Quote/citation đánh dấu riêng, không tự kết luận gian lận; case khó có expected output | IN PROGRESS |
| `W8.6` | `EP-04-S07` | Side-by-side evidence/highlight UI và integration test | Y | Q | 5 | `W8.2/3` | Hai đoạn/nguồn/type/score/location hiển thị; empty/error/review state và E2E fixture đạt | IN PROGRESS |

**Tải kế hoạch:** Q = 13 SP, Y = 13 SP.

### Tuần 9 — 03/10 đến 09/10/2026

**Milestone:** Rubric Compiler v1 sinh checklist thực thi được.

| ID | Backlog | Work package | Owner | Review | SP | Phụ thuộc | Đầu ra/DoD riêng | Trạng thái |
|---|---|---|---|---|---:|---|---|---|
| `W9.1` | `EP-05-S01` | Rubric persistence, immutable version và API | Q | Y | 5 | `W2.2/3/5` | Draft/clone/publish/version lifecycle, order/weight và quyền sửa được test | IN PROGRESS |
| `W9.2` | `EP-05-S09` | Compiler execution/persistence và validation error mapping | Q | Y | 5 | `W9.1`, `W9.4` | Compile deterministic; invalid rule/reference báo đúng field; output versioned | IN PROGRESS |
| `W9.3` | `EP-05-S01/09` | Rubric API/compiler test suite | Q | Y | 3 | `W9.1/2` | Test lifecycle, total weight, rule conflict và reproducible compile output | IN PROGRESS |
| `W9.4` | `EP-05-S01/09` | Rubric domain model và template library | Y | Q | 5 | `W2.5` | Criterion–checklist–evidence–level–rule có định nghĩa và rubric mẫu thực tế | IN PROGRESS |
| `W9.5` | `EP-05-S09` | LOCAL/GRAPH assignment và deterministic decision-rule spec | Y | Q | 5 | `W9.4` | Mỗi checklist có mode, evidence requirement và three-state decision table | IN PROGRESS |
| `W9.6` | `EP-05-S01` | Rubric management UI | Y | Q | 3 | `W9.1/2` | Tạo/sửa/preview/publish; validation và version history hiển thị đúng | CONDITIONAL |

**Tải kế hoạch:** Q = 13 SP, Y = 13 SP.

### Tuần 10 — 10/10 đến 16/10/2026

**Milestone:** LOCAL Evidence Assessment v1 đạt `G-05`.

| ID | Backlog | Work package | Owner | Review | SP | Phụ thuộc | Đầu ra/DoD riêng | Trạng thái |
|---|---|---|---|---|---:|---|---|---|
| `W10.1` | `EP-05-S02/03/04` | LOCAL assessment orchestration và API | Q | Y | 5 | `W7.3`, `W9.2`, `W10.4` | Criterion chạy retrieval→pack→verification; liên kết run/checklist/rubric/report version | IN PROGRESS |
| `W10.2` | `EP-05-S04` | Evidence Pack persistence và evidence validator | Q | Y | 3 | `W10.1/5` | Bắt buộc chunk/page/section/relevance/provenance; dangling/cross-report evidence bị loại | IN PROGRESS |
| `W10.3` | `EP-05-S03/04`, `EP-11-S02` | Authorization, no-evidence, timeout và integration tests | Q | Y | 5 | `W10.1/2` | Tenant/report isolation, stale version, retry và prompt-injection fixture đạt | IN PROGRESS |
| `W10.4` | `EP-05-S02` | Criterion query strategy và LOCAL Evidence Retrieval | Y | Q | 5 | `W7.3`, `W9.5` | Checklist query tạo Top-K evidence đúng report; config/run truy vết được | IN PROGRESS |
| `W10.5` | `EP-05-S03` | Three-state verification baseline | Y | Q | 5 | `W5.3/6`, `W10.4` | MET/UNMET/CANNOT_ASSESS đúng JSON Schema và chỉ dựa Evidence Pack | IN PROGRESS |
| `W10.6` | `EP-05-S05` | Ground-truth cases và pilot LOCAL assessment | Y | Q | 3 | `W10.4/5` | Case đủ/thiếu/mâu thuẫn; báo label metric, evidence recall và lỗi sơ bộ | IN PROGRESS |

**Tải kế hoạch:** Q = 13 SP, Y = 13 SP.

### Tuần 11 — 17/10 đến 23/10/2026

**Milestone:** Evidence Graph v1 có provenance đầy đủ.

| ID | Backlog | Work package | Owner | Review | SP | Phụ thuộc | Đầu ra/DoD riêng | Trạng thái |
|---|---|---|---|---|---:|---|---|---|
| `W11.1` | `EP-05-S06` | Graph persistence, index và version/rebuild strategy | Q | Y | 5 | `W2.2`, `W4.4`, `W11.4` | Node/edge versioned; index report/type/relation; rebuild/cleanup được test | TODO |
| `W11.2` | `EP-05-S06` | Graph provenance/query API | Q | Y | 5 | `W11.1` | Node/edge mở ngược tới chunk/span/run; API không trả graph ngoài quyền | TODO |
| `W11.3` | `EP-05-S06` | Graph build worker và integration tests | Q | Y | 3 | `W11.1/2`, `W11.5` | Re-extraction idempotent; version không trộn; dangling/cross-report edge bị phát hiện | TODO |
| `W11.4` | `EP-05-S06` | Claim/entity/relation schema và ontology mapping | Y | Q | 5 | `W4.2`, `W9.5` | Claim/concept/method/result/conclusion/source và relation có định nghĩa/ví dụ | IN PROGRESS |
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

**Milestone baseline:** Targeted Question MVP nếu review đầu W14 xác nhận
`G-06` vẫn đúng forecast; nếu không, dành capacity cho Graph/Assessment recovery.

| ID | Backlog | Work package | Owner | Review | SP | Phụ thuộc | Đầu ra/DoD riêng | Trạng thái |
|---|---|---|---|---|---:|---|---|---|
| `W14.1` | `EP-08-S01` | Findings adapter từ similarity/rubric/evidence | Q | Y | 5 | `W8.3`, `W13.1`, điều kiện cut-line | Chuẩn hóa issue/criterion/evidence/severity/source cho generator | CONDITIONAL |
| `W14.2` | `EP-08-S01/02` | Question API, provenance, version và audit | Q | Y | 5 | `W14.1/4` | Câu liên kết issue/evidence/purpose; create/edit/approve audit đầy đủ | CONDITIONAL |
| `W14.3` | `EP-01-S04` | Go/no-go decision cho auxiliary style/AI-writing warning | Q | Y | 3 | `G-04`, `G-06` | Ghi capacity/data/ethics decision; `EP-06-S03` vẫn ICEBOX nếu không Go; nếu mở phải tách khỏi điểm, có disclaimer và limitation | CONDITIONAL |
| `W14.4` | `EP-08-S01` | Grounded question schema/prompt và generation | Y | Q | 5 | `W5.1/3`, `W14.1` | Câu có purpose/answerability/evidence; output ngoài schema bị loại | CONDITIONAL |
| `W14.5` | `EP-08-S02` | Lecturer question review/edit UI | Y | Q | 5 | `W14.2/4` | Xem căn cứ, edit/reject/approve; draft chưa duyệt không được dùng | CONDITIONAL |
| `W14.6` | `EP-08-S02`, `EP-10-S04` | Question quality test set và pilot | Y | Q | 3 | `W14.4/5` | Chấm relevance/grounding/answerability/usefulness; lưu accept/edit/reject | CONDITIONAL |

**Capacity envelope:** tối đa Q = 13 SP, Y = 13 SP. Trong đó Question là
conditional; nếu no-go, không để trống capacity mà kéo Graph/Assessment
recovery theo mục 11.

### Tuần 15 — 14/11 đến 20/11/2026

**Milestone:** Human-in-the-loop dashboard, Feedback Log và export v1.

| ID | Backlog | Work package | Owner | Review | SP | Phụ thuộc | Đầu ra/DoD riêng | Trạng thái |
|---|---|---|---|---|---:|---|---|---|
| `W15.1` | `EP-09-S02/07` | Unified result API và Feedback Log | Q | Y | 5 | `W8.3`, `W13.1`; `W14.2` nếu enabled | Tổng hợp module output; edit giữ original/before-after/actor/time/reason | CONDITIONAL |
| `W15.2` | `EP-09-S03` | Final report/export service | Q | Y | 5 | `W15.1` | HTML/JSON có version/evidence/review/disclaimer và fixture ổn định; PDF chỉ thêm nếu còn capacity | CONDITIONAL |
| `W15.3` | `EP-02-S08`, `EP-09-S02/03/06/07` | Lecturer workflow RBAC/audit và lifecycle archive/delete orchestration | Q | Y | 3 | `W2.6`, `W15.1/2` | Accept/Edit/Reject/publish/archive/delete đúng quyền và audit; purpose/retention/approver gate được enforce; cascade job file/chunk/vector/graph/result/cache idempotent; giữ AI suggestion gốc | CONDITIONAL |
| `W15.4` | `EP-09-S02` | Evaluation Dashboard UI | Y | Q | 5 | `W15.1` | Similarity/rubric/evidence/rationale/score nhất quán; hiển thị question nếu enabled | CONDITIONAL |
| `W15.5` | `EP-05-S04`, `EP-09-S02` | Accept/Edit/Reject interactions và concurrent-state handling | Y | Q | 5 | `W15.3/4` | Review từng finding/checklist; xử lý unsaved/error/concurrent edit | CONDITIONAL |
| `W15.6` | `EP-09-S02`, `EP-10-S04` | Usability/accessibility smoke và export-view test | Y | Q | 3 | `W15.4/5` | Lecturer flow hoàn tất; keyboard/focus/empty/error và rendered export được kiểm | CONDITIONAL |

**Tải kế hoạch:** Q = 13 SP, Y = 13 SP.

### Tuần 16 — 21/11 đến 27/11/2026

**Milestone:** Release Candidate 1 và feature freeze.

| ID | Backlog | Work package | Owner | Review | SP | Phụ thuộc | Đầu ra/DoD riêng | Trạng thái |
|---|---|---|---|---|---:|---|---|---|
| `W16.1` | `EP-11-S05` | E2E orchestration upload→reviewed final report | Q | Y | 5 | `G-04`, `G-06`, `W15.2/5` | Một run tạo parse, similarity, assessment và reviewed export; tạo question nếu feature được enable | TODO |
| `W16.2` | `EP-09-S01`, `EP-11-S05` | Retry/cache/progress/error hardening | Q | Y | 3 | `W16.1` | Retry idempotent; cache version-aware; partial failure/resume được test | TODO |
| `W16.3` | `EP-11-S01/02/05` | Backend/system/RBAC/security test suite | Q | Y | 5 | `W16.1/2` | Happy/error/cross-role/upload/parser/model/graph; không còn Critical mở | TODO |
| `W16.5` | `EP-11-S05` | E2E/UAT scenario suite cho ba actor | Y | Q | 5 | `W16.1` | Bao phủ no-evidence, partial failure và manual review | TODO |
| `W16.6` | `EP-11-S01/02` | AI/retrieval/graph regression và adversarial suite | Y | Q | 5 | `W16.1` | Fixed dataset bắt schema/provenance/quality regression ngoài tolerance | TODO |
| `W16.7` | `EP-11-S05` | Defect triage và feature-freeze evidence | Y | Q | 3 | `W16.3/5/6` | Lỗi có severity/owner; P1/P2 defer bằng quyết định | TODO |

**Tải kế hoạch:** Q = 13 SP, Y = 13 SP. Full operations/user guide được
gộp vào `W22.4`; nội dung chương hiện thực/kiểm thử được gộp vào `W22.1`.

### Tuần 17 — 28/11 đến 04/12/2026

**Milestone:** Dataset, ground truth và protocol thực nghiệm được freeze (`G-08`).

| ID | Backlog | Work package | Owner | Review | SP | Phụ thuộc | Đầu ra/DoD riêng | Trạng thái |
|---|---|---|---|---|---:|---|---|---|
| `W17.1` | `EP-01-S02`, `EP-10-S01` | Dataset manifest, version, checksum, rights state và split | Y | Q | 5 | `W2.6`, `W6.4`, `W10.6` | Train/validation/test có provenance và approval state; split theo document/source; validator loại sample chưa duyệt | TODO |
| `W17.2` | `EP-10-S06` | Metric/statistics scripts và unit tests | Q | Y | 5 | `W17.1` | Recall/MRR/nDCG/P/R/F1/evidence/agreement chạy tự động và đúng case biết trước | TODO |
| `W17.3` | `EP-10-S01/06` | Leakage, duplicate và label-quality audit | Q | Y | 3 | `W17.1/2` | Near-duplicate/overlap được báo; final test khóa trước run chính | TODO |
| `W17.4` | `EP-10-S05` | Clean reproduction dry run | Q | Y | 3 | `W17.1–3` | Từ manifest/config sinh lại một bảng pilot trên môi trường sạch | TODO |
| `W17.5` | `EP-04-S01`, `EP-10-S01` | Adjudication và freeze similarity ground truth đã xây dần từ W06–W08 | Q | Y | 2 | `W6.4`, `W8.4`, `W17.1` | Bốn nhãn/source span đầy đủ; duplicate/leakage flags xử lý; ambiguous case có adjudication; reviewer Y ký freeze | TODO |
| `W17.6` | `EP-10-S01` | Completeness QA và freeze report–rubric–checklist annotation đã xây dần từ W10–W13 | Y | Q | 2 | `W10.6`, `W13.6` | MET/UNMET/CANNOT_ASSESS, evidence span và lecturer note đầy đủ | TODO |
| `W17.7` | `EP-10-S01` | Annotation guideline, QA và inter-rater review | Y | Q | 3 | `W17.5/6` | Guideline có example; agreement và cách xử lý bất đồng được báo | TODO |
| `W17.8` | `EP-01-S02`, `EP-10-S01` | Dataset card, rights/ethics và limitations | Y | Q | 3 | `W17.1`, `W17.5–7` | Nguồn/quyền/population/bias/retention/giới hạn rõ | TODO |

**Tải kế hoạch:** Q = 13 SP, Y = 13 SP. W17 chỉ QA/adjudicate/freeze;
không dồn việc gán nhãn lần đầu vào tuần này.

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

**Milestone:** Đánh giá Lecturer Support, Feedback Log và tính hữu ích hệ
thống hoàn tất; đánh giá câu hỏi chỉ chạy nếu Targeted Questions được enable.

| ID | Backlog | Work package | Owner | Review | SP | Phụ thuộc | Đầu ra/DoD riêng | Trạng thái |
|---|---|---|---|---|---:|---|---|---|
| `W20.1` | `EP-10-S04`, `EP-09-S07` | Study tooling, telemetry export và privacy controls | Q | Y | 5 | `W15.1`, `W17.8` | Form/rating/log dùng participant/sample ID ẩn danh; consent/access rõ | TODO |
| `W20.2` | `EP-10-S04`; `EP-08-S02` nếu enabled | Quantitative lecturer-support/question evaluation pipeline | Q | Y | 5 | `W20.1/4` | Tính usability và A/E/R từ raw artifact; thêm relevance/evidence-grounding/answerability khi question enabled | TODO |
| `W20.3` | `EP-09-S07`, `EP-10-S04/05`; `EP-08-S02` nếu enabled | Lecturer-support regression và reproducible artifact package | Q | Y | 3 | `W15.6`, `W20.2`; `W14.6` nếu enabled | Evidence/feedback và question nếu enabled giữ provenance; raw→table/plot tái sinh | TODO |
| `W20.4` | `EP-10-S04`; `EP-08-S02` nếu enabled | Lecturer expert/usability evaluation | Y | Q | 5 | `W15.6`, `W20.1`; `W14.6` nếu enabled | Protocol cố định; người đánh giá làm task/rating trên sample | TODO |
| `W20.5` | `EP-09-S07`, `EP-10-S04` | Feedback Log và qualitative thematic analysis | Y | Q | 5 | `W20.4` | Lý do accept/edit/reject được mã hóa; example ẩn danh/review chéo | TODO |
| `W20.6` | `EP-12-S01` | Viết kết quả hỗ trợ, hạn chế và hướng cải tiến | Y | Q | 3 | `W20.2/5` | Phân biệt kết quả đo, cảm nhận người dùng và phần chưa đủ evidence | TODO |

**Tải kế hoạch:** Q = 13 SP, Y = 13 SP.

### Tuần 21 — 26/12/2026 đến 01/01/2027

**Milestone:** Release Candidate 2 đạt ngưỡng hiệu năng, bảo mật và tái lập (`G-09`).

| ID | Backlog | Work package | Owner | Review | SP | Phụ thuộc | Đầu ra/DoD riêng | Trạng thái |
|---|---|---|---|---|---:|---|---|---|
| `W21.1` | `EP-11-S03` | Profiling latency/throughput/RAM/VRAM theo stage | Q | Y | 5 | `G-07`, `W18.3`, `W19.3`, `W20.3` | p50/p95 và bottleneck có profile; hardware/workload ghi rõ | TODO |
| `W21.2` | `EP-11-S03` | Tối ưu bottleneck do profiling xác định; ưu tiên local AI, lexical/vector và reranker | Q | Y | 5 | `W21.1` | Cải thiện metric/resource; quality regression trong tolerance; graph/cache/queue chỉ thay thế một phần cùng capacity nếu là bottleneck | TODO |
| `W21.4` | `EP-09-S06`, `EP-11-S01/02/03` | Lifecycle cascade, security/privacy và backup/restore closeout | Q | Y | 3 | `W15.3`, `W16.3`, `W17.8` | Archive/delete E2E loại file/chunk/vector/graph/result/cache khỏi active store theo policy; tombstone/audit không chứa nội dung; backup expiry/restore diễn tập; upload/isolation/log review đạt, không còn Critical/High mở | TODO |
| `W21.5` | `EP-11-S03/04` | Quality regression, defect verification và known-issues review trên RC2 | Y | Q | 5 | `W21.2`, `W21.4` | Parser/similarity/assessment và question nếu enabled đạt threshold; lỗi có evidence đóng hoặc mức chấp nhận/workaround | TODO |
| `W21.6` | `EP-09-S04`, `EP-11-S03` | Resource benchmark và configuration recommendation | Y | Q | 5 | `W21.1/2` | Bảng latency/throughput/RAM/VRAM; khóa config demo/experiment | TODO |
| `W21.8` | `EP-10-S05`, `EP-11-S04` | Reproducibility/configuration freeze | Y | Q | 3 | `W21.5/6` | Khóa commit/dependency/model/index/config; rerun trong tolerance | TODO |

**Tải kế hoạch:** Q = 13 SP, Y = 13 SP. Chỉ tối ưu đúng bottleneck có
profile; không cộng thêm một gói graph/cache/queue riêng.

### Tuần 22 — 02/01 đến 08/01/2027

**Milestone:** Luận văn đầy đủ phiên bản 1 gửi GVHD.

| ID | Backlog | Work package | Owner | Review | SP | Phụ thuộc | Đầu ra/DoD riêng | Trạng thái |
|---|---|---|---|---|---:|---|---|---|
| `W22.1` | `EP-12-S01` | Viết chương kiến trúc, hiện thực, tích hợp và kiểm thử | Q | Y | 5 | `G-07`, `G-09` | Khớp code/diagram/schema/API/test report hiện hành; decision có lý do | TODO |
| `W22.2` | `EP-12-S01` | Viết phần thực nghiệm Similarity và hiệu năng | Q | Y | 5 | `W18.3–5`, `G-09` | Bảng/claim liên kết raw artifact; protocol/ablation đủ tái lập | TODO |
| `W22.4` | `EP-12-S02` | Hướng dẫn cài đặt, triển khai, vận hành và API | Q | Y | 3 | `W21.8` | Người mới clean install và chạy fixture/demo; có healthcheck, backup/rollback và known issues | TODO |
| `W22.5` | `EP-12-S01` | Hoàn thiện tổng quan, cơ sở lý thuyết, phương pháp và references | Y | Q | 5 | `W1.3`, `G-08` | Citation/thuật ngữ đầy đủ; phương pháp/data/ethics khớp protocol freeze | TODO |
| `W22.6` | `EP-12-S01` | Viết kết quả Assessment và Lecturer Support | Y | Q | 5 | `W19.3–5`, `W20.2–5` | Bảng/error/feedback/limitation truy vết artifact | TODO |
| `W22.8` | `EP-12-S02` | Hướng dẫn sử dụng | Y | Q | 3 | `W15.4–6`, `G-09` | Upload/analysis/review/export/failure recovery có hướng dẫn/ảnh | TODO |

**Tải kế hoạch:** Q = 13 SP, Y = 13 SP. Đồng bộ UML/schema/API và
reproducibility appendix là DoD của các chương liên quan, không là gói riêng.

### Tuần 23 — 09/01 đến 15/01/2027

**Milestone:** Release 1.0 và bộ bảo vệ bản nháp hoàn chỉnh (`G-10`).

| ID | Backlog | Work package | Owner | Review | SP | Phụ thuộc | Đầu ra/DoD riêng | Trạng thái |
|---|---|---|---|---|---:|---|---|---|
| `W23.1` | `EP-11-S04` | Xử lý feedback code/sản phẩm | Q | Y | 5 | `EXT:GVHD feedback`, `W22.1/2/4/5/6/8` | Mỗi góp ý có commit/status hoặc lý do; không mở scope mới | TODO |
| `W23.2` | `EP-10-S05`, `EP-11-S04` | Audit báo cáo–code–data–số liệu và đóng gói Release 1.0 | Q | Y | 5 | `W21`, `W23.1` | Model/config/data/metric khớp artifact; tag/source/migration/docs/checksum/release notes đầy đủ; không dữ liệu cấm | TODO |
| `W23.3` | `EP-12-S02` | Demo environment, script và offline fallback | Q | Y | 3 | `W23.2` | Chạy từ sạch, đúng thời lượng, dùng fixture hợp lệ và có phương án khi model/service lỗi | TODO |
| `W23.5` | `EP-12-S01` | Xử lý feedback và hoàn thiện luận văn gần cuối | Y | Q | 5 | `EXT:GVHD feedback`, `W22.5/6` | Comment resolve/truy vết; số liệu chỉ đổi từ script/artifact | TODO |
| `W23.6` | `EP-12-S01` | Hoàn thiện contribution, kết luận và future work | Y | Q | 5 | `W18.6`, `W19.6`, `W20.6` | Không overclaim; phân biệt prototype/result/extension | TODO |
| `W23.7` | `EP-12-S02` | Slide bảo vệ bản nháp | Y | Q | 3 | `W23.5/6` | Problem–method–demo–result–limitation; số liệu thống nhất | TODO |

**Tải kế hoạch:** Q = 13 SP, Y = 13 SP. Audit được gộp vào release gate;
video/Q&A hoàn thiện một lần ở W24, tránh làm trùng.

### Tuần 24 — 16/01 đến 22/01/2027

**Milestone:** Submission readiness; không mở feature mới (`G-11`).

| ID | Backlog | Work package | Owner | Review | SP | Phụ thuộc | Đầu ra/DoD riêng | Trạng thái |
|---|---|---|---|---|---:|---|---|---|
| `W24.1` | `EP-11-S04` | Final functional/regression và fallback test | Q | Y | 5 | `W23.2/3` | Demo/fixed suite và offline fallback đạt; chỉ sửa defect | TODO |
| `W24.2` | `EP-11-S03`, `EP-12-S03` | Backup/restore và checksum verification | Q | Y | 5 | `W24.1` | Backup độc lập; restore thử thành công; checksum khớp | TODO |
| `W24.3` | `EP-12-S03` | Submission/release package | Q | Y | 3 | `W24.1/2` | Gói mở được, quyền/link đúng, loại dữ liệu không được phép; kèm fallback đã kiểm | TODO |
| `W24.5` | `EP-12-S01/03` | Final formatting, citation và similarity review | Y | Q | 5 | `W23.5` | Đúng mẫu Khoa; citation hợp lệ; xử lý đoạn trùng không hợp lệ | TODO |
| `W24.6` | `EP-12-S02/03` | Hoàn thiện báo cáo, slide, video, rehearsal và Q&A | Y | Q | 5 | `W24.5`, `W23.7` | Artifact dùng cùng số liệu/version và mở/chạy được; rehearsal đúng thời lượng, phân vai và lỗi được xử lý | TODO |
| `W24.7` | `EP-12-S03` | Forms, inventory và submission checklist | Y | Q | 3 | `W24.2/6` | Đủ biểu mẫu/xác nhận/tên file/danh mục thành phần | TODO |

**Tải kế hoạch:** Q = 13 SP, Y = 13 SP. Offline fallback và rehearsal được
đưa vào DoD của gói demo/final thay vì tạo work package trùng.

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
| 14 | 13 | 13 | Conditional Question capacity / Graph recovery |
| 15 | 13 | 13 | Human-in-the-loop v1 |
| 16 | 13 | 13 | `G-07` RC1/Feature freeze |
| 17 | 13 | 13 | `G-08` Dataset freeze |
| 18 | 13 | 13 | RQ1 result freeze |
| 19 | 13 | 13 | RQ2 result freeze |
| 20 | 13 | 13 | Support evaluation freeze |
| 21 | 13 | 13 | `G-09` RC2 |
| 22 | 13 | 13 | Thesis v1 |
| 23 | 13 | 13 | `G-10` Release 1.0 |
| 24 | 13 | 13 | `G-11` Submission readiness |
| **Tổng** | **307** | **307** | Cân bằng tuyệt đối theo SP |

Mọi tuần hiện không vượt trần 13 SP/người. Các work package trùng được gộp vào
DoD của gate/release tương ứng; tối ưu ngoài bottleneck, PDF export, full
Docling/GROBID và Targeted Questions không được cộng thêm capacity. Nếu velocity
thấp, phải nhập remaining SP và cắt các mục `CONDITIONAL`/P1 phụ trước; không
cắt research-core của hai pipeline, data-rights, security, provenance, hai thực
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

Đường găng thực thi v1.7 từ ngày 19/10/2026:

```text
Clean branch + approved data
→ Pipeline 1 retrieval/reranking
→ classification + span/coverage + document aggregation + report
→ Rubric Compiler
→ LOCAL evidence + three-state verification
→ Evidence Graph + GRAPH retrieval/router
→ grounded rationale + deterministic scoring
→ offline E2E/review package
→ dataset/protocol freeze
→ locked RQ1/RQ2 experiments
```

Hai pipeline dùng chung parser/chunker, provenance, dataset governance và
experiment runner. Chúng không được dùng chung final-test feedback: Pipeline 1
khóa trên DEV1 trước khi mở TEST0; Pipeline 2 khóa protocol trên pilot được
duyệt trước khi chạy tập đánh giá cuối.

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

## 11. Recovery và reforecast v1.7 — ưu tiên hoàn thành hai pipeline

Các bảng tuần ở mục 7 tiếp tục là baseline để đo schedule variance; không sửa
ngược ngày hoặc SP lịch sử. Từ 19/10/2026, bảng dưới đây là thứ tự thực thi hiện
hành. SP trong bảng là **remaining SP đã re-estimate**, không cộng thêm vào SP
baseline; mỗi người vẫn tối đa 13 SP/tuần.

| Cửa sổ | Q — tối đa 13 remaining SP | Y — tối đa 13 remaining SP | Kết quả bắt buộc |
|---|---|---|---|
| **W10 — 10–16/10** | Đã tạo Pipeline 1 technical slice, quota-union/evidence budget, exact alignment/unique coverage, aggregation và Similarity Report; đã nối local API/worker (ghi nhận actual, không cộng lại SP) | Đã tạo synthetic hard-negative/no-source/quote cases, guideline và local review flow; dataset approval/gold labels chưa đóng | Technical slice chạy một lệnh; semantic candidate không bị gán nhãn khi chưa có verifier; chưa tuyên bố empirical pass |
| **W11 — 17–23/10** | Commit/tách PR cho API/golden/core contracts/app fixes; chạy clean test; hoàn thiện compiler/output schema và bảo vệ exact evidence (8); chuẩn bị graph persistence interface, chưa dựng quá ontology khi extraction chưa khóa (5) | Review API/UX/rubric/ontology (4); xác minh quyền và report/version của private pilot, gán nhãn độc lập + adjudication nếu đủ điều kiện (6); khóa citation/four-label guideline và DEV1 approval request (3) | Hai technical slice chạy và có test; `G-02/G-03` có thể đóng sau review; `G-04/G-05` vẫn OPEN đến khi có dataset được duyệt và nhãn chéo |
| **W12 — 24–30/10** | LOCAL orchestration, Evidence Pack validator và failure/authorization tests `W10.1–W10.3` (13) | Criterion query/LOCAL retrieval, three-state verifier và pilot cases `W10.4–W10.6` (13) | Rubric→checklist→Top-K evidence→MET/UNMET/CANNOT_ASSESS chạy offline; đạt `G-05` |
| **W13 — 31/10–06/11** | Graph persistence/query/build và integration tests `W11.1–W11.3` (13) | Ontology, claim/entity/relation extraction và graph QA `W11.4–W11.6` (13) | Evidence Graph versioned, idempotent; mọi node/edge truy ngược được report version→chunk→raw span→run |
| **W14 — 07–13/11** | Graph retrieval, router/LOCAL fallback và performance tests `W12.1–W12.3` (13) | Seed selection, deterministic PPR, bounded multi-hop ranking và router evaluation `W12.4–W12.6` (13) | LOCAL/GRAPH/SELECTIVE có reason; graph lỗi fail-safe; có bảng LOCAL–GRAPH quality/latency trên cùng cases |
| **W15 — 14–20/11** | Assessment orchestration/persistence, consistency validator và deterministic/RBAC tests `W13.1–W13.3` (13) | Evidence-grounded verifier/rationale, deterministic scoring và consistency analysis `W13.4–W13.6` (13) | Pipeline 2 v1 đạt `G-06`: mỗi checklist có status, evidence IDs, rationale được hỗ trợ và score xác định |
| **W16 — 21–27/11** | Offline E2E orchestration, retry/cache/failure và system tests `W16.1–W16.3` (13) | E2E/UAT, regression/adversarial suite và defect triage `W16.5–W16.7` (13) | Research RC1: PDF/DOCX→parse/chunk→Pipeline 1 + Pipeline 2→reviewable JSON/HTML chạy từ clean config; feature freeze |
| **W17 — 28/11–04/12** | Metric/statistics tests, leakage audit, clean reproduction và similarity adjudication `W17.2–W17.5` (13) | Manifest/rights/split, assessment annotation freeze, inter-rater QA và data card `W17.1`, `W17.6–W17.8` (13) | `G-08`: dataset/protocol/metric được version/checksum/freeze; TEST0 chỉ được mở theo protocol sau gate |

### 11.1. Definition of Done của hai pipeline trong reforecast

**Pipeline 1 — Similarity:** một lệnh phải thực hiện được
`parse/chunk → BM25 + Dense → RRF → Cross-Encoder → bốn nhãn similarity → exact
span/unique coverage → document aggregation → Similarity Report`. Artifact phải
có run manifest, model/config/seed/commit/hardware/timing, exact provenance,
negative/no-source và quote/citation cases. Báo cáo phải ghi rõ similarity không
đồng nghĩa đạo văn.

**Pipeline 2 — Assessment:** một lệnh phải thực hiện được
`rubric → atomic LOCAL/GRAPH checklists → evidence retrieval → Evidence Pack →
SUPPORTED/CONTRADICTED/INSUFFICIENT → MET/UNMET/CANNOT_ASSESS → grounded
rationale → deterministic score`. Mọi kết luận phải dẫn evidence span hợp lệ;
thiếu evidence phải abstain/chuyển review, không tự suy diễn.

File/in-memory adapter và JSON/HTML review package được chấp nhận cho
research-core W10–W16. MongoDB/API/UI production vẫn là work package riêng;
không được dùng offline RC1 để tuyên bố đã đạt đầy đủ product gate `G-07`.

### 11.2. Dataset và experiment guardrail

- PAN DEV0 hiện tại được khóa làm diagnostic set; dừng tune lặp lại trên 30
  parent này.
- DEV1 phải được regenerate từ clean commit, zero-overlap audit và governance
  approval trước khi chọn phương pháp. TEST0 giữ sealed đến khi config đã khóa.
- Pipeline 2 cần report–rubric in-domain đã được phép dùng, ẩn danh và gán nhãn
  chéo. MMDocIR/HoVer/HARMOGEN-R chỉ kiểm thử component, không thay thế
  end-to-end in-domain assessment.
- Không có approval thì chỉ được báo kết quả synthetic/component; không được
  ghi `G-04/G-05/G-06/G-08 PASS` hoặc đưa claim end-to-end vào bài báo.

### 11.3. Cut-line

Trong W10–W17, tạm hoãn toàn bộ `W14.1–W14.6` Targeted Questions,
`W8.6/W9.6/W15.1–W15.6` product UI/dashboard đầy đủ, AI-writing warning, OCR,
full Docling/GROBID, Neo4j optimization và PDF export. Review/export tối thiểu
được thực hiện bằng fixture JSON/Markdown/HTML trong `W8.3/W13.1/W16.1`.

Nếu GRAPH trễ sau W14, giữ LOCAL là đường hoàn chỉnh và thu hẹp GRAPH thành
component pilot có limitation; không cắt provenance, verifier/scorer,
rights/consent, annotation review, leakage audit, reproducibility, W17 freeze
hoặc hạn nộp 23/01/2027.

## 12. Change Log và phê duyệt

| Phiên bản | Ngày | Thay đổi |
|---|---|---|
| 1.0 | 21/08/2026 | Tách WBS khỏi Product Backlog; phân rã đúng 24 tuần Excel/phạm vi 2 hướng chính + 1 bổ sung; gán owner/reviewer Q/Y; recovery trừ carry-over vào capacity; bổ sung gate evidence, data-rights/security/lifecycle và closure 23/01; cân bằng 325 SP/người |
| 1.1 | 03/09/2026 | Sửa MSSV thành viên Y thành `52200229`; ghi nhận scope/pipeline và dataset-task mapping đã chốt; cập nhật actual W01–W04; parser/chunker baseline ở commit `3c1c133` đạt `2 passed, 1 skipped` nhưng chưa đạt production DoD; chuyển parser plan sang benchmark-driven adapter; tách prototype khỏi worker/provenance/golden benchmark; reforecast `G-02→11/09`, `G-03→25/09`, `G-04→16/10`, `G-05→30/10`, `G-06→20/11`; giữ `G-07` trở đi và hạn nộp; đưa mọi tuần về tối đa 13 SP/người, tổng 307 SP/người; Targeted Questions/PDF/full Docling–GROBID là conditional |
| 1.2 | 03/09/2026 | Bổ sung evidence `W2.1`: C4 Context/Container/Deployment, data flow với 10 trust boundary và threat-model/adversarial plan v1; giữ actual 50%/`CARRY-OVER` theo quy tắc WBS cho đến khi đồng bộ `W1.1` và Y review xác nhận |
| 1.3 | 10/09/2026 | Mở PR #5 cho `W2.1`; bổ sung ADR-001 và data dictionary `W2.2` gồm MongoDB deployment, collection/index, provenance, migration/rebuild, retention/tombstone/cascade và deny-by-default; cập nhật actual `W2.2` lên 75% nhưng giữ `CARRY-OVER` đến khi Y review |
| 1.4 | 10/09/2026 | Ghi nhận PR #5 đã được Y approve/merge; bổ sung API Contract v1 và OpenAPI review candidate `W2.3`; cập nhật actual `W2.1/W2.3` nhưng chưa đóng `W2.3` khi branch chưa vào `main` |
| 1.5 | 16/09/2026 | Ghi nhận PR #6 `W2.2` đã được Y approve/merge; bổ sung quan hệ `document_elements → chunks`; đóng design task `W2.2` ở 100%; runtime MongoDB/provenance tiếp tục ở `W3.1/W4.2` |
| 1.6 | 12/10/2026 | Đối chiếu lại repository: scope sync PR #8, provenance PR #9, offline runner PR #11, PAN pilot PR #12 và A1–A5 DEV0; phân biệt component diagnostic với pipeline hoàn chỉnh; cập nhật actual/gate; reforecast W10–W17 ưu tiên Pipeline 1, Rubric/LOCAL, GRAPH/Assessment, offline E2E và dataset freeze; đưa Targeted Questions/UI polish/OCR/full Docling–GROBID/PDF xuống cut-line |
| 1.7 | 19/10/2026 | Ghi nhận app local upload→worker→hai pipeline→review, Pipeline 1 exact-span/coverage/report, Pipeline 2 compiler/LOCAL/GRAPH-v0/verifier/scorer/report; tích hợp API/UX/rubric/golden benchmark/ADR/output contract vào working tree; bổ sung contract/regression/fixture tests; cập nhật W2–W11 theo artifact thật nhưng giữ gate OPEN đến khi commit-review-merge, governance và gold annotation hoàn tất |

| Vai trò | Họ tên | Quyết định | Ngày |
|---|---|---|---|
| Nhóm trưởng | Nguyễn Trần Ngọc Quý | Chờ review/ký |  |
| Thành viên | Võ Thị Kim Yến | Chờ review/ký |  |
| GVHD | Vũ Đình Hồng | Chờ xác nhận baseline |  |
