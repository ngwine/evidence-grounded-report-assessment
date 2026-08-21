# PRODUCT BACKLOG

## Evidence-Grounded Plagiarism Checking and Student Report Assessment

| Thuộc tính | Giá trị |
|---|---|
| Phiên bản | 1.0 |
| Ngày lập/cập nhật | 21/08/2026 |
| Product Owner/nhóm trưởng | Nguyễn Trần Ngọc Quý — 523H0087 |
| Thành viên | Nguyễn Trần Ngọc Quý (Q), Võ Thị Kim Yến (Y) |
| GVHD | Vũ Đình Hồng |
| Nguồn phạm vi | [`README.md`](../../README.md) và mô tả đã chốt: 2 hướng chính (Similarity, Evidence-grounded Assessment) + 1 hướng bổ sung (Targeted Questions) |
| Hồ sơ trước rebaseline | `docs/week-01/W1-03-dac-ta-yeu-cau-v1.md`; `docs/week-01/W1-04-bo-use-case.md` — chỉ dùng chi tiết không mâu thuẫn phạm vi mới |
| Nguồn lịch | `Schedule_KLTN_Evidence_Grounded.xlsx` — 24 tuần, 08/08/2026–22/01/2027; SHA-256 `548f068bdc71d022e29f8def983b10f689d14606cc0db6d33c0783189f318984` |
| Kế hoạch thực thi | [`WBS_VA_PHAN_CONG.md`](./WBS_VA_PHAN_CONG.md) |
| Trạng thái baseline | Phạm vi nội bộ đã chốt theo hai hướng nghiên cứu chính và một hướng bổ sung; phân công v1 chờ Q/Y review, gate cần GVHD vẫn để mở |

---

## 1. Quy ước backlog

### 1.1. Priority

- `P0`: critical path của lịch Excel hoặc bắt buộc để chứng minh hai hướng
  nghiên cứu chính.
- `P1`: vẫn thuộc phạm vi đã chốt nhưng có thể giản lược mức tự động hóa/UX;
  chỉ triển khai sau P0 của tuần.
- `P2`: extension/optional; không nằm trong cam kết lịch chính và mặc định để
  `ICEBOX` cho đến khi gate liên quan đạt.

Priority chỉ có ý nghĩa xếp hàng khi item không mang `OUT OF SCOPE`; các item
ngoài phạm vi giữ priority lịch sử để truy vết, không tạo cam kết triển khai.

### 1.2. Status

- `DONE`: artifact đã tồn tại, đạt DoD và được review.
- `IN PROGRESS`: đã có một phần artifact nhưng chưa đủ DoD.
- `PLANNED`: đã phân tích và phân công nhưng chưa có bằng chứng triển khai.
- `BLOCKED`: không thể tiếp tục do dependency/decision ngoài task chưa đóng.
- `ICEBOX`: chưa cam kết thực hiện trong lịch 24 tuần.
- `OUT OF SCOPE`: giữ canonical ID để truy vết lịch sử nhưng không thuộc phạm
  vi đã chốt; chỉ mở lại bằng change request được duyệt.

`Ready` là cột workflow của issue board, không phải giá trị `Status`; item ở
cột `Ready` vẫn mang `PLANNED` cho đến khi bắt đầu.

### 1.3. Story point

- `1 SP`: thay đổi rất nhỏ, ít bất định.
- `2–3 SP`: item nhỏ, đầu ra và cách kiểm tra rõ.
- `5 SP`: item vừa, cần thiết kế/tích hợp/test.
- `8 SP`: item lớn hoặc có rủi ro nghiên cứu; phải tách thành work package
  trước khi chuyển `IN PROGRESS`.

SP ở Product Backlog ước lượng outcome/user story. SP ở WBS ước lượng work
package thực thi; không cộng hai cấp với nhau.

### 1.4. Definition of Ready

Một item chỉ được kéo lên `Ready` khi:

1. Outcome/user story, phạm vi trong/ngoài và acceptance criteria đã rõ.
2. Có owner, reviewer, SP, target week và dependency.
3. Input, test fixture/dataset hoặc mock tối thiểu đã sẵn sàng.
4. Quyền dữ liệu, model/provider và rủi ro privacy/security đã được xử lý khi
   liên quan.
5. Thay đổi schema/API/UI có thiết kế hoặc contract trước khi code.

### 1.5. Definition of Done

- Artifact được commit và liên kết được với backlog ID.
- Code qua format/lint/type check/test phù hợp; reviewer còn lại chấp thuận.
- Tài liệu/API/schema/migration được cập nhật cùng thay đổi.
- Mọi kết quả AI/retrieval lưu evidence/provenance và phiên bản
  model/prompt/config/index/dataset.
