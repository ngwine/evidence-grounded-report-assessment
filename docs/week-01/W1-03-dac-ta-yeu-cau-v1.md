# ĐẶC TẢ YÊU CẦU — BASELINE PHẠM VI V2.0

## Hệ thống hỗ trợ kiểm tra đạo văn và đánh giá báo cáo sinh viên dựa trên bằng chứng

## 1. Thông tin tài liệu

| Thuộc tính | Giá trị |
|---|---|
| Mã tài liệu | `SRS-KLTN-01` |
| Phiên bản | `2.0` |
| Ngày lập | 13/08/2026 |
| Ngày đồng bộ phạm vi | 17/09/2026 |
| Trạng thái | **Baseline đã được reviewer Y duyệt và merge qua PR #8; thay đổi mới phải có change log** |
| Owner | Nguyễn Trần Ngọc Quý (Q) |
| Reviewer | Võ Thị Kim Yến (Y) |
| WBS | `W1.1` |
| Phạm vi chuẩn | Hai hướng chính: Similarity và Evidence-grounded Assessment; Targeted Questions là hướng `CONDITIONAL` |

Tài liệu này thay thế nội dung active của bản `1.2-review-candidate`. Các ID cũ
không còn thuộc phạm vi được giữ tại mục 13 để truy vết, không được hiểu là chức
năng sẽ triển khai.

### 1.1. Thứ tự nguồn chuẩn

Khi tài liệu mâu thuẫn, áp dụng thứ tự:

1. quyết định phạm vi có Q/Y/GVHD xác nhận;
2. tài liệu này và bộ Use Case v2.0;
3. Product Backlog/WBS hiện hành;
4. C4, ADR, Data Dictionary và API Contract đã review;
5. mô tả hoặc tài liệu trước rebaseline chỉ dùng như lịch sử.

### 1.2. Thuật ngữ

- **Report:** báo cáo sinh viên cần phân tích.
- **Source document:** tài liệu đối chứng đã được nạp vào corpus và được duyệt
  quyền sử dụng; core không tự tìm/fetch nguồn trên Internet.
- **Evidence:** đoạn nội dung có locator và provenance resolve được về đúng file
  và version.
- **Claim–evidence relation:** `SUPPORTED`, `CONTRADICTED` hoặc `INSUFFICIENT`.
- **Checklist outcome:** `MET`, `UNMET` hoặc `CANNOT_ASSESS`, chỉ được xác định
  sau khi áp decision rule của rubric.
- **Proposal:** kết quả AI chưa được giảng viên duyệt; không phải điểm/kết luận
  chính thức.
- **Publication:** snapshot đã được giảng viên review và chủ động công bố.

## 2. Bối cảnh và nguyên tắc

Hệ thống hỗ trợ giảng viên tìm nội dung tương đồng và đánh giá báo cáo dài dựa
trên bằng chứng. Hệ thống không tự kết luận đạo văn, không tự công bố điểm và
không xem việc thiếu evidence là bằng chứng nội dung sai.

Các nguyên tắc bắt buộc:

1. **Local-first:** báo cáo và model chạy local theo baseline; outbound không
   thuộc core.
2. **Evidence-first:** mọi nhận xét/nhãn phải dẫn được về evidence hợp lệ.
3. **Human-in-the-loop:** giảng viên Accept/Edit/Reject trước khi publish.
4. **Deny-by-default:** dữ liệu chưa có quyền/purpose/retention/approver không
   được index hoặc chạy experiment.
5. **Reproducible:** run khóa data, model, prompt/config, code commit, seed và
   hardware.

## 3. Câu hỏi nghiên cứu canonical

| ID | Câu hỏi nghiên cứu | Trạng thái |
|---|---|---|
| `RQ1` | BM25, Dense, Hybrid + RRF và reranker ảnh hưởng thế nào đến source/evidence retrieval và nhận diện nội dung tương đồng? | CORE |
| `RQ2` | Rubric compilation và evidence-grounded assessment có cải thiện evidence retrieval, phân loại checklist, rationale grounding và score agreement so với chấm trực tiếp không retrieval hay không? | CORE |
| `RQ3` | Câu hỏi sinh từ issue + evidence có liên quan, grounded, answerable và hữu ích với giảng viên hay không? | CONDITIONAL; chỉ mở sau gate core |

