# Authenticated app: index → hai pipeline → evidence/review

Luồng này tiếp nối [auth/rubric/upload/PARSE](./authenticated-mongo-app.md).
API và worker mới dùng MongoDB; `/api/local/v1` cũ vẫn độc lập, không chuyển
kết quả cũ thành authenticated result.

```text
Report/source upload → PARSE → immutable version/elements/chunks
Source version → INDEX → BM25 postings + optional cached E5 vectors
  → generation activation (transaction, lease fence)
Report version + explicit source versions + published rubric version + config
  → freeze active source generation IDs + content/config/rubric hashes
  → ANALYZE worker → bounded subprocess → existing two pipelines
  → transaction: result + evidence + manifest + terminal run/job state
  → authorized web/API/export → lecturer review revision (not publication)
```

## Đã hiện thực

- Mỗi version/config có generation history và active head; rebuild không ghi đè
  artifact cũ. Một rebuild cũ chạy chậm không thể kéo head lùi lại sau yêu cầu
  mới hơn. Artifact 0600/parent 0700, checksum và canonical chunk/provenance
  được đối chiếu lại trước khi dùng. Mongo là source of truth; artifact là
  dữ liệu dẫn xuất, không phải registry quyền truy cập.
- Lexical index lưu BM25 postings/lengths. Analysis ghép corpus theo source
  scope đã khóa rồi dựng BM25 statistics cho corpus kết hợp; chưa tối ưu thành
  một lexical daemon. Dense index lưu E5 vectors thật; source vectors được
  reuse chỉ trong document-prefix mode khi text khớp, query vẫn encode riêng.
- Cấu hình server chỉ nhận `bm25-smoke` hoặc `research-v0`. Không nhận model,
  path hay prompt tùy ý từ client. `bm25-smoke` không dùng Dense/reranker;
  `research-v0` dùng model/revision trong config đã commit và cache offline.
  Thiếu model/timeout thì job báo lỗi có mã; không tự thay bằng toy embedding
  hoặc lặng lẽ trả kết quả BM25 dưới tên research-v0.
- Run khóa report version, source versions/generation IDs, parser generation,
  content/chunk hashes, config và published rubric compiled hash. Tạo run,
  idempotency operation và ANALYZE job cùng transaction. Cả `BOTH`, `SIMILARITY`
  và `ASSESSMENT` dùng lại core pipeline, không tạo classifier thứ hai ở web.
- ANALYZE subprocess có wall/CPU/file/input/output limits; parent heartbeat,
  kiểm cancellation/lease và kill child nếu mất lease. Index encoder có
  process budget/offline-only; không truyền Mongo URI qua biến môi trường model.
  Linux có address-space cap; macOS không tuyên bố hard RAM cap.
- Run/result/evidence/manifest commit dưới một lease fence. Fault injection
  giữa result/evidence phải rollback; retry không để lại output nửa chừng.
  Result và evidence có checksum; đọc/export/review từ chối payload bị sửa.
- Current user/membership/workspace, ownership, lifecycle, tombstones,
  current và pinned governance đều được kiểm lại khi enqueue, claim, commit
  và đọc kết quả. Quyền bị thu hồi không được dùng một historical generation
  hoặc run đã hoàn tất để vượt kiểm soát. Kiểm tra này không phải bằng chứng
  linearizable revocation giữa filesystem và nhiều Mongo collection.
- Web có library/upload/version/status, chọn explicit source/rubric/config,
  polling, hai báo cáo, evidence, JSON export và review ACCEPT/REJECT theo
  tài khoản/revision. Không lưu nội dung/token vào browser storage.
- File version endpoint kiểm scope/quyền/hash trước khi trả bytes; PDF mở ở
  page coordinate nếu có. Đây **chưa phải** geometric highlight chính xác trên
  PDF; exact ranges/raw–normalized/source spans vẫn được trả để kiểm tra.

## Chạy

Commit source migration trước, dừng writers rồi bootstrap như hướng dẫn auth.
Bootstrap hiện apply migrations 001–004. Không đổi checksum migration 001–003.

