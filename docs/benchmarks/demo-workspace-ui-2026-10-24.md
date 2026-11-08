# Kiểm tra giao diện demo — 24/10/2026

Branch `feat/demo-workspace-ui` nối tiếp item-review/evaluation. Đây là bản cải
thiện trải nghiệm sử dụng, không phải thay đổi thuật toán hoặc kết quả khoa học.

## Đã thay đổi

- Sidebar phân tích, kho tài liệu, rubric; workspace duy nhất được chọn tự động.
- Một nút phân tích chuẩn bị index thật trước khi enqueue ANALYZE; giữ config
  và phiên bản nguồn rõ ràng, không fallback ngầm khi model/index lỗi.
- Chọn hồ sơ quyền đã duyệt từ API thay vì buộc nhập ObjectId. Selector không
  cấp quyền mới; upload/worker vẫn kiểm lại current governance, purpose, expiry,
  anonymization và tombstone. Hồ sơ đã gắn document không thành lựa chọn mới.
- Rubric editor theo tiêu chí, checklist và evidence requirements. Advanced JSON
  có thể mở khi cần; published version không bị sửa trực tiếp.
- Kết quả có tab đối chiếu / rubric / evidence, lọc exact vs unverified, đoạn
  report/source cạnh nhau và human-readable checklist reasons. Hash, raw JSON,
  phiên bản, manifest và item annotation chuyên sâu được đưa vào details.
- Truy hồi lượt đã lưu từ danh sách theo report, không bắt người dùng nhớ run ID.

## Kiểm chứng

| Kiểm tra | Kết quả |
|---|---|
| Python suites với dedicated Mongo + cached-model opt-in | 636 passed, 1 skipped (private DOCX thiếu), 86.06 giây |
| Browser → Mongo thật, upload → auto index → hai kết quả → review/export/reload | 1 passed, 19.9 giây |
| Mocked auth/rubric/item review, gồm visual editor không JSON | 6 passed, 12.2 giây |
| Governance selector negative/positive/pagination | 21 passed |
| TypeScript/Vite build; Ruff; scoped selector Mypy; Bandit | PASS |
| Kiểm tra desktop và 390px mobile | Không horizontal overflow; screenshots riêng trong `var/` |

Các kiểm thử browser dùng self-authored fixtures, không phải chấm report sinh
viên hoặc đánh giá model trên gold. Hai PDF tự viết trong workspace demo cho
ra exact-match coverage 46%, và 1 MET / 1 UNMET / 1 CANNOT_ASSESS từ code thật.
Đây là **kịch bản minh họa**, không phải empirical result. Seed chạy lại cùng
checksum/idempotency key giữ nguyên report/version/rubric/run, không tạo bản
trùng. Tài khoản, mật khẩu, file demo và outputs không nằm trong Git.

Semantic/cross-source verification, calibrated paraphrase classification,
graph extraction và geometric PDF highlighting vẫn chưa được hiện thực bởi
đợt sửa giao diện này. Không dùng UI mới để tuyên bố các mục đó DONE.