Kết quả âm vẫn là kết quả hợp lệ nếu protocol được khóa trước và báo cáo trung
thực. Không dùng acceptance criteria để buộc phương pháp đề xuất phải thắng.

## 4. Mục tiêu

| ID | Mục tiêu | Dấu hiệu hoàn thành |
|---|---|---|
| `OBJ-01` | Xử lý PDF/DOCX Việt/Anh và giữ cấu trúc/vị trí | Parser/chunker có golden benchmark và provenance resolve được |
| `OBJ-02` | Tìm nguồn/đoạn tương đồng trong corpus được duyệt | Có BM25, Dense, Hybrid/RRF, reranker baseline và metric |
| `OBJ-03` | Đánh giá rubric dựa trên evidence | Checklist có evidence, three-state outcome, rationale và deterministic scoring |
| `OBJ-04` | Giữ quyền quyết định của giảng viên | Có review history, publication riêng và Feedback Log |
| `OBJ-05` | Thực nghiệm tái lập | Một lệnh tạo run manifest, prediction, metric và bảng kết quả |
| `OBJ-06` | Sinh câu hỏi có mục tiêu | Chỉ thực hiện nếu gate/capacity cho phép và có human evaluation |

## 5. Phạm vi

### 5.1. Core bắt buộc

1. Quản lý session, workspace, role và quyền tài nguyên tối thiểu.
2. Upload và version report/source PDF hoặc DOCX an toàn.
3. Parsing, normalization và structure-aware chunking có provenance.
4. Lexical/dense index có version và rebuild được.
5. Pipeline Similarity: BM25 + Dense → RRF → optional reranker → similarity
   type → Similarity Report.
6. Rubric template/compiler, checklist `LOCAL/GRAPH`, evidence retrieval,
   verification, rationale và deterministic scoring.
7. Lecturer review, publication, Feedback Log, audit và data lifecycle.
8. Dataset manifest, protocol, offline runner, metric và error analysis.

### 5.2. Conditional

- Targeted Questions chỉ được triển khai khi `G-06` đúng forecast, dữ liệu có
  evidence/issue hợp lệ và capacity không ảnh hưởng hai pipeline core.
- GRAPH chỉ được giữ trong cấu hình chính nếu pilot multi-hop cho thấy lợi ích;
  LOCAL là fallback bắt buộc.
- PDF export, parser nâng cao hoặc model lớn chỉ được kéo vào sau benchmark.

### 5.3. Ngoài phạm vi hoặc Icebox

| Hạng mục | Trạng thái | Lý do |
|---|---|---|
| Search Provider/fetch/crawl nguồn web tự động | OUT OF SCOPE | Core dùng corpus nội bộ/công khai được nạp hợp pháp |
| DOI/Crossref/metadata reference checker nâng cao | OUT OF SCOPE | Không thuộc hai hướng nghiên cứu chính |
| Citation/reference marker-to-span | CORE | Là provenance parsing, không phải DOI checker |
| Standalone grammar/style/AI-writing detector | ICEBOX | Chỉ là cảnh báo phụ, cần dataset/ethics riêng |
| OCR, công thức và vision/multimodal đầy đủ | ICEBOX | Chỉ mở nếu corpus chứng minh nhu cầu và còn capacity |
| Tự kết luận đạo văn hoặc tự publish điểm | PROHIBITED | Trái human-in-the-loop và ranh giới sản phẩm |
| Sinh viên trả lời vấn đáp trực tuyến | OUT OF SCOPE | RQ3 chỉ sinh–review–export câu hỏi |

## 6. Actor và quyền chính

