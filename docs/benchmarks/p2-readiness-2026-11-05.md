# Chuẩn bị P2 trong lúc chờ hai phiếu mới — 05/11/2026

> Cập nhật 07/11: đã nhận phiếu Yến và người phụ trách chọn dùng một người
> gán nhãn, không làm phiếu Quý. Xem
> [hồ sơ nhận phiếu và thiết kế cập nhật](sefora-p2-single-annotator-intake-2026-11-07.md).
> Nội dung bên dưới ghi lại trạng thái chuẩn bị ngày 05/11; không coi là yêu
> cầu bổ sung người gán cho thiết kế một người hiện tại.

Đợt này chuẩn bị đường nhận phiếu, bằng chứng vắng mặt và phép so sánh
verifier. Không chạy P2 trên 15 bài Class_2 đang gán, không tạo nhãn người
hoặc thêm số liệu chất lượng P2 vào bảng kết quả bài báo.

## Nhận Excel và tạo bảng cần đối chiếu

Module `research/gold_annotation/p2_workbook_intake.py` nhận đúng hai file
XLSX và packet gốc. Nó kiểm metadata/checksum, các ô định danh bị sửa,
nhãn/căn cứ, paragraph và quote nguyên văn. File trả về được lưu riêng,
read-only và có receipts; các nhãn cuối/phân xử không được tự điền.

Phiếu trống, UNSURE và khai báo phương thức/đã xem dữ liệu gì còn thiếu
được ghi riêng. `CANNOT_ASSESS` không bị dùng thay cho việc người gán chưa
chắc, và lỗi nhập liệu không được tính thành dự đoán model.

Dependency tùy chọn: `research/requirements-annotation.txt`. Hướng dẫn và
lệnh nhận file ở [gold annotation README](../../research/gold_annotation/README.md).

Đã thử nhận hai workbook gốc **còn trống** tại
`var/quality/p2-waiting-2026-11-05/blank-template-preflight/`:
45 mục mỗi người được giữ trống, 0 mục có hai nhãn xác định, trạng thái
`INCOMPLETE`, không freeze gold. Đây không phải hai phiếu người gán đã gửi lại.

## Bằng chứng khi thành phần bắt buộc vắng mặt

`research/gold_annotation/assessment_evidence.py` giữ `DOCUMENT_ABSENCE`
tách khỏi các span có quote. Record cần đúng report/version/hash body,
phạm vi ENTIRE_CAPTURED_TEXT, xác nhận đã đọc hết và toàn bộ paragraph,
cùng lý do. Kiểm này xác minh hồ sơ/phạm vi được khai, không tự chứng minh
thành phần thực sự vắng mặt hoặc suy thành thiếu trong PDF gốc/ảnh.

`SPAN_SET` có quote và offset nguồn; `INSUFFICIENT_INPUT` và `UNRESOLVED`
giữ lý do riêng. Không tạo span giả cho vắng nội dung; không tính bằng
chứng rỗng thành một kết quả evidence hoàn hảo. Chỉ số overlap ký tự và
khớp phạm vi vắng nội dung được tính riêng, không gọi là semantic accuracy.

Đây là evidence contract bổ sung. Gold-v1 hiện hành không bị nới điều kiện,
không tự nhận record vắng nội dung. Bước chuyển sang gold có version và
approval cho bộ mới vẫn cần xử lý sau khi nhận/chốt các quyết định người gán.

## So sánh một bước và hai bước trên cùng đầu vào

[Runner và protocol](../../research/p2_comparison/README.md) tạo một
Evidence Pack và source-unit catalog chung trước khi gọi model. Hai config
tại `research/configs/p2-comparison/` khớp model/digest, seed, parser/context,
budget mỗi request và tối đa ba citations mỗi requirement. Chúng chỉ khác
luồng `citation_audit` và định danh run.

Optional policy `max_citations_per_requirement` trong verifier cho phép
chuẩn hóa giới hạn giữa hai phương pháp. Khi không khai báo, các profile
đã chạy vẫn giữ prompt/schema/policy mặc định trước đây.

Runner ghi hash pack/catalog trước và sau, các call/token/thời gian thực
tế và report qua contract/schema hiện hành. Nó chỉ chạy DEV khi có yêu cầu
tường minh; chuẩn bị không gọi model. Đường dẫn và hash body của 15 bài mới
được chặn trong công cụ DEV này, kể cả copy body sang tên file khác.

Hai bước có thể dùng hai request, nên đây là **cùng budget mỗi request**,
không phải cùng tổng compute. Việc chúng chọn unit khác nhau là hành vi của
hai kiến trúc, không phải so sánh riêng tác dụng auditor trên cùng unit cuối.
Không coi latency một lượt là thí nghiệm tài nguyên có kiểm soát.

Timeout/schema/proof failures được ghi technical abstention với
`accepted_label: null`; CA qua xác minh là quyết định semantic riêng.
Runner không đọc gold và không tự tính accuracy/F1 từ ca thử phần mềm.

Đã chạy model thật trên **một ca tự soạn cũ** tại
`var/quality/p2-waiting-2026-11-05/comparison-real-smoke/`: cả hai phương
pháp nhận cùng pack/catalog và trả MET qua contract, không technical
abstention. Ghi nhận 1 call cho one-step, 2 call cho two-step và telemetry
token riêng. Đây là xác nhận đường chạy, không phải kết quả đánh giá chất
lượng hay kết luận về latency giữa hai kiến trúc.

Kiểm tra research/backend của đợt này: **1.288 passed, 21 skipped** khi
bật dependency Excel tùy chọn. Lint và `git diff --check` đạt. Các kiểm tra
bằng chứng/Excel dùng fixture tự soạn; phiếu thật chưa được điền hộ.

## Đồng bộ bài báo

Sect. 3.3 đã mô tả thêm verifier local một bước/hai bước, source-unit IDs,
kiểm provenance và giới hạn ngữ nghĩa. Bản DOCX được tạo lại từ Markdown.
Phần Experimental Design trở đi giữ nguyên bytes; nội dung 13 bảng Word
khớp bản trước. Không thêm số P2 9/10 vào abstract, Results hoặc kết luận.

Backups và xác minh ở `var/paper/p2-paper-method-sync-2026-11-05/`.

## Khi hai phiếu được trả về

1. Nhận và lưu bản riêng; chạy intake, xử lý lỗi/UNSURE/bất đồng và khai báo.
2. Chốt phạm vi checklist, bằng chứng, split và hồ sơ pack. Không ép ba lớp
   đều có mẫu nếu nhãn thực tế không như vậy.
3. Hoàn thiện đường freeze/evaluate có version phù hợp với các loại evidence
   thực có trong phiếu. Đo nhãn, evidence và lỗi kỹ thuật riêng.
4. Chỉ chạy đánh giá sau khi phương pháp được khóa; những lượt dùng sửa
   phương pháp giữ DEV, không đổi tên thành holdout.