- Metric được tạo bằng script/config có version; không tune trên final test.
- Không chứa secret, dữ liệu cá nhân hoặc báo cáo chưa được phép commit.
- Item cần GVHD/giảng viên xác nhận chỉ `DONE` khi có bằng chứng và ngày xác
  nhận.

---

## 2. Epic EP-01 — Discovery, phạm vi, dữ liệu và quản trị nghiên cứu

| ID | Backlog item/outcome | Pri. | SP | Owner | Review | Tuần | Dependency | Acceptance criteria/DoD | Status |
|---|---|---:|---:|---|---|---|---|---|---|
| `EP-01-S01` | Đồng bộ baseline mục tiêu, phạm vi, actor, Use Case, RQ và tiêu chí hoàn thành | P0 | 3 | Q | Y | W01–W03 recovery | — | Quyết định phạm vi 2 hướng chính + 1 bổ sung đã chốt; SRS/Use Case/README phải bỏ RQ/provider/reference feature cũ không còn scope, review Q/Y và lưu change log trước khi `DONE` | IN PROGRESS |
| `EP-01-S02` | Lập data/rubric inventory, quyền sử dụng, ẩn danh, retention và annotation governance | P0 | 5 | Y | Q | W01–W03 | Nguồn dữ liệu/GVHD | Mỗi nguồn có owner, license/consent, allowed purpose, classification, anonymization, retention, approver/date; deny-by-default chặn dữ liệu chưa duyệt khỏi corpus/index/experiment; vai trò gán nhãn/adjudication rõ | IN PROGRESS |
| `EP-01-S03` | Quản trị nhánh tìm nguồn ngoài hệ thống nếu được phê duyệt | P1 | 5 | Q | Y | — | Change request + quyền/provider được duyệt | Canonical story lịch sử; provider mặc định tắt; chỉ tái mở khi thay đổi phạm vi nêu quota, privacy, provenance và fallback hợp lệ | OUT OF SCOPE |
| `EP-01-S04` | Chốt nhân lực, máy demo, ngân sách và capacity/cut line | P0 | 3 | Q | Y | W01–W02; review gate W14 | — | Xác nhận hai thành viên, deadline 23/01/2027, cấu hình máy, cut line và quyết định có/không mở auxiliary warning khi review capacity W14 | IN PROGRESS |
| `EP-01-S05` | Khảo sát và xác nhận quy trình AS-IS/TO-BE với giảng viên | P0 | 3 | Y | Q | W01–W02 | `EP-01-S01` | Biên bản ghi người/ngày; giả định được đánh dấu xác nhận, bác bỏ hoặc cần làm rõ | IN PROGRESS |
| `EP-01-S06` | Xây rubric template, guideline và kế hoạch người gán nhãn | P0 | 5 | Y | Q | W02 | `EP-01-S02/05` | Rubric có criterion/checklist/evidence/weight/level/rule; guideline có ví dụ và cơ chế giải quyết bất đồng | PLANNED |

## 3. Epic EP-02 — Kiến trúc, nền tảng và security-by-design

| ID | Backlog item/outcome | Pri. | SP | Owner | Review | Tuần | Dependency | Acceptance criteria/DoD | Status |
|---|---|---:|---:|---|---|---|---|---|---|
| `EP-02-S01` | Repo, dependency manifest, Compose, CI và môi trường tái lập | P0 | 5 | Q | Y | W01–W03 | `EP-01-S04` | FE/BE/worker/DB chạy healthcheck; lint/type/test, SAST, secret và dependency scan chạy trong CI từ W03; High/Critical làm fail gate hoặc có waiver owner/expiry; README chạy trên môi trường sạch | IN PROGRESS |
| `EP-02-S02` | Thiết kế MongoDB collection, index, invariant và data dictionary | P0 | 8 | Q | Y | W02–W03 | `EP-02-S05` | Schema/version/reference/index/migration/rebuild được mô tả; source of truth và derived index tách rõ | PLANNED |
| `EP-02-S03` | Authentication, session, RBAC và user management tối thiểu | P0 | 8 | Q | Y | W03 | `EP-02-S02/06/07` | Student/Lecturer/Admin đúng ma trận; cross-user access bị chặn; authorization test đạt | PLANNED |
| `EP-02-S04` | Threat model và adversarial test plan | P0 | 5 | Q | Y | W02, cập nhật W16/W21 | `EP-02-S05` | Có asset/trust boundary/risk→mitigation→test traceability cho upload/parser, queue, DB, tenant retrieval, prompt injection, output sanitization và log privacy | PLANNED |
| `EP-02-S05` | Thiết kế C4 Context/Container/Deployment và trust boundary | P0 | 5 | Q | Y | W02 | `EP-01-S01` | Sơ đồ phản ánh React–FastAPI–worker–MongoDB–storage–local AI; ranh giới đồng bộ/bất đồng bộ rõ | IN PROGRESS |
| `EP-02-S06` | Viết API contract v1 và error format chung | P0 | 8 | Q | Y | W02–W03 | `EP-02-S02/05` | Contract bao phủ auth, report/source, upload, job/run, chunks, rubric, result/review; có lỗi và pagination | PLANNED |
| `EP-02-S07` | Thiết kế wireframe/navigation cho các luồng P0 | P0 | 5 | Y | Q | W02 | `EP-01-S01` | Bao phủ upload, progress, similarity evidence, rubric assessment và Accept/Edit/Reject; có loading/empty/error | PLANNED |
| `EP-02-S08` | Audit log và data lifecycle nền tảng | P0 | 5 | Q | Y | W03, W15 | `EP-02-S02/03`, `EP-01-S02` | Sự kiện quyền/upload/run/review/publish có actor/time/before-after; retention/delete có authorization | PLANNED |