| Actor | Quyền chính | Ranh giới |
|---|---|---|
| Student | Upload/xem report của mình; xem publication được phép | Không xem proposal/review nội bộ hoặc report người khác |
| Lecturer | Quản lý source/rubric; chạy phân tích; review/publish | Chỉ trong workspace/scope được cấp |
| Admin | Quản lý tài khoản, policy và vận hành | Không mặc định được review/publish học thuật |
| Experiment Operator | Chạy config đã duyệt và đọc artifact nghiên cứu đúng quyền | Không tự thay split/test hoặc quyền dữ liệu |
| Local AI runtime | Embedding/rerank/structured proposal | Không có quyền DB/tool/publish độc lập |

## 7. Yêu cầu chức năng active

### 7.1. Identity và scope

| ID | Yêu cầu | Pri. | Kiểm chứng |
|---|---|---:|---|
| `FR-AUTH-01` | Hệ thống xác thực session, CSRF và rotate/revoke session ID | MUST | T |
| `FR-AUTH-02` | Mọi read/write/retrieval lọc workspace, owner, role và purpose trước khi lấy content | MUST | T/A |
| `FR-AUTH-03` | Cross-scope identifier không làm lộ resource tồn tại | MUST | T |

### 7.2. Report, source và document processing

| ID | Yêu cầu | Pri. | Kiểm chứng |
|---|---|---:|---|
| `FR-RPT-01` | Upload PDF/DOCX kiểm tra size, magic/MIME, path và checksum | MUST | T |
| `FR-RPT-02` | Mỗi upload hợp lệ tạo immutable file/document version | MUST | T |
| `FR-RPT-03` | Parser tạo ordered elements gồm raw text, normalized text, structure và locator | MUST | T/A |
| `FR-RPT-04` | Chunker tạo stable chunk key, bounded chunk, source spans và raw↔normalized mapping | MUST | T/A |
| `FR-RPT-05` | File→version→element→chunk provenance phải resolve được và deterministic | MUST | T |
| `FR-RPT-06` | Source/dataset chưa `APPROVED` được quarantine và không index/run | MUST | T |
| `FR-RPT-07` | Parse/index job có progress, retry hữu hạn, idempotency và safe failure | MUST | T |

### 7.3. Similarity pipeline

| ID | Yêu cầu | Pri. | Kiểm chứng |
|---|---|---:|---|
| `FR-SIM-01` | BM25 trả Top-K source passages kèm score và locator | MUST | T/A |
| `FR-SIM-02` | Dense retrieval dùng cùng corpus/filter/candidate schema với BM25 | MUST | T/A |
| `FR-SIM-03` | RRF hợp nhất ranking; config và tie-break deterministic | MUST | T/A |
| `FR-SIM-04` | Reranker có batch/timeout/fallback và model version | MUST | T/A |
| `FR-SIM-05` | Candidate được phân loại `verbatim/paraphrase/summary/none` khi dataset hỗ trợ | MUST | A |
| `FR-SIM-06` | Similarity Report hiển thị đoạn nghi vấn, source, locator, loại và score | MUST | D/T |
| `FR-SIM-07` | UI/report luôn nêu similarity không đồng nghĩa plagiarism | MUST | I/D |

### 7.4. Evidence-grounded assessment

| ID | Yêu cầu | Pri. | Kiểm chứng |
|---|---|---:|---|
| `FR-RUB-01` | Rubric version chứa criterion, atomic checklist, evidence need, weight, level và decision rule | MUST | T/I |
| `FR-RUB-02` | Published rubric version bất biến; thay đổi tạo version mới | MUST | T |
| `FR-RUB-03` | Rubric compiler phân loại checklist `LOCAL/GRAPH` kèm reason/config | MUST | T/A |
| `FR-RUB-04` | Evidence retrieval chỉ dùng report/source version được run khóa | MUST | T |
| `FR-RUB-05` | Claim–evidence relation chỉ là `SUPPORTED/CONTRADICTED/INSUFFICIENT` | MUST | T/A |
| `FR-RUB-06` | Checklist outcome chỉ là `MET/UNMET/CANNOT_ASSESS` sau decision rule | MUST | T/A |
| `FR-RUB-07` | Rationale chỉ dẫn evidence ID hợp lệ; unsupported citation bị validator chặn | MUST | T/A |
| `FR-RUB-08` | Điểm đề xuất do deterministic rule của rubric tính, không do LLM tự đặt | MUST | T |
| `FR-RUB-09` | Nếu evidence thiếu/mâu thuẫn chưa phân giải, hệ thống abstain và chuyển giảng viên | MUST | T/A |
| `FR-RUB-10` | GRAPH lỗi hoặc không qua gate phải fallback LOCAL/CANNOT_ASSESS an toàn | MUST | T |

