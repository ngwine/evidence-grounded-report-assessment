# MongoDB local replica set

W3.1 baseline dùng MongoDB Community 8.0.29, pin image digest, một replica-set
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
