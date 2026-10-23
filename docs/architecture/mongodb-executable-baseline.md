# MongoDB executable baseline

Baseline này hiện thực một phần thiết kế ở ADR-001, không thay thế repository
authorization hay nối app local sang MongoDB một cách ngầm định.

Compose hiện dùng replica-set name `kltn-rs`; ADR design ghi `rs0`. Đây là
configuration deviation cần reviewer xác nhận. URI/health/test đã dùng nhất
quán `kltn-rs`; không tự đổi tên replica set trên volume đang có dữ liệu.

## Phạm vi đã có code

- Migration `001-identity-and-job-validators-v1`: validator strict/error cho
  `users`, `workspaces`, `memberships`, `jobs`; unique identity/membership/job
  keys và job claim indexes; checksum giữ nguyên khi bổ sung migration mới.
- Migration 002 thêm auth credentials/sessions/throttles, audit, rubric/version
  và operation idempotency. Migration 003 thêm documents/versions/files,
  governance, elements/chunks và upload operations. Còn index/analysis/graph/
  review/publication/lifecycle catalog; chưa coi đây là toàn bộ data dictionary.
- Preflight hình dạng document, trùng giá trị unique và index options drift;
  không sửa/xóa dữ liệu để lách lỗi. Áp dụng additive và đọc lại validator,
  field order/unique/partial/TTL options trước khi ghi ledger.
- Ledger dùng migration ID ổn định ở `_id`, checksum, code commit, operator,
  duration và verification summary; reapply giữ nguyên hồ sơ áp dụng ban đầu,
  chỉ cập nhật các field `last_verified_*`. Record `__lock__` là lease vận hành riêng,
  không phải migration đã áp dụng; đây là ngoại lệ có chủ đích đối với common
  ObjectId/audit fields của các collection nghiệp vụ.
- Ba custom database roles `kltn_api`, `kltn_worker`, `kltn_migration`, không
  kế thừa `readWrite`, `dbAdmin` hoặc `root`. API không ghi AI evidence/proposal;
  worker không sửa account/membership hoặc đọc/ghi review/publication. Hai
  runtime identities chỉ append audit, không sửa/xóa audit, không migration,
  không tạo index/user và không truy cập database khác.

Worker cần đọc identity status/membership/governance để kiểm lại quyền sau
claim. MongoDB collection role không lọc được workspace hoặc field PII; repository
vẫn phải dùng projection tối thiểu và scope predicate. **DB roles không phải
application RBAC.** Chưa cấp quyền remove cho runtime, vì cascade physical
purge và restore guard chưa được hiện thực/review. Chưa tạo backup identity
khi chưa có backup/restore procedure được kiểm thử.

## Chạy trên máy phát triển

```bash
.venv-research/bin/python scripts/prepare_mongodb_local.py
docker compose -f infra/mongodb/compose.yaml up -d --wait
.venv-research/bin/python scripts/test_mongodb_local.py --restart
# Sau khi migration/bootstrap source đã commit; dừng API/worker trước khi apply:
.venv-research/bin/python scripts/setup_mongodb_local.py --operator ngwine
```

Bootstrap chỉ kết nối loopback từ file admin URI private đã có, tạo/đồng bộ
role đúng database và ghi URI runtime ở `var/infra/mongodb/*_app-uri` (0600).
Không copy URI, password, replica key vào Git, report hoặc command line.
Không dùng admin URI cho API/worker. [Authenticated app](./authenticated-mongo-app.md)
đọc đúng URI của từng role; demo local cũ không tự chuyển database.

Entrypoint copy secret từ read-only Compose mount sang tmpfs, owner `mongodb`,
mode `0400` trước khi official entrypoint drop root. Host secret vẫn `0600`;
không nới quyền file gốc để chữa permission khác nhau giữa Linux/Docker Desktop.
Bootstrap fresh-volume cũng phải qua CI, không chỉ test trên volume đã có DB.

Migration có lease năm phút, renew trước các DDL, cùng server/driver timeout;
lease chỉ phối hợp maintenance client, **không phải atomic fence cho DDL**.
MongoDB không gộp `collMod`/`createIndexes` với kiểm tra lease trong một
transaction. Phải dừng mọi writer và process migrator cũ trước khi resume.
Nếu crash giữa các bước, validator/index đã tạo được giữ lại; chạy lại cùng
ID/checksum sẽ xác minh và tiếp tục. Không có tự động rollback/drop index.
Drift detection đối chiếu các named indexes trong manifest; chưa kết luận
mọi index bổ sung do operator tạo đều hợp lệ hoặc tối ưu. Không tự xóa chúng.

## Kiểm chứng

Integration tests dùng database/user/role test tên ngẫu nhiên, sau đó chỉ xóa
state do chính test tạo. Chúng kiểm tra reapply/checksum drift/preflight,
validator từ chối malformed document, unique key, queue lifecycle sau validator,
quyền đọc/ghi hợp lệ và thao tác vượt quyền bị từ chối. Suite mở rộng còn kiểm
HTTP session/current RBAC, rubric transaction và upload → bounded parser →
chunks bằng API/worker identities riêng trên TXT/PDF/DOCX tổng hợp. Có fault
injection rollback giữa elements/chunks. Chưa có full analysis/index/lifecycle
integration, backup/restore hoặc chất lượng mô hình trên gold data.

Tài liệu tham chiếu: [MongoDB schema validation](https://www.mongodb.com/docs/manual/core/schema-validation/update-schema-validation/),
[collection-level access control](https://www.mongodb.com/docs/manual/core/collection-level-access-control/),
[privilege actions 8.0](https://www.mongodb.com/docs/v8.0/reference/privilege-actions/).