## 4. Epic EP-03 — Tiếp nhận, bóc tách và lập chỉ mục tài liệu

| ID | User story/outcome | Pri. | SP | Owner | Review | Tuần | Dependency | Acceptance criteria/DoD | Status |
|---|---|---:|---:|---|---|---|---|---|---|
| `EP-03-S01` | Là sinh viên/giảng viên, tôi upload và theo dõi phiên bản báo cáo/tài liệu nguồn an toàn | P0 | 5 | Q | Y | W03 | `EP-02-S02/03/06` | PDF/DOCX hợp lệ tạo version/hash/status; MIME/size/path/duplicate và quyền được test | PLANNED |
| `EP-03-S02` | Bóc tách PDF/DOCX thành cấu trúc chuẩn bằng Docling/GROBID | P0 | 8 | Q | Y | W04 | `EP-03-S01/06`, fixture | Section/paragraph/table/citation/reference/page được lưu khi hỗ trợ; parse failure không sinh dữ liệu giả | PLANNED |
| `EP-03-S03` | Làm sạch và structure-aware chunking giữ provenance | P0 | 8 | Y | Q | W04 | `EP-03-S02` | Chunk có document/version/section/order/page/span/language; raw/normalized text truy xuất được | PLANNED |
| `EP-03-S04` | Lập lexical/vector index có version và có thể rebuild | P0 | 8 | Q | Y | W05–W06 | `EP-03-S03`, `EP-02-S02` | Index idempotent/resumable; model/config/index version lưu; smoke recall/latency/RAM có artifact | PLANNED |
| `EP-03-S05` | Hỗ trợ PDF scan bằng OCR | P2 | 8 | Y | Q | Sau W16 | `EP-03-S02–04`, `G-07` | OCR confidence/page mapping được lưu; benchmark riêng; không làm giảm parser text | ICEBOX |
| `EP-03-S06` | Xử lý tác vụ dài qua queue/worker có retry và idempotency | P0 | 8 | Q | Y | W03–W04 | `EP-03-S01` | State queued/processing/failed/review-ready/completed; restart không mất checkpoint; retry hữu hạn | PLANNED |
| `EP-03-S07` | Ánh xạ quote/citation/reference marker vào span/chunk có provenance | P0 | 5 | Y | Q | W04, W08 | `EP-03-S02/03` | Marker/entry và ngữ cảnh quote/citation giữ raw/confidence/page/span/chunk; mở đúng vị trí; parse failure là unknown | PLANNED |
| `EP-03-S08` | Xây golden fixture và benchmark parser/chunking | P0 | 5 | Y | Q | W04 | `EP-03-S02/03` | Corpus khóa trước; expected structure/page mapping; báo coverage, lỗi và thời gian xử lý | PLANNED |

## 5. Epic EP-04 — Hybrid Retrieval và Similarity Analysis