### 7.5. Review, publication và feedback

| ID | Yêu cầu | Pri. | Kiểm chứng |
|---|---|---:|---|
| `FR-REV-01` | Lecturer Accept/Edit/Reject proposal kèm reason khi cần | MUST | T/D |
| `FR-REV-02` | Review giữ original/final value, actor, time, evidence và revision | MUST | T/I |
| `FR-REV-03` | Publish là action riêng; chỉ publication đã sanitize được hiển thị | MUST | T |
| `FR-REV-04` | Feedback Log bất biến và xuất được cho error analysis đúng quyền | MUST | T/A |
| `FR-REV-05` | Tombstone chặn read/retrieval/job mới trước physical cleanup | MUST | T |

### 7.6. Experiment và hướng conditional

| ID | Yêu cầu | Pri. | Kiểm chứng |
|---|---|---:|---|
| `FR-EXP-01` | Run manifest lưu commit, dataset/version/split, config, model, seed, hardware và timing | MUST | T/I |
| `FR-EXP-02` | Runner tái tạo raw prediction, metric và bảng từ config khóa | MUST | T/A |
| `FR-EXP-03` | Test split không được dùng chọn model/threshold | MUST | I/A |
| `FR-QST-01` | Nếu enabled, câu hỏi phải liên kết issue/evidence/rubric | CONDITIONAL | T/A |
| `FR-QST-02` | Lecturer review/edit/reject trước khi export câu hỏi | CONDITIONAL | T/D |

## 8. Yêu cầu chất lượng

| ID | Yêu cầu |
|---|---|
| `NFR-SEC-01` | File/nội dung/model output đều untrusted; parser giới hạn CPU/RAM/time/network; output được sanitize/schema validate |
| `NFR-SEC-02` | Secret, stack trace, raw report và PII không xuất hiện trong operational log |
| `NFR-PRV-01` | Dữ liệu chỉ dùng đúng purpose/retention/authority; revoke/tombstone lan tới derived artifact |
| `NFR-REL-01` | Job/rebuild idempotent; retry không nhân đôi authoritative artifact |
| `NFR-PERF-01` | Mỗi benchmark báo p50/p95 latency, throughput, RAM và index size trên hardware đã ghi |
| `NFR-REP-01` | Dataset/checksum/split/config/seed/code/hardware và metric implementation được version hóa |
| `NFR-REP-02` | Raw result bất biến; bảng/biểu sinh từ script, không chép số thủ công |
| `NFR-AI-01` | Structured output fail schema hoặc evidence validation phải retry hữu hạn hoặc abstain |
| `NFR-ETH-01` | Không diễn giải similarity/AI warning thành gian lận; limitation và dữ liệu loại trừ phải được báo cáo |

Ngưỡng chất lượng nghiên cứu được khóa trong protocol trước khi mở test split,
không hard-code vào SRS để hợp thức hóa kết quả.

## 9. Dữ liệu và provenance

Chuỗi bắt buộc:

```text
file → document version → element → chunk → index generation
→ analysis run → evidence → proposal → review → publication
```

Mỗi dataset/report dùng nghiên cứu phải có owner, version, nguồn, checksum,
license hoặc consent, allowed purpose, classification, anonymization,
retention, approver/date và split theo document/source để chống leakage.

## 10. Luồng xử lý chuẩn

```text
Upload
→ Validate/Governance Gate
→ Parse
→ Structure-aware Chunk
→ Index
→ Similarity and/or Assessment Run
→ Evidence Verification
→ Lecturer Review
→ Publication/Feedback Log
```

AI/worker không có transition trực tiếp tới publication.

## 11. Traceability