```bash
.venv-research/bin/python scripts/setup_mongodb_local.py --operator ngwine
.venv-research/bin/uvicorn services.backend.src.kltn_ai.api.runtime:create_runtime_app --factory --host 127.0.0.1 --port 8001
VITE_APP_MODE=authenticated npm --prefix apps/web run dev -- --port 5173
```

Terminal worker:

```bash
HF_HOME=var/models/hf-home HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
  .venv-research/bin/python scripts/run_mongo_worker.py
```

Worker mặc định xử lý PARSE, INDEX, ANALYZE theo thứ tự. `--once` chỉ xử lý
tối đa một job; loop mặc định thoát sau 100 claims hoặc 60 idle polls, không
phải daemon tự restart. Có thể chạy riêng bằng `--job-type PARSE|INDEX|ANALYZE`.

1. Login, chọn workspace, tạo/publish rubric với atomic requirements.
2. Upload report/source bằng governance record đã được người có thẩm quyền
   duyệt đúng resource/purpose; UI không có nút tự bỏ qua license/consent.
3. Đợi PARSED. Index các source version với cùng config định chạy. Report có
   thể được index riêng nhưng analysis v0 không bắt buộc report index.
4. Chọn report version, source versions và published rubric; tạo `BOTH` run.
5. Xem evidence/version/manifest, review và export JSON. Không có official
   grade/plagiarism publication tự động.

## Kiểm thử và giới hạn

`test_mongo_analysis_flow.py` kiểm HTTP, source/report isolation, quyền bị thu
hồi trước/sau/during run, provenance tamper, result/evidence tamper, idempotency,
review revision và transaction rollback bằng API/worker DB identities riêng.
`test_mongo_index_flow.py` kiểm activation/rebuild/stale generation, artifact
integrity, authorization và model failure không fallback ngầm.

```bash
.venv-research/bin/python scripts/test_mongodb_local.py
cd apps/web
npx playwright test --config playwright.mongo.config.ts
```

Browser Mongo E2E cần Compose test riêng đang chạy. Bootstrap chỉ tạo database
tên ngẫu nhiên, account/quyền cho bytes tự viết, rồi dọn đúng state test tạo.
Không dùng report thật hoặc tự approve dataset; không chạy song song server
khác trên cổng 8001/5173. CI chạy bộ này trong job Mongo riêng.

Real-model smoke là opt-in `KLTN_TEST_LOCAL_MODELS=1`, dùng cache tại HF_HOME;
không tải weight trong CI. Không ghi URI vào lệnh, Git, ảnh hoặc báo cáo.

Việc cả hai pipeline chạy qua app chứng minh luồng thực thi/tính truy vết,
**không chứng minh hiệu quả học thuật**. Pipeline 1 vẫn chưa có bộ phân loại
PARAPHRASE/SUMMARY được hiệu chuẩn bằng gold data. Pipeline 2 dùng authored
phrase/negation baseline, chưa có semantic/cross-source entailment. GRAPH mode
vẫn là structure/term PPR baseline, không phải claim/entity/relation extraction.

## Còn mở trong danh sách W1–W11

- W11: extraction → graph build/checkpoint → Mongo graph/provenance API và
  graph QA trên nhãn thật; chưa được hiện thực bởi lượt index/analysis này.
- W10: semantic/cross-source verifier và evaluation; custom rubric score levels
  vẫn bị publish từ chối khi chưa có rule engine thực thi.
- W8: geometric PDF highlight, export định dạng trình bày, calibrated semantic
  classifier và đánh giá chất lượng; hiện mới có JSON export/page link.
- W3/W5: backup/restore, account lifecycle tooling, data approval workflow,
  retention/tombstone cascade/physical purge đầy đủ và network/TLS deployment.
- W4/W5: parser/citation corpus rộng hơn, local LLM benchmark, model selection
  trên approved DEV1; không dùng synthetic integration test thay gold evaluation.
- Quyền dataset/report, gán nhãn độc lập, adjudication và review chéo phải có
  bằng chứng con người; không tự ký hoặc đổi PENDING thành APPROVED.