| ID | User story/outcome | Pri. | SP | Owner | Review | Tuần | Dependency | Acceptance criteria/DoD | Status |
|---|---|---:|---:|---|---|---|---|---|---|
| `EP-04-S01` | Tạo similarity seed dataset và annotation guideline | P0 | 5 | Y | Q | W02–W06 | `EP-01-S02` | Có verbatim/paraphrase/summary/none, provenance, negative khó và split theo source/group chống leakage | PLANNED |
| `EP-04-S02` | BM25 lexical retrieval baseline | P0 | 5 | Q | Y | W06 | `EP-03-S04`, `EP-04-S01` | Trả Top-K passage/source/score/location; có Recall@K và latency trên protocol khóa | PLANNED |
| `EP-04-S03` | Dense vector retrieval baseline | P0 | 5 | Q | Y | W06 | `EP-03-S04`, `EP-04-S01` | Cùng corpus/split với BM25; model/normalization versioned; Recall/MRR/nDCG/latency/RAM được báo | PLANNED |
| `EP-04-S04` | RRF và Cross-Encoder/Semantic reranking cho Hybrid Retrieval | P0 | 8 | Q | Y | W07 | `EP-04-S02/03` | Fusion/reranker config versioned; duplicate/batch/timeout/fallback test; báo quality–latency–RAM | PLANNED |
| `EP-04-S05` | Provider boundary/fallback cho nguồn ngoài được duyệt | P1 | 5 | Q | Y | — | `EP-01-S03` | Canonical story lịch sử; core dùng kho tài liệu nguồn nội bộ; chỉ tái mở bằng change request có fail-closed, quota/privacy/provenance | OUT OF SCOPE |
| `EP-04-S06` | Approved web adapter cho candidate-source path | P1 | 8 | Q | Y | — | `EP-04-S05`, provider approval | Canonical story lịch sử; chỉ tái mở khi phạm vi và quyền provider/target site được duyệt, có quota/SSRF test và kill switch | OUT OF SCOPE |
| `EP-04-S07` | Similarity Report và side-by-side evidence viewer | P0 | 8 | Y | Q | W08, W15 | `EP-04-S09–11`, `EP-02-S07` | Mở đúng page/chunk/source; hiển thị score/label/access state; lecturer sửa/duyệt có audit | PLANNED |
| `EP-04-S08` | Phát hiện tương đồng xuyên Việt–Anh | P2 | 8 | Y | Q | Sau W18 | `EP-04-S04/09`, `EXT:bilingual labeled set` | Có labeled bilingual subset và kết quả báo riêng theo ngôn ngữ | ICEBOX |
| `EP-04-S09` | Phân loại verbatim/paraphrase/summary/no-significant-similarity | P0 | 8 | Y | Q | W08 | `EP-04-S04`, labeled data | Nhãn/confidence/calibration lưu; F1 từng lớp và confusion matrix; trường hợp bất định chuyển review | PLANNED |
| `EP-04-S10` | Xử lý quote/citation hợp lệ và span alignment | P0 | 5 | Y | Q | W08 | `EP-03-S07`, `EP-04-S09` | Match span truy vết hai tài liệu; quote/citation là tín hiệu ngữ cảnh, không tự kết luận đạo văn | PLANNED |
| `EP-04-S11` | Tổng hợp unique coverage từ passage lên document | P0 | 5 | Q | Y | W08 | `EP-04-S09/10` | Vùng overlap không tính hai lần; công thức/version/threshold rõ; similarity không được gọi là plagiarism rate | PLANNED |

## 6. Epic EP-05 — Rubric, Evidence Retrieval và Grounded Assessment

