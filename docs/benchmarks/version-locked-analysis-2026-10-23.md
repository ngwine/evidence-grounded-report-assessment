# Mongo index và hai pipeline — kiểm chứng 23/10/2026

Branch: `feat/w6-w10-mongo-analysis`, kế thừa PR #20 tại `984c617`.
Backend commit `4f443fb`; web/real-browser CI commit `2771665`.
Đây là kiểm thử software/integration, không phải bảng kết quả chất lượng cho
bài báo. Không có dữ liệu thật/PII, gold label hoặc quyền dataset mới được
tự phê duyệt trong lượt này.

## Kết quả

| Kiểm tra | Kết quả thực tế |
|---|---|
| Toàn bộ Python suites, bật dedicated Mongo + cached-model opt-in | **546 passed, 1 skipped**, 87.63 giây; skip là private DOCX không có file |
| Cùng suites không bật real-model opt-in | **545 passed, 2 skipped**; không tính skipped model là đã chạy |
| Real-Mongo runtime-role BOTH smoke | BM25 và research-v0 **2 passed**; có fault injection rollback/retry |
| Real Chromium authenticated web → Mongo → workers | **1 passed**, upload report/source → PARSE → BM25 INDEX → BOTH → evidence → review → JSON export → reload session |
| Authenticated UI mock contracts | **3 passed**; không gọi đây là Mongo E2E |
| TypeScript/Vite authenticated build | PASS |
| Ruff E4/E7/E9/F | PASS backend/core/retrieval/graph và scripts/tests mới |
| Scoped Mypy | PASS DB catalog 8 files; API/domain/workers 17 files với explicit namespace/import-skip flags |
| Bandit medium/high | PASS backend |
| Whitespace diff check | PASS |

Bootstrap thật từ source đã commit đã apply/reapply migrations 001–004 bằng
migration identity; worker CLI ALL `--once` kết nối bằng worker identity và
thoát an toàn với queue rỗng. Không tạo account mặc định hoặc tự approve input.

Mongo test project riêng `kltn-auth-app-check`, pinned Mongo8.0.34/`kltn-rs`,
loopback27188. Runtime HTTP dùng `kltn_api`, workers dùng `kltn_worker`; admin
chỉ bootstrap/migration/test fault injection. Test tạo random databases/users/
roles và chỉ dọn state của chính nó. Không sử dụng Mongo của project khác.

Real-model smoke dùng cache offline E5-small revision
`614241f622f53c4eeff9890bdc4f31cfecc418b3` và mMARCO Cross-Encoder revision
`1427fd652930e4ba29e8149678df786c240d8825`. Test xác minh manifest ghi
`index_vectors_reused=true` và số document vectors reuse > 0. Không tải model
hoặc chạy TEST0 để chọn tham số. CPU/memory/time ở đây không thay benchmark
model-quality/resource envelope trên máy hai thành viên.

## Điều được xác minh

- Source generation/head/rebuild và private BM25/E5 artifact có config/hash/
  version lock; generation cũ không đẩy active pointer lùi sau rebuild mới.
- Input pins gồm report/source/parser/chunk/rubric/index/config; core pipeline
  được reuse, không viết lại heuristic ở API/frontend.
- Bounded model/pipeline subprocess và heartbeat/lease fence; lỗi model explicit,
  không tự fallback thành phương pháp khác mà vẫn dùng tên research-v0.
- Results/evidence/manifest trong một transaction: cố ý lỗi sau result trước
  evidence không để lại output; retry chỉ có một result và completion audit.
- Current access/governance được kiểm trước/during/after run; thu hồi quyền
  chặn result/evidence/export/review. Chunk/element raw hashes và exact span
  references được kiểm; result/manifest/evidence bị sửa thì read fail closed.
- Review gắn tài khoản/revision, immutable audit record và retry cùng nội dung;
  không tự publish điểm hay kết luận đạo văn.

## Vẫn chưa hoàn thành

Pipeline 2 vẫn là authored phrase/negation verifier, GRAPH vẫn structure/term
PPR; chưa có semantic/cross-source entailment, claim/entity/relation extraction
hay Mongo graph build/provenance API. Pipeline 1 semantic classifier chưa được
gold-calibrate. PDF mới có page link + text/span evidence, chưa geometric
highlight. Full account/data lifecycle, backup/restore, physical cascade purge,
LLM benchmark và approved DEV1/gold evaluation vẫn mở. Không dùng test pass để
đóng các mục này hoặc ký thay reviewer.

Lệnh chạy và API/web flow ở
[version-locked analysis app](../architecture/version-locked-analysis-app.md).
CI của commit mới phải được kiểm riêng; CI PR #20 không bao phủ thay đổi này.