| RQ | Yêu cầu chính | Use Case | Artifact/metric |
|---|---|---|---|
| `RQ1` | `FR-RPT-03–05`, `FR-SIM-01–07`, `FR-EXP-01–03` | `UC-02`, `UC-04`, `UC-05`, `UC-12` | Recall@K, MRR, nDCG, span/class F1, latency |
| `RQ2` | `FR-RUB-01–10`, `FR-REV-01–04`, `FR-EXP-01–03` | `UC-03`, `UC-04`, `UC-06`, `UC-10`, `UC-12` | Evidence Recall/Precision, three-state macro-F1, grounding, agreement |
| `RQ3` | `FR-QST-01–02` | `UC-08` | Relevance, grounding, answerability, usefulness; chỉ khi enabled |

## 12. Điều kiện chấp nhận baseline `W1.1`

- [x] Chỉ còn `RQ1`, `RQ2` và `RQ3-CONDITIONAL` trong active scope.
- [x] Web provider, DOI checker và style detector không còn ở MUST/P0.
- [x] Citation span core được tách khỏi DOI/reference checker.
- [x] Mermaid/Use Case chính không chứa actor hoặc flow ngoài phạm vi.
- [x] FR ↔ UC ↔ RQ active không có dangling ID.
- [x] Có mapping legacy và change log.
- [ ] Q/Y review và xác nhận qua PR.
- [ ] GVHD xác nhận scope/RQ hoặc ghi change request.

## 13. Migration từ baseline cũ

| ID/nội dung cũ | Xử lý trong v2.0 |
|---|---|
| Legacy `RQ1` Similarity | Giữ thành canonical `RQ1` |
| Legacy `RQ2` Google Search/provider | `RETIRED / OUT OF SCOPE` |
| Legacy `RQ3` Rubric-RAG | Đổi thành canonical `RQ2` |
| Legacy `RQ4` DOI/reference checker | `RETIRED / OUT OF SCOPE` |
| Legacy `RQ5` Questions | Đổi thành canonical `RQ3-CONDITIONAL` |
| Legacy `FR-SIM-02–05` web collection | `RETIRED`; ID không tái sử dụng |
| Legacy `FR-REF-*` DOI/metadata validation | `RETIRED`; citation/span chuyển về document provenance |
| Legacy `FR-WRI-*` standalone style | `ICEBOX`; logic consistency nằm trong `FR-RUB-*` |
| Legacy question assignment/online answer | `RETIRED`; chỉ review/edit/export nếu RQ3 enabled |

## 14. Open decisions

| ID | Câu hỏi | Owner/Approver |
|---|---|---|
| `OQ-01` | Rubric/checklist/annotation guideline v1 và adjudication | Y / Q / GVHD |
| `OQ-02` | Dataset version, license/consent, split và retention | Y / data owner / GVHD |
| `OQ-03` | Parser/embedding/reranker/LLM cấu hình thắng benchmark dev | Q/Y |
| `OQ-04` | GRAPH có qua gate multi-hop hay giữ LOCAL fallback | Q/Y/GVHD |
| `OQ-05` | RQ3 có được kéo vào theo capacity/gate hay không | Q/Y/GVHD |

## 15. Change log và phê duyệt

| Phiên bản | Ngày | Thay đổi |
|---|---|---|
| `1.2-review-candidate` | 13/08/2026 | Baseline cũ gồm RQ1–RQ5, web provider, DOI/reference và style feature |
| `2.0-review-candidate` | 17/09/2026 | Đồng bộ về hai pipeline core + RQ3 conditional; retire web provider/DOI checker; đưa style/AI warning về icebox; cập nhật FR/traceability/provenance |

| Vai trò | Người | Quyết định | Ngày | Evidence |
|---|---|---|---|---|
| Owner | Nguyễn Trần Ngọc Quý | Đề xuất review v2.0 | 17/09/2026 | Branch `docs/w1-1-scope-sync` |
| Reviewer | Võ Thị Kim Yến | Chờ review | — | — |
| GVHD | Vũ Đình Hồng | Chờ xác nhận scope/RQ | — | — |