| ID | User story/outcome | Pri. | SP | Owner | Review | Tuần | Dependency | Acceptance criteria/DoD | Status |
|---|---|---:|---:|---|---|---|---|---|---|
| `EP-05-S01` | Là giảng viên, tôi tạo, clone, version và publish rubric chuẩn hóa | P0 | 8 | Y | Q | W02, W09 | `EP-01-S06`, `EP-02-S02/03/06` | Criterion/checklist/evidence requirement/weight/level/rule validate; rubric đã dùng bất biến; thay đổi có audit | PLANNED |
| `EP-05-S02` | Criterion query và LOCAL Evidence Retrieval | P0 | 8 | Y | Q | W09–W10 | `EP-03-S04`, `EP-05-S09` | Query/filter/top-k versioned; evidence đúng report/run; không tìm đủ trả insufficient thay vì bịa | PLANNED |
| `EP-05-S03` | Structured LOCAL evaluation và verification MET/UNMET/CANNOT_ASSESS | P0 | 8 | Y | Q | W10 | `EP-05-S02`, `G-03` | Output có checklist/evidence IDs/confidence/issues; structured schema bắt buộc; no-evidence không bịa | PLANNED |
| `EP-05-S04` | Evidence validation và lecturer Accept/Edit/Reject | P0 | 8 | Y | Q | W10, W13, W15 | `EP-05-S03`, `EP-02-S03/08` | Evidence giả/cross-report bị reject; lưu AI gốc/before-after/actor/time/reason; worker không tự publish | PLANNED |
| `EP-05-S05` | Pilot LOCAL assessment trên report–rubric có ground truth | P0 | 5 | Y | Q | W10, lặp W19 | `EP-05-S03/04`, lecturer availability | Chạy cùng report/rubric/split; đo evidence correctness, label metric, latency và phân tích lỗi | PLANNED |
| `EP-05-S06` | Claim/entity/relation extraction và Evidence Graph có provenance | P0 | 8 | Y | Q | W11 | `EP-03-S03`, `EP-05-S04` | Node/edge có type/confidence/source chunk/model/config; duplicate/invalid/cross-report relation được xử lý | PLANNED |
| `EP-05-S07` | GRAPH Evidence Retrieval theo hướng PPR/multi-hop và Retrieval Router | P0 | 8 | Y | Q | W12 | `EP-05-S06` | Seed/edge/filter/depth/config versioned; route LOCAL/GRAPH giải thích được; có graph test cases và latency | PLANNED |
| `EP-05-S08` | Evidence-grounded rationale và deterministic scoring | P0 | 8 | Y | Q | W13 | `EP-05-S03/04/07` | Rationale chỉ dẫn evidence hợp lệ; score do decision rules; CANNOT_ASSESS chuyển review thủ công; consistency test đạt | PLANNED |
| `EP-05-S09` | Rubric Compiler chuyển rubric thành checklist LOCAL/GRAPH | P0 | 8 | Y | Q | W09 | `EP-05-S01` | Compiler deterministic; output schema/version rõ; lỗi rubric chỉ đúng field; test fixture bao phủ rule | PLANNED |

## 7. Epic EP-06 — Writing/logic và cảnh báo hỗ trợ

Các item trong Epic này không được dùng độc lập để kết luận gian lận và không
được chen vào đường găng Evidence Graph/Assessment.

| ID | User story/outcome | Pri. | SP | Owner | Review | Tuần | Dependency | Acceptance criteria/DoD | Status |
|---|---|---:|---:|---|---|---|---|---|---|
| `EP-06-S01` | Cảnh báo chất lượng diễn đạt/văn phong có vị trí | P1 | 5 | Y | Q | Sau W13 | `EP-03-S04`, core gates | Mỗi finding có type/severity/page/chunk/explanation; lecturer review; báo precision sample và limitation | ICEBOX |
| `EP-06-S02` | Phát hiện bất nhất mục tiêu–phương pháp–kết quả–kết luận có evidence | P1 | 8 | Y | Q | Sau W13 | `EP-05-S06–08` | Finding trỏ evidence; thiếu căn cứ trả needs-verification; có test contradiction/missing support | ICEBOX |
| `EP-06-S03` | Cảnh báo style anomaly/AI-writing ở mức hỗ trợ | P2 | 5 | Y | Q | W14 nếu core đạt | Dataset/ethics/gate core | Không có “% AI”; có vị trí/feature/disclaimer/bias limitation; không ảnh hưởng điểm tự động | ICEBOX |

## 8. Epic EP-07 — Kiểm chứng trích dẫn/tài liệu tham khảo (ngoài phạm vi đã chốt)

| ID | User story/outcome | Pri. | SP | Owner | Review | Tuần | Dependency | Acceptance criteria/DoD | Status |
|---|---|---:|---:|---|---|---|---|---|---|
| `EP-07-S01` | Trích xuất citation/reference và candidate link phục vụ reference checker nâng cao | P1 | 5 | Y | Q | — | `EP-03-S02/03/07`, scope change | Canonical story lịch sử; khác `EP-03-S07` ở chỗ chuẩn bị dữ liệu cho kiểm chứng metadata/consistency ngoài core parsing | OUT OF SCOPE |
| `EP-07-S02` | Kiểm chứng DOI/metadata/URL theo trạng thái verified/warning/unknown | P1 | 5 | Y | Q | — | `EP-07-S01`, scope change | API timeout/not-found tách khỏi tài liệu giả; field comparison có provenance/cache/retry | OUT OF SCOPE |
| `EP-07-S03` | Phát hiện/đánh giá missing, unused và mismatch citation/reference | P1 | 5 | Y | Q | — | `EP-07-S01/02`, scope change | Finding có evidence/review; báo Precision/Recall/F1, failure cases và limitation | OUT OF SCOPE |

## 9. Epic EP-08 — Sinh và duyệt câu hỏi grounded

