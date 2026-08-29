# Quy ước cộng tác

Quy ước này áp dụng cho mọi thay đổi của dự án. `main` là nhánh tích hợp ổn
định; không phát triển trực tiếp trên `main`.

## 1. Branch

Tạo branch mới từ `main` đã cập nhật, theo mẫu:

```text
<type>/<backlog-id>-<mo-ta-ngan>
```

- `type`: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `experiment`.
- `backlog-id`: viết thường từ canonical ID, ví dụ `ep-02-s01` hoặc `w3-1`.
- Phần mô tả dùng chữ thường, số và dấu gạch ngang; không dùng tên cá nhân.

Ví dụ: `docs/w1-5-git-workflow`, `feat/ep-03-s01-upload-report`.

Mỗi branch chỉ xử lý một outcome hoặc một thay đổi có thể review độc lập. Nếu
scope thay đổi, cập nhật issue/PR trước khi tiếp tục.

## 2. Commit

Dùng Conventional Commits:

```text
<type>(<scope>): <mô tả ở thể mệnh lệnh> [<BACKLOG-ID>]
```

Ví dụ:

```text
docs(planning): document Git review workflow [W1.5]
feat(upload): validate report MIME and size [EP-03-S01]
```

- Commit phải nhỏ, chạy được và không trộn refactor không liên quan.
- Không commit secret, `.env`, PII, báo cáo thật, model weight, cache hoặc log.
- Khi hành vi thay đổi, commit phải kèm test và tài liệu/schema liên quan.
- `experiment` phải lưu config/seed/dataset version/hardware và đường dẫn raw
  result; không commit dữ liệu chưa được phép.

## 3. Pull request

1. Mở draft PR sớm và dùng template của repository.
2. Tiêu đề theo mẫu `[BACKLOG-ID] Động từ + kết quả kiểm chứng được`.
3. Gắn issue, milestone, label type/component/priority/risk phù hợp và ghi rõ
   artifact/evidence kiểm chứng.
4. Author tự review diff và chạy checks liên quan trước khi chuyển `Ready for
   review`.
5. Thành viên còn lại review; author không tự approve PR của mình.
6. Chỉ merge khi có ít nhất một approval chéo, mọi conversation đã resolve và
   checks bắt buộc đã pass. Thay đổi scope/data-rights/gate cần thêm xác nhận
   được quy định trong WBS.
7. Dùng `Squash and merge`, giữ tiêu đề PR làm commit message và xóa branch sau
   merge. Không force-push sau khi reviewer đã approve nếu không thông báo và
   yêu cầu review lại.

Nếu cần sửa khẩn cấp, vẫn mở PR và ghi lý do; không bỏ qua review đối với thay
đổi security, quyền dữ liệu, schema, metric hoặc kết quả thực nghiệm.

## 4. Trách nhiệm review

| Author | Reviewer bắt buộc |
|---|---|
| Nguyễn Trần Ngọc Quý (Q) | Võ Thị Kim Yến (Y) |
| Võ Thị Kim Yến (Y) | Nguyễn Trần Ngọc Quý (Q) |

Reviewer kiểm tra phạm vi/AC, tính đúng đắn, test/evidence, security/privacy,
tài liệu và khả năng tái lập. Approval trên GitHub là bằng chứng review; trao
đổi ngoài GitHub phải được tóm tắt lại trong PR.

## 5. Liên kết kế hoạch

- Product outcome dùng `EP-xx-Sxx`; work package dùng `Wn.m`.
- Issue và PR phải ghi ít nhất một ID ở tiêu đề hoặc phần mô tả.
- Chỉ chuyển item sang `DONE` khi PR/artifact đã merge, đạt DoD và có reviewer
  chấp thuận.
- Board dùng luồng `Backlog → Ready → In Progress → Review → Test/Verify →
  Done`; trạng thái canonical vẫn theo Product Backlog/WBS.
