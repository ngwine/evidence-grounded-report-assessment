# MongoDB local replica set

W3.1 baseline dùng MongoDB Community 8.0.34, pin image digest, một replica-set
member, xác thực SCRAM/keyfile và volume riêng `kltn-evidence-db_*`. Host chỉ
mở `127.0.0.1:27188`. Bộ này phục vụ phát triển và integration test; API/worker
hiện vẫn dùng local store và chưa sử dụng database này.

[Executable baseline](../../docs/architecture/mongodb-executable-baseline.md)
có migration/validator bốn collection và ba database identities tách quyền.
Sau khi commit source và dừng writer, chạy
`.venv-research/bin/python scripts/setup_mongodb_local.py --operator ngwine`;
không đưa URI/password private vào cấu hình public hoặc Git.

```bash
.venv-research/bin/python scripts/prepare_mongodb_local.py
docker compose -f infra/mongodb/compose.yaml up -d --wait
docker compose -f infra/mongodb/compose.yaml ps
.venv-research/bin/python scripts/test_mongodb_local.py --restart
```

Secret ngẫu nhiên nằm dưới `var/infra/mongodb/`, không có trong Git. Script giữ
nguyên secret đã tạo để lần khởi động sau dùng được volume cũ. URI admin dùng
cho setup/test ở file `admin-uri`; không dùng tài khoản admin cho API/worker.
Custom roles migration/API/worker đã được bootstrap; repository/auth integration
và toàn bộ collection validators vẫn chưa xong. Không công khai port/chia sẻ URI.
`prepare` kiểm lại mode/nội dung URI và từ chối port/credential drift, không
ghi đè secret để ép volume cũ khởi động. Bootstrap runtime URI hiện quản lý một
application database duy nhất; nếu đổi `--database`, phải tách cấu hình secret
trước, không xóa credential hoặc database đang dùng để vượt reconciliation.

Ngày 23/10 nâng bản vá 8.0.29 → 8.0.34 sau khi CI báo event `12257600`
(TCMalloc/rseq kernel guard); image vẫn pin digest cho amd64/arm64.
Không tắt guard hoặc đổi `GLIBC_TUNABLES` để vượt lỗi kernel. Host phải đáp ứng
[kernel compatibility trong release notes](https://www.mongodb.com/docs/manual/release-notes/8.0/)
và [SERVER-125742](https://jira.mongodb.org/browse/SERVER-125742).
Kiểm thử bản vá dùng volume mới riêng, không nâng/xóa volume cũ để chạy test;
trước khi dùng image mới với volume có dữ liệu cần giữ, phải backup và xác nhận
quy trình upgrade/restore. Đổi image trong Git không tự tạo backup.

CI Mongo target được khai báo riêng là `ubuntu-22.04` hosted runner; các job
Python/web vẫn dùng `ubuntu-latest`. Label OS không pin kernel: CI ghi `uname`,
runner image version và image digest, giữ startup guard và fail nếu target
không tương thích. Không suy rộng CI/local pass thành hỗ trợ mọi Linux kernel.

Healthcheck yêu cầu authenticated writable primary. Init service chỉ tạo
replica set nếu chưa có. Muốn dừng mà giữ dữ liệu:

```bash
docker compose -f infra/mongodb/compose.yaml down
```

Không dùng `down -v` với dữ liệu cần giữ. Single-node replica set kiểm thử
transaction/restart, không đem lại khả năng chịu lỗi nhiều node. Xem
[ADR-001](../../docs/adr/ADR-001-mongodb-provenance-storage.md),
[MongoDB keyfile setup](https://www.mongodb.com/docs/manual/tutorial/deploy-replica-set-with-keyfile-access-control/)
và [official image](https://hub.docker.com/_/mongo/) cho cách bootstrap.