| ID | User story/outcome | Pri. | SP | Owner | Review | Tuần | Dependency | Acceptance criteria/DoD | Status |
|---|---|---:|---:|---|---|---|---|---|---|
| `EP-08-S01` | Sinh câu hỏi có mục tiêu từ issue, similarity, evidence và rubric | P0 | 8 | Y | Q | W14 | `EP-04-S07/09`, `EP-05-S08` | Mỗi câu có type/question/reference answer/evidence/purpose/difficulty; evidence giả bị reject | PLANNED |
| `EP-08-S02` | Lecturer review, chỉnh sửa, loại bỏ và đánh giá câu hỏi | P0 | 5 | Y | Q | W14, W20 | `EP-08-S01`, `EP-02-S03/08` | Chỉ câu approved được dùng; audit before/after; rating relevance/grounding/answerability/usefulness xuất được | PLANNED |

## 10. Epic EP-09 — Workflow, review workspace, feedback và export

| ID | User story/outcome | Pri. | SP | Owner | Review | Tuần | Dependency | Acceptance criteria/DoD | Status |
|---|---|---:|---:|---|---|---|---|---|---|
| `EP-09-S01` | Job workflow có progress, retry, resume và partial result | P0 | 8 | Q | Y | W03–W05, W15–W16 | `EP-02-S02/06`, `EP-03-S01/06` | HTTP không block; state/checkpoint/idempotency test; worker restart không mất kết quả đã commit | PLANNED |
| `EP-09-S02` | Unified lecturer review workspace/dashboard cho similarity/assessment/question | P0 | 8 | Y | Q | W15 | `EP-04-S07`, `EP-05-S04/08`, `EP-08-S02` | Evidence mở đúng; filter/status/UX state; Accept/Edit/Reject nhất quán; unpublished result không lộ | PLANNED |
| `EP-09-S03` | Final Report/Export có version và disclaimer | P0 | 5 | Q | Y | W15 | `EP-09-S02/07` | HTML/PDF tối thiểu có evidence/review status/version; chỉ Lecturer publish; similarity ≠ plagiarism | PLANNED |
| `EP-09-S04` | Observability, correlation ID và run/resource telemetry | P0 | 5 | Q | Y | W03–W21 | `EP-09-S01` | `request_id→job_id→run_id` xuyên API/worker/model/index/graph/evidence; structured log redacted PII/secret; stage latency, success/failure và resource truy vết được | PLANNED |
| `EP-09-S05` | Cohort/class analytics dashboard | P2 | 5 | Y | Q | Sau W21 | `G-09`, `EP-09-S06` | Chỉ aggregate đúng quyền; metric định nghĩa rõ; không suy diễn gian lận | ICEBOX |
| `EP-09-S06` | Data lifecycle, retention, archive/delete và derived-data cleanup | P0 | 5 | Q | Y | W02 design, W15/W21 | `EP-01-S02`, `EP-02-S02/03/08` | Enforce purpose/retention/approver; archive/delete đúng quyền và idempotent cascade file/chunk/vector/graph/result/cache; backup expiry, tombstone/audit và cross-tenant tests đạt | PLANNED |
| `EP-09-S07` | Feedback Log bất biến cho mọi điều chỉnh | P0 | 5 | Q | Y | W15, W20 | `EP-09-S02`, `EP-02-S08` | Lưu run/model/original/final/actor/time/reason; export được cho error analysis đúng quyền | PLANNED |

## 11. Epic EP-10 — Dataset, thực nghiệm và reproducibility

| ID | Research outcome | Pri. | SP | Owner | Review | Tuần | Dependency | Acceptance criteria/DoD | Status |
|---|---|---:|---:|---|---|---|---|---|---|
| `EP-10-S01` | Khóa benchmark, data card, annotation guideline và split | P0 | 8 | Y | Q | W02–W17 | `EP-01-S02/06`, `EP-04-S01`, `EP-05-S05` | Manifest/checksum/license/provenance; train/validation/test chống leakage; QA/inter-rater khi có | PLANNED |
| `EP-10-S02` | Thực nghiệm RQ1: BM25, Dense, RRF, reranker và full pipeline | P0 | 8 | Q | Y | W18 | `EP-04-S01–04`, `EP-04-S09–11`, `EP-10-S01/06` | Recall@K/MRR/nDCG, per-class P/R/F1, latency/RAM, ablation và error analysis cùng protocol | PLANNED |
| `EP-10-S03` | Thực nghiệm RQ2: no retrieval, LOCAL và selective LOCAL/GRAPH | P0 | 8 | Y | Q | W19 | `EP-05-S01–09`, `EP-10-S01/06` | Evidence Recall/Precision, three-state metric, score agreement, rationale support, latency và error analysis | PLANNED |
| `EP-10-S04` | Đánh giá hướng bổ sung và tính hữu ích hệ thống | P0 | 5 | Y | Q | W20 | `EP-08-S01/02`, `EP-09-S02/07`, `EP-10-S01/06` | Đo relevance/evidence-grounding/answerability/usefulness, accept/edit/reject và usability; cảnh báo hỗ trợ chỉ đánh giá nếu đã qua gate; báo sample/rater/uncertainty/limitation | PLANNED |
| `EP-10-S05` | Artifact/checksum và script tái tạo bảng/biểu | P0 | 5 | Q | Y | W17–W22 | `EP-10-S02–04/06` | Truy từ bảng luận văn về run; clean rerun trong tolerance; dữ liệu lưu đúng quyền | PLANNED |
| `EP-10-S06` | Experiment runner, metric implementation và run manifest | P0 | 8 | Q | Y | W05–W17 | `EP-10-S01` | Mỗi run có commit/data/model/config/seed/hardware; metric unit test; raw result bất biến | PLANNED |

