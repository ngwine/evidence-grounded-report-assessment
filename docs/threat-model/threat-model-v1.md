# W2.1 — Threat Model và Adversarial Test Plan v1

| Thuộc tính | Giá trị |
|---|---|
| Phiên bản | 0.1 |
| Ngày | 03/09/2026 |
| Trạng thái | REVIEW CANDIDATE — control/test mới ở mức thiết kế |
| WBS | `W2.1`; backlog `EP-02-S04` |
| Owner | Nguyễn Trần Ngọc Quý (Q) |
| Reviewer | Võ Thị Kim Yến (Y) |
| Phạm vi review lại | W04 parser, W10 AI, W16 security/E2E, W21 release |

## 1. Mục đích và giới hạn

Threat model trả lời bốn câu hỏi trước khi khóa DB/API và viết sâu:

1. tài sản nào cần bảo vệ;
2. dữ liệu vượt qua trust boundary nào;
3. kịch bản lạm dụng gây tác động gì;
4. control và test nào chứng minh hệ thống đã xử lý kịch bản đó.

Phạm vi gồm C4/data flow baseline local-first, hai pipeline core, lecturer
review/publish và import dataset/experiment. External Search/Web Provider đang
`DISABLED / OUT OF SCOPE`; rủi ro Internet được giữ dưới dạng dormant risk để
không vô tình mở egress sau này.

Đây là threat model thiết kế, **không phải chứng nhận hệ thống đã an toàn**.
Hiện parser/chunker mới là prototype; API, auth, queue/worker, MongoDB
integration, index, Local AI và các security test chưa được triển khai đầy đủ.

## 2. Phương pháp và quy tắc đánh giá

- Dùng STRIDE cho spoofing, tampering, repudiation, information disclosure,
  denial of service và elevation of privilege.
- Bổ sung privacy/data-rights và research-validity vì dữ liệu sinh viên và kết
  quả thực nghiệm là tài sản của đề tài.
- `Khả năng` và `Tác động`: `L` thấp, `M` trung bình, `H` cao.
- `Rủi ro ban đầu`: `CRITICAL` cho `H/H`; `HIGH` cho `H/M` hoặc `M/H`;
  `MEDIUM` cho `H/L`, `L/H`, `M/M`, `M/L` hoặc `L/M`; `LOW` cho `L/L`.
- Chỉ hạ residual risk sau khi test tương ứng chạy đạt trên implementation.
  Việc viết control trong tài liệu không làm giảm risk.

Đối tượng tấn công gồm người dùng sai quyền hoặc tò mò, file/dataset độc hại,
nội dung prompt-injection nằm trong report/source, process bị cấu hình sai và
lỗi vô ý của thành viên vận hành/thực nghiệm. Không giả định người dùng nội bộ
luôn đáng tin.

## 3. Tài sản cần bảo vệ

| ID | Tài sản | Yêu cầu chính |
|---|---|---|
| `A-01` | Danh tính, session, credential và role | Bí mật; đúng actor/scope; thu hồi được |
| `A-02` | File báo cáo, extracted text, chunk và nguồn nội bộ | Bí mật/riêng tư; toàn vẹn; đúng version; có lifecycle |
| `A-03` | Provenance, checksum, locator và evidence span | Không bị tráo/sửa; resolve về đúng source/version |
| `A-04` | Corpus, lexical/vector/graph index và cache | Không rò tenant; đồng bộ source; xóa/rebuild được |
| `A-05` | Rubric, prompt, model/config và score rule | Có version; không bị sửa ngầm; đúng run |
| `A-06` | Similarity/assessment proposal, feedback và published result | Chính xác theo evidence; chỉ người có quyền publish; audit được |
| `A-07` | Queue job, run state, retry/checkpoint | Không giả mạo/replay/tráo scope; idempotent; khôi phục được |
| `A-08` | Dataset, annotation, split và experiment manifest/result | Đúng quyền; không leakage/poison; tái lập được |
| `A-09` | Log, audit, export và backup | Không rò secret/PII; chống chối bỏ; retention/delete đúng |
| `A-10` | CPU, RAM, disk, model runtime và khả năng demo | Không bị cạn kiệt; timeout/quota; phục hồi hữu hạn |

## 4. Trust boundary được dùng

