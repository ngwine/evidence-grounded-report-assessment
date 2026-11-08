# Nhận phiếu SEFORA của Yến — 07/11/2026

> Cập nhật sau bước nhận: người phụ trách đã yêu cầu chạy. Hai cấu hình
> đã được khóa và hoàn thành 90 quyết định local; xem
> [hồ sơ lượt chạy](sefora-p2-single-reference-result-2026-11-07.md).
> Phần bên dưới ghi trạng thái tại thời điểm nhận và kiểm phiếu.

Người phụ trách chọn dùng **một người gán nhãn** cho bộ 15 bài Class_2;
không yêu cầu Quý làm phiếu thứ hai. Thiết kế hiện tại là đánh giá thăm dò
với nhãn tham chiếu của một người có AI hỗ trợ, không phải gold đồng thuận
hai người. Không tính tỷ lệ đồng thuận hay Cohen's kappa.

## Phiếu nhận được

- Nguồn: `PHIEU_GAN_NHAN_YEN.xlsx`, nhận ngày 07/11/2026.
- SHA-256: `5818dedd4c8b14f3da6b95903ffbf704bd6303cf156e39009b13871f778fb34d`.
- Đúng 15 bài × 3 checklist, không thiếu nhãn, không có UNSURE.
- Yến khai ngày hoàn thành 06/11/2026, tự đọc/ghi câu trả lời rồi trao đổi
  với Claude; chưa xem nhãn người khác, dự đoán P2 hoặc nhận xét giảng viên.
  Đây là khai báo trong phiếu, không phải chứng nhận độc lập của chương trình.

| Checklist | MET | UNMET | CANNOT_ASSESS |
| --- | ---: | ---: | ---: |
| CLM001 — Luận điểm trung tâm | 13 | 2 | 0 |
| EXP001 — Trải nghiệm cá nhân | 15 | 0 | 0 |
| QUO001 — Hai trích dẫn nguồn | 14 | 1 | 0 |
| Tổng | 42 | 3 | 0 |

## Kiểm tra và bản dẫn xuất

Validator nghiêm ngặt chấp nhận 43/45 mục trong file gốc. Hai lỗi còn lại
ở ô `GAN_NHAN!G31` và `GAN_NHAN!G40`: dấu nháy cong/thẳng và gạch ngang
`–`/`--` khác văn bản nguồn. Cả bốn đoạn trích trong hai ô khớp duy nhất
trong đúng paragraph đã khai khi chỉ quy đổi các dấu này.

Đã tạo **bản dẫn xuất riêng**, thay hai ô bằng đúng chuỗi nguồn để lấy
offset Unicode. Không đổi nhãn, lý do, paragraph ID hoặc khai báo người
gán; không thay từ hay số. File gốc trên Desktop và bản lưu nhận được giữ
nguyên bytes. Đây là sửa căn cứ kỹ thuật do Codex thực hiện, không phải
Yến gán lại hoặc chương trình chứng nhận nội dung trích dẫn đủ sức hỗ trợ nhãn.

Bản dẫn xuất qua kiểm tra cấu trúc/căn cứ **45/45 mục**: 42 `SPAN_SET`,
3 `DOCUMENT_ABSENCE`. Cả ba record vắng nội dung giữ xác nhận đọc toàn văn,
phạm vi toàn bộ paragraph và lý do của người gán; không tạo quote/span giả.

Hồ sơ riêng tư nằm ở
[`var/paper/p2-single-annotator-2026-11-07/v1/`](../../var/paper/p2-single-annotator-2026-11-07/v1/):

- `originals/PHIEU_GAN_NHAN_YEN.xlsx`: bản nhận nguyên gốc, chỉ đọc.
- `canonical-original.json`: kết quả kiểm file nhận, giữ hai lỗi ban đầu.
- `PHIEU_YEN_SOURCE_EXACT_DERIVED.xlsx`: bản sửa đúng hai ô trích dẫn.
- `canonical-source-exact-derived.json`: nhãn/căn cứ từ bản dẫn xuất.
- `source-anchor-repairs.json`: giá trị trước/sau, vị trí nguồn và từng dấu đổi.
- `receipt-and-summary.json`: checksum, thiết kế một người và giới hạn kết luận.
- `receive_yen.py`: mã tạo hồ sơ; từ chối ghi đè bản đã lưu.
- `single-intake/`: kết quả nhận bản dẫn xuất bằng chế độ một người. Không
  có mục lỗi; flag `AI_ASSISTANCE_DECLARED` được giữ để mô tả phương pháp,
  nên trạng thái là `NEEDS_REVIEW`, không phải thiếu phiếu thứ hai.

Kiểm tra phần mềm của lượt nhận này: **86 test đạt**, gồm đường nhận một
người, đường nhận hai người hiện có và evidence contract. Ruff và
`git diff --check` đạt.

Hai bundle và hướng dẫn gốc ngày 05/11 vẫn được giữ nguyên. Chỉ kế hoạch
sử dụng nhãn thay đổi theo yêu cầu người phụ trách; không giả lập phiếu Quý
hoặc nới đường freeze gold-v1 vốn yêu cầu hai người.

## Phạm vi đánh giá tiếp theo

Có thể dùng bộ này để chuẩn bị một phép đánh giá thăm dò P2 với nhãn tham
chiếu một người, ghi rõ AI hỗ trợ và các chỉnh sửa căn cứ kỹ thuật. Chưa gọi
model trên 15 bài, chưa tạo gold được phê duyệt hay kết quả accuracy/F1 mới.

Trước khi chạy cần khóa snapshot phương pháp và đường đánh giá có version
phù hợp với thiết kế một người và evidence vắng nội dung. Giữ guard của
runner DEV để không dùng bộ mới sửa phương pháp rồi gọi là holdout.

Khi đo, tách kết quả nhãn, kiểm căn cứ và lỗi kỹ thuật. Luôn so với baseline
đoán toàn MET: **42/45 = 93,33%** trên nhãn tham chiếu này. Đây là baseline
tính từ phân bố nhãn, không phải kết quả P2. Bộ này chưa đo được khả năng
nhận ra CANNOT_ASSESS vì không có mẫu tham chiếu lớp đó; EXP001 cũng chỉ có
MET. Không suy một accuracy cao thành khả năng chấm đủ mọi tình huống.