## 12. Epic EP-11 — Quality, security, performance và release engineering

| ID | Outcome | Pri. | SP | Owner | Review | Tuần | Dependency | Acceptance criteria/DoD | Status |
|---|---|---:|---:|---|---|---|---|---|---|
| `EP-11-S01` | Test pyramid và CI quality/security gates | P0 | 8 | Q | Y | W03 initial; W16/W21 gates | `EP-02-S01/04` | Unit/integration/E2E; SAST/secret/dependency scan; Critical/High được sửa hoặc waiver có owner/expiry | PLANNED |
| `EP-11-S02` | Malicious upload, parser isolation và prompt-injection defense | P0 | 8 | Q | Y | W04, W10, W16 | `EP-02-S04`, `EP-03`, `EP-05` | MIME/path/zip/resource limit; tenant/report isolation; untrusted text không điều khiển tool; output sanitize/schema validate | PLANNED |
| `EP-11-S03` | Performance/resilience/data-safety và backup-restore benchmark | P0 | 8 | Q | Y | W16, W21 | `EP-11-S05` | p50/p95, throughput, RAM/VRAM; timeout/restart/outage; restore drill và bottleneck evidence | PLANNED |
| `EP-11-S04` | Release Candidate và Release 1.0 có thể cài lại | P0 | 8 | Q | Y | W16, W21, W23–W24 | `EP-11-S01–03/05` | Clean install/smoke; migration/rollback; release notes/known issues/checksum; không đóng gói dữ liệu nhạy cảm | PLANNED |
| `EP-11-S05` | E2E integration, retry/cache/failure và feature freeze | P0 | 8 | Q | Y | W16 | `G-04`, `G-06`, `EP-09-S01–03`, `EP-09-S07` | Upload→parse→similarity/assessment→review→export chạy; failure/recovery test; không mở feature mới | PLANNED |

## 13. Epic EP-12 — Luận văn, tài liệu và bàn giao

| ID | Outcome | Pri. | SP | Owner | Review | Tuần | Dependency | Acceptance criteria/DoD | Status |
|---|---|---:|---:|---|---|---|---|---|---|
| `EP-12-S01` | Viết luận văn song song với artifact và evidence matrix | P0 | 8 | Y | Q | W01–W22 | Tất cả epic | Claim định lượng dẫn run artifact; UML/API/code/bảng thống nhất; limitation/ethics/kết quả âm được nêu | IN PROGRESS |
| `EP-12-S02` | Technical/user/API/data/model docs, slide, video và demo package | P0 | 8 | Q | Y | W16–W23 | `G-09`, `EP-11-S04` | Người mới dựng/chạy demo được; requirement/runtime/limitation rõ; slide/video khớp release | PLANNED |
| `EP-12-S03` | Gói nộp, backup, checksum, rehearsal và defense fallback | P0 | 5 | Y | Q | W24 + 23/01 | `EP-11-S04`, `EP-12-S01/02` | Checklist Khoa; artifact khôi phục được; rehearsal/offline fallback; nộp đúng 23/01/2027 và lưu submission receipt truy vết được | PLANNED |

---

## 14. Stretch/conditional backlog và scope cut line