Nguồn định nghĩa đầy đủ là
[`data-flow.md`](../architecture/data-flow.md#3-trust-boundary).

| ID | Tóm tắt |
|---|---|
| `TB-01` | Browser ↔ Web/API |
| `TB-02` | File/dataset không tin cậy ↔ Parser sandbox |
| `TB-03` | Nội dung/evidence không tin cậy ↔ Local AI |
| `TB-04` | Worker ↔ Internet — đóng trong baseline |
| `TB-05` | Role/workspace ↔ Corpus/index/evidence |
| `TB-06` | AI proposal ↔ Quyết định/publish |
| `TB-07` | API ↔ Queue/Worker |
| `TB-08` | Dataset/corpus source ↔ Governed store/experiment |
| `TB-09` | Runtime/store ↔ Log/export/backup |
| `TB-10` | API/Worker ↔ MongoDB/File storage/Index |

## 5. Security invariant

1. Mọi resource access phải được authorize ở server bằng actor + scope từ
   authoritative state; ID client gửi không chứng minh quyền.
2. Persistent store dùng private endpoint và service identity riêng; mỗi
   service chỉ có quyền đọc/ghi/xóa/backup tối thiểu cần thiết.
3. Scope filter chạy trước candidate retrieval, rank, prompt, cache và evidence;
   post-filter sau retrieval là không đủ.
4. File, dataset, extracted text, model output và metadata nhập từ ngoài đều là
   untrusted input.
5. Queue chỉ mang reference tối thiểu do server tạo; worker tải lại owner/scope/
   version/state và từ chối job stale, replay hoặc không hợp lệ.
6. Mọi artifact/result/evidence gắn immutable input/config version và checksum;
   index là derived artifact, không là source of truth.
7. Local AI không có tool, shell, Internet, secret, DB credential hoặc publish
   credential; output sai schema/evidence allowlist bị từ chối.
8. AI/worker/admin không tự publish kết quả học thuật; lecturer đúng scope mới
   được Accept/Edit/Reject và publish, có optimistic concurrency + audit.
9. Thiếu rights/purpose/retention/approver hoặc provenance thì fail closed.
10. Delete/tombstone chặn retrieval ngay và cascade tới derived artifact, cache,
   result, export và backup record theo policy.

## 6. Control catalog

| ID | Control thiết kế | Điểm thực thi dự kiến | Trạng thái 03/09 |
|---|---|---|---|
| `C-W21-01` | Authentication, session protection, server-side RBAC và object/scope authorization | API/auth middleware + policy service | `PLANNED` |
| `C-W21-02` | Upload gate: allowlist PDF/DOCX, magic/MIME/size/quota/path/checksum, quarantine | API + storage adapter | `PLANNED` |
| `C-W21-03` | Parser isolation: read-only/no-network/non-root, CPU/RAM/time/process/archive limit, output schema | Worker + parser sandbox | `PLANNED`; parser prototype chưa sandbox |
| `C-W21-04` | Queue integrity: server-created minimal payload, idempotency, authoritative reload, claim/ack, finite retry, transition guard | API + queue + worker + DB | `PLANNED` |
| `C-W21-05` | Immutable version/provenance/checksum, stable locator, atomic artifact generation, stale-generation guard | DB/storage/index/worker | `PARTIAL PROTOTYPE / NOT VERIFIED`; provenance chưa ổn định đầy đủ |
| `C-W21-06` | Pre-retrieval scope/purpose filter cho corpus, index, cache và evidence | Retrieval adapters + authorization tests | `PLANNED` |
| `C-W21-07` | AI containment: instruction/content separation, evidence allowlist, bounded context, no tools/egress/secrets, JSON schema + semantic verification | Worker + Local AI adapter | `PLANNED` |
| `C-W21-08` | Human decision gate, optimistic concurrency, Accept/Edit/Reject/publish separation và immutable audit | API + DB + review UI | `PLANNED` |
| `C-W21-09` | Context-aware output encoding, safe export, log/error redaction và correlation ID | Web/API/export/logging | `PLANNED` |
| `C-W21-10` | Dataset governance: rights/purpose/privacy/retention/approver/checksum/split/leakage gate | Importer + registry + experiment runner | `PLANNED` |
| `C-W21-11` | Tombstone/delete cascade, retrieval deny, cleanup verification và backup policy | API + worker + stores | `PLANNED` |
| `C-W21-12` | Network/secret/dependency/resource hardening: loopback/default-deny egress, secret management, lock/scan/SBOM, quota/monitoring | Deployment + CI + runtime | `PLANNED` |
| `C-W21-13` | Persistent-store hardening: private endpoint, per-service identity/least privilege, schema/operator allowlist, typed repository, checksum/CAS/atomic write và backup protection | API/worker + Mongo/storage/index | `PLANNED` |
| `C-W21-14` | Pagination integrity: random server-side handle hoặc AEAD cursor bind/hash endpoint, actor, workspace, scope, filter, immutable sort tuple, high-watermark/as-of boundary, expiry và schema version; re-authorize mỗi page; deterministic order có unique tie-break | API/query adapter | `PLANNED` |

## 7. Threat register và traceability

| Threat | Asset / boundary | Kịch bản và tác động | Khả năng / tác động → risk | Control | Test xác minh | Owner / status |
|---|---|---|---|---|---|---|
| `T-W21-01` Spoofing/CSRF/session theft | `A-01`, `A-02`, `A-06`; `TB-01` | Kẻ tấn công dùng session bị đánh cắp hoặc cross-site request để đọc report, chạy job hay review/publish | H / H → `CRITICAL` | `C-W21-01`, `C-W21-08`, `C-W21-12` | `AT-W21-01`, `AT-W21-10` | Q / `OPEN-DESIGN` |
| `T-W21-02` IDOR/cross-user access | `A-02–A-06`; `TB-01`, `TB-05` | Đổi report/run/chunk/evidence ID để đọc hoặc sửa resource lớp/người khác | H / H → `CRITICAL` | `C-W21-01`, `C-W21-06` | `AT-W21-02` | Q / `OPEN-DESIGN` |
| `T-W21-03` Malicious upload/parser exploit | `A-02`, `A-10`; `TB-01`, `TB-02` | MIME spoof, path traversal, malformed/polyglot PDF/DOCX hoặc payload khai thác parser để đọc file/chạy code | H / H → `CRITICAL` | `C-W21-02`, `C-W21-03`, `C-W21-12` | `AT-W21-03`, `AT-W21-04` | Q / `OPEN-DESIGN` |
| `T-W21-04` Resource exhaustion | `A-07`, `A-10`; `TB-01`, `TB-02`, `TB-03`, `TB-07` | File nhiều trang/object, decompression bomb, prompt/context lớn hoặc flood job làm hết RAM/CPU/disk | H / H → `CRITICAL` | `C-W21-02`, `C-W21-03`, `C-W21-04`, `C-W21-07`, `C-W21-12` | `AT-W21-04`, `AT-W21-12` | Q / `OPEN-DESIGN` |
| `T-W21-05` Forged/replayed/stale job | `A-02–A-07`; `TB-07` | Sửa payload, replay job hoặc chạy version đã xóa để ghi result sai scope/ghi đè state mới | M / H → `HIGH` | `C-W21-04`, `C-W21-05`, `C-W21-11` | `AT-W21-05` | Q / `OPEN-DESIGN` |
| `T-W21-06` Cross-tenant retrieval/cache leak | `A-02–A-04`; `TB-05` | Vector/BM25/cache truy candidate toàn cục rồi mới lọc, khiến text/report khác tenant vào rank, prompt hay evidence | H / H → `CRITICAL` | `C-W21-01`, `C-W21-06` | `AT-W21-02`, `AT-W21-06` | Q / `OPEN-DESIGN` |
| `T-W21-07` Prompt injection/data exfiltration | `A-01–A-06`; `TB-03`, `TB-04` | Report/source chứa lệnh yêu cầu bỏ rubric, tiết lộ prompt/secret, gọi tool/Internet hoặc gán điểm | H / H → `CRITICAL` | `C-W21-06`, `C-W21-07`, `C-W21-12` | `AT-W21-07` | Q + Y / `OPEN-DESIGN` |
| `T-W21-08` Hallucinated/tampered evidence | `A-03–A-06`; `TB-03`, `TB-05`, `TB-06` | Model tạo evidence ID/quote không tồn tại; stale index hoặc locator bị tráo làm rationale/score không có căn cứ | H / H → `CRITICAL` | `C-W21-05`, `C-W21-06`, `C-W21-07`, `C-W21-08` | `AT-W21-08` | Q + Y / `OPEN-DESIGN` |
| `T-W21-09` Stored XSS/export injection | `A-02`, `A-06`, `A-09`; `TB-01`, `TB-09` | Tên file, extracted text hay rationale chứa HTML/script; CSV chứa formula; mở evidence/export gây code execution/exfiltration | M / H → `HIGH` | `C-W21-02`, `C-W21-09` | `AT-W21-09` | Q + Y / `OPEN-DESIGN` |
| `T-W21-10` Unauthorized/overwritten publish | `A-05`, `A-06`, `A-09`; `TB-06` | Student/admin/worker publish, lecturer ngoài scope duyệt, hoặc stale UI ghi đè edit mới | M / H → `HIGH` | `C-W21-01`, `C-W21-08` | `AT-W21-10` | Q + Y / `OPEN-DESIGN` |
| `T-W21-11` Secret/PII leakage in logs/errors/backups | `A-01`, `A-02`, `A-06`, `A-09`; `TB-09` | Prompt/report/session/path/stack trace vào log, error response, export hoặc backup truy cập rộng | H / H → `CRITICAL` | `C-W21-09`, `C-W21-11`, `C-W21-12` | `AT-W21-11` | Q / `OPEN-DESIGN` |
| `T-W21-12` Unapproved, poisoned hoặc leaked dataset | `A-03`, `A-05`, `A-08`; `TB-08` | Dữ liệu thiếu license/consent vào corpus; file/label bị sửa; dùng test set để tune làm kết quả nghiên cứu sai | M / H → `HIGH` | `C-W21-05`, `C-W21-10` | `AT-W21-14` | Y + Q / `OPEN-DESIGN` |
| `T-W21-13` Incomplete deletion/resurrection | `A-02–A-04`, `A-06`, `A-09`; `TB-05`, `TB-09` | Xóa file gốc nhưng chunk/index/cache/result/export/backup vẫn retrieval được hoặc được rebuild lại | M / H → `HIGH` | `C-W21-05`, `C-W21-11` | `AT-W21-13` | Q / `OPEN-DESIGN` |
| `T-W21-14` Exposed service/default secret | `A-01–A-10`; `TB-10`, deployment boundary | API/Mongo/AI/queue bind LAN/Internet, CORS quá rộng, debug bật hoặc dùng default credential | M / H → `HIGH` | `C-W21-01`, `C-W21-12`, `C-W21-13` | `AT-W21-15` | Q / `OPEN-DESIGN` |
| `T-W21-15` Vulnerable/tampered dependency or model | `A-02`, `A-05`, `A-08`, `A-10` | Package/parser/model artifact độc hại hoặc version không khóa gây code execution/kết quả không tái lập | M / H → `HIGH` | `C-W21-05`, `C-W21-10`, `C-W21-12` | `AT-W21-16` | Q + Y / `OPEN-DESIGN` |
| `T-W21-16` SSRF/Internet disclosure khi mở extension | `A-01–A-05`; `TB-04` | URL/provider feature được mở lại và bị dùng để dò mạng nội bộ hoặc gửi report/query ra ngoài | L / H → `MEDIUM` dormant; đánh giá lại trước khi mở | `C-W21-07`, `C-W21-12`; change request bắt buộc | `AT-W21-17` nếu feature được mở | Q / `DORMANT-DISABLED` |
| `T-W21-17` Store tampering/NoSQL injection/over-privileged service | `A-02–A-09`; `TB-10` | Operator/query injection, credential dùng chung hoặc service quá quyền cho phép đọc/sửa/xóa chéo scope, tráo provenance/result hay phá index/backup | M / H → `HIGH` | `C-W21-01`, `C-W21-05`, `C-W21-06`, `C-W21-13` | `AT-W21-18` | Q / `OPEN-DESIGN` |
| `T-W21-18` Cursor tampering/replay và scope confusion | `A-02`, `A-04`, `A-06`; `TB-01`, `TB-05` | Sửa hoặc replay cursor giữa actor/workspace/endpoint/filter để đọc dữ liệu ngoài scope; concurrent insert làm lặp/bỏ sót item và tạo kết quả không nhất quán | M / H → `HIGH` | `C-W21-01`, `C-W21-06`, `C-W21-14` | `AT-W21-19`, `AT-W23-12` | Q / `OPEN-DESIGN` |

## 8. Adversarial test plan

Mọi test dưới đây đang `PLANNED`; cột `Pass condition` là tiêu chí tương lai,
không phải kết quả đã đạt. Test case phải dùng fixture synthetic/được phép,
không commit báo cáo thật hay secret.

| Test | Input/attack | Pass condition | Mức test / mốc | Owner | Status |
|---|---|---|---|---|---|
| `AT-W21-01` | Request không session, session hết hạn, CSRF và origin sai | `401/403`; không state change; cookie/CSRF/CORS đúng ADR; log không lộ token | API integration, W03/W16 | Q | `PLANNED` |
| `AT-W21-02` | Student/lecturer A đoán ID report, run, chunk, evidence của B | Tất cả read/write/list/search/cache path từ chối; không lộ existence/content | Authorization + E2E, W03/W16 | Q, Y review | `PLANNED` |
| `AT-W21-03` | Extension/MIME mismatch, `../` filename, duplicate, malformed/polyglot PDF/DOCX | Reject/quarantine an toàn; không path escape/overwrite/parser execution; safe error | API/parser contract, W03–W04 | Q | `PLANNED` |
| `AT-W21-04` | File cực lớn/nhiều object, archive bomb, parser hang/crash | Enforce byte/page/object/time/RAM/process limit; worker sống; terminal state và cleanup đúng | Sandbox/resource, W04/W16 | Q | `PLANNED` |
| `AT-W21-05` | Payload job giả, duplicate/replay, out-of-order transition, deleted/stale version | Worker reload authoritative state; reject hoặc idempotent; không artifact/result kép | Queue integration/chaos, W03–W04/W16 | Q | `PLANNED` |
| `AT-W21-06` | Query retrieval toàn cục, thiếu filter, cache key thiếu scope/purpose | Không candidate/text/score ngoài scope xuất hiện trước hoặc sau rank/prompt/cache | Retrieval negative test, W06–W08/W16 | Q | `PLANNED` |
| `AT-W21-07` | Report ghi “ignore rubric”, yêu cầu secret/tool/network/publish; indirect injection trong source | Instruction không được thi hành; no egress/tool/secret; output schema; action bị chặn và ghi metric | AI adversarial eval, W10/W13/W16 | Y, Q review | `PLANNED` |
| `AT-W21-08` | AI trả fabricated evidence ID, quote sai span, stale locator, wrong version | Reject/abstain; không score/publish; validator chỉ cho evidence allowlist resolve đúng checksum | Provenance/AI integration, W08/W10/W13 | Q + Y | `PLANNED` |
| `AT-W21-09` | HTML/script/event handler trong filename/text/rationale; CSV values `=cmd`, `+`, `-`, `@` | UI không execute; CSP/encoding đúng; export neutralize formula; JSON content type đúng | Web/export E2E, W15–W16 | Y, Q review | `PLANNED` |
| `AT-W21-10` | Student/admin/worker publish; lecturer khác lớp; stale review revision | `403/409`; chỉ lecturer đúng scope + current revision publish; actor/before-after/reason audit đủ | API/E2E, W15–W16 | Q + Y | `PLANNED` |
| `AT-W21-11` | Canary secret/PII trong request/report/prompt và induced exception; actor sai quyền thử đọc log/export/backup | Canary không có trong client error, operational log, trace hoặc metric label; unauthorized read bị chặn; backup nhạy cảm được bảo vệ theo ADR | Log/privacy/access integration, W03/W16 | Q | `PLANNED` |
| `AT-W21-12` | Flood upload/job, context quá dài, disk gần quota, model timeout | Rate/quota/backpressure/timeout/circuit behavior hữu hạn; service phục hồi; không starvation | Load/chaos, W04/W16/W21 | Q | `PLANNED` |
| `AT-W21-13` | Xóa report/dataset rồi query ID/span/index/cache/export; kiểm backup record | Retrieval bị chặn ngay; cascade/verification đạt; backup xử lý đúng documented policy | Lifecycle integration, W03/W16 | Q, Y review | `PLANNED` |
| `AT-W21-14` | Import thiếu license/purpose/checksum/approver; checksum sai; train/test duplicate | Deny before index/run; manifest immutable; leakage test báo lỗi; không có final metric | Data/experiment gate, W02/W17 | Y, Q review | `PLANNED` |
| `AT-W21-15` | Scan port/bind/CORS/debug/default credential trên clean deployment | Chỉ endpoint dự kiến reachable; DB/AI/queue không public; no default secret/debug; TLS khi qua mạng | Deployment security, W03/W16/W21 | Q | `PLANNED` |
| `AT-W21-16` | Dependency/model lock/checksum bị đổi; scan có High/Critical | Install/build fail hoặc gate chặn; provenance ghi version/hash; waiver có owner/expiry | CI/supply-chain, W03/W16/W21 | Q + Y | `PLANNED` |
| `AT-W21-17` | URL loopback/private/link-local/redirect/DNS rebinding và payload có PII | Feature vẫn disabled; nếu được mở thì deny private network/redirect bypass và không gửi PII ngoài policy | Conditional provider test | Q | `NOT APPLICABLE WHILE DISABLED` |
| `AT-W21-18` | NoSQL/operator injection; service API/worker dùng credential của nhau; direct DB/index access; concurrent stale write | Operator không được inject; endpoint private; credential sai quyền bị chặn; CAS/schema/checksum giữ toàn vẹn; audit không lộ content | Store authorization/integration, W02–W03/W16 | Q, Y review | `PLANNED` |
| `AT-W21-19` | Sửa token/handle/expiry hoặc replay cursor sang actor, workspace, endpoint, filter hay sort khác; insert item giữa hai page | Cursor sai trả `400 INVALID_CURSOR` và không lộ data/query; cursor hợp lệ không lặp/bỏ sót item theo snapshot/order contract | API/query integration, W03/W16 | Q, Y review | `PLANNED` |

## 9. Residual risk và quyết định còn mở

Chưa có residual risk nào được chấp nhận hoặc hạ mức vì implementation/test
chưa đầy đủ. Các quyết định sau phải có owner, evidence và ngày:

| ID | Quyết định cần khóa | Nơi xử lý | Default an toàn trước khi khóa |
|---|---|---|---|
| `OD-W21-01` | Localhost/LAN/Internet demo | GVHD + deployment ADR | Localhost/loopback |
| `OD-W21-02` | Session cookie hay token/SSO | `W2.3/W3.2` | Không invent auth contract; không expose qua mạng |
| `OD-W21-03` | Queue backend/ack/persistence | `W2.2/W3.6` ADR | Không nhận arbitrary client payload |
| `OD-W21-04` | Process/container parser sandbox | `W4.1.2` ADR | Chỉ synthetic fixture; không parse file thật không tin cậy như production |
| `OD-W21-05` | Storage/backup/delete SLA | `W2.2`, `W2.6.3` | Không dùng dữ liệu thật chưa duyệt |
| `OD-W21-06` | Mongo/index/graph deployment | `W2.2`, `G-03` | DB/index không expose client/network |
| `OD-W21-07` | Local AI/model/resource cap | `G-03` benchmark | No tool/egress/secret; bounded input |
| `OD-W21-08` | Rights/retention/delete authority | `W2.6.3`, GVHD | Deny import/index/experiment |

Rủi ro `CRITICAL/HIGH` không được coi là release-ready nếu chưa có test pass
hoặc waiver nêu lý do, owner, compensating control và ngày hết hạn.

## 10. Review và cập nhật

Threat model phải được review lại khi có một trong các thay đổi:

- mở hệ thống từ localhost ra LAN/Internet;
- thêm provider, crawler, OCR, tool-calling hoặc model remote;
- đổi auth, queue, DB/index, storage/backup, parser hoặc Local AI runtime;
- thêm data class/dataset thật, thay rights/retention hoặc xuất thêm định dạng;
- thêm actor/role, auto-scoring/auto-publish hoặc thay trust boundary;
- trước `G-03`, `G-07` và release `G-09/G-10`, hoặc sau incident/test fail.

### Checklist đóng `W2.1`

- [x] Có asset và trust-boundary inventory.
- [x] Có threat → control → verification test traceability.
- [x] Bao phủ upload/parser, queue, DB/index/tenant retrieval, prompt injection,
  store authorization/tampering, evidence integrity, output sanitization, log
  privacy, dataset và lifecycle.
- [x] Không mô tả control/test chưa chạy là đã đạt.
- [ ] Đồng bộ scope `W1.1` trong SRS/Use Case cũ.
- [ ] Yến review ít nhất toàn bộ threat `CRITICAL`, xác nhận owner/mốc test và ghi
  approval/comment truy vết được.

| Vai trò | Họ tên | Quyết định | Ngày | Evidence/comment |
|---|---|---|---|---|
| Owner | Nguyễn Trần Ngọc Quý | Chờ xác nhận |  |  |
| Reviewer | Võ Thị Kim Yến | Chờ review |  |  |