| Thứ tự | Item | Điều kiện kéo vào | Mặc định |
|---:|---|---|---|
| 1 | `EP-01-S03`, `EP-04-S05/06` — nguồn ngoài/provider | Change request được Q/Y/GVHD duyệt, đủ quyền/privacy/quota và không làm trễ core | `OUT OF SCOPE`; dùng kho nguồn nội bộ |
| 2 | `EP-07-S01–03` — reference checker DOI/metadata/consistency | Change request được duyệt; không nhầm với citation/span mapping core `EP-03-S07` | `OUT OF SCOPE` |
| 3 | `EP-06-S01/02` — writing/document logic | Assessment Engine và benchmark core ổn | `ICEBOX` |
| 4 | `EP-06-S03` — style/AI-writing warning | Có dataset/ethics/disclaimer và không ảnh hưởng W14 | `ICEBOX` |
| 5 | `EP-03-S05` — OCR | Corpus scan đủ lớn và parser core đạt | `ICEBOX` |
| 6 | `EP-04-S08` — cross-language | Có labeled bilingual subset sau RQ1 | `ICEBOX` |
| 7 | `EP-09-S05` — cohort dashboard | Release core, privacy và buffer đều đạt | `ICEBOX` |

Khi trễ, cắt từ dưới lên trong bảng. Không cắt parser/provenance, Hybrid
Similarity, LOCAL/GRAPH Assessment, lecturer review, benchmark hoặc
reproducibility chỉ để giữ extension.

## 15. Critical path và nhánh song song

```text
Scope/data baseline
→ Architecture + MongoDB + API
→ Upload + queue
→ Parse + chunk + provenance
→ Lexical/vector index
→ BM25 + Dense → RRF → Reranker
→ Similarity classifier/report
→ Rubric Compiler → LOCAL Evidence Retrieval
→ Evidence Graph → Graph Retrieval
→ Verification/rationale/deterministic scoring
→ Lecturer review/feedback/export
→ Dataset freeze → RQ1/RQ2 experiments
→ RC2 → Thesis/Release → Submission
```

Các nhánh được phép chạy song song:

- Wireframe dùng JSON fixture trước khi API hoàn chỉnh.
- Similarity labels và rubric/checklist được xây từ W02, không chờ pipeline.
- Experiment runner/metric được viết cùng baseline, không chờ W17.
- Luận văn cập nhật theo increment từ W01.
- Question UI dùng assessment/similarity fixture trước W14.

## 16. Tổng hợp tải Product Backlog

Tải được tính theo owner của outcome, không tính effort review. Bảng này phải
được cập nhật bằng script/kiểm tra khi thay owner hoặc SP.

| Phạm vi | Quý (SP) | Yến (SP) | Ghi chú |
|---|---:|---:|---|
| Phạm vi đã lên lịch (`P0` + `P1`, không gồm blocked/icebox/out-of-scope) | 199 | 186 | Product SP là độ lớn outcome; WBS mới là tải thực thi theo tuần |
| Ngoài phạm vi đã chốt (`OUT OF SCOPE`) | 18 | 15 | Giữ canonical ID cho provider/reference checker; chỉ mở lại bằng change request |
| Icebox (`P1` + `P2`) | 0 | 39 | Writing/logic, OCR, cross-language, style và cohort dashboard; không tính vào cam kết 24 tuần |

## 17. Cấu hình issue board đề xuất

### Cột

1. Backlog
2. Ready
3. In Progress
4. Review
5. Test/Verify
6. Done

### Field

- `Backlog ID`, `Epic`, `Priority`, `Story Point`.
- `Owner`, `Reviewer`, `Target Week`, `Dependency`, `Status`.
- `Artifact/PR`, `Experiment Run`, `Actual`, `Blocker`.

### Label

- Type: `feature`, `research`, `design`, `test`, `docs`, `chore`, `bug`.
- Component: `frontend`, `backend`, `worker`, `data`, `ml-ir`, `graph`,
  `database`, `devops`.
- Priority: `P0`, `P1`, `P2`.
- Risk: `security`, `privacy`, `research-validity`, `performance`, `data-rights`.

Tên issue:

```text
[BACKLOG-ID] Động từ + kết quả kiểm chứng được
```

## 18. Change Log và phê duyệt

| Phiên bản | Ngày | Thay đổi |
|---|---|---|
| 1.0 | 21/08/2026 | Tách Product Backlog khỏi WBS; phân công Q/Y; lấy roadmap Excel và phạm vi 2 hướng chính + 1 bổ sung làm chuẩn; giữ canonical ID cũ nhưng đánh dấu provider/reference checker `OUT OF SCOPE`; chuyển extension khỏi critical path |

| Vai trò | Họ tên | Quyết định | Ngày |
|---|---|---|---|
| Nhóm trưởng | Nguyễn Trần Ngọc Quý | Chờ review/ký |  |
| Thành viên | Võ Thị Kim Yến | Chờ review/ký |  |
| GVHD | Vũ Đình Hồng | Chờ xác nhận baseline |  |
