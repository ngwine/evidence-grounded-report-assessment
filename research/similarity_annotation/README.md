# Pilot gán nhãn cặp đoạn tương đồng

Đây là bộ **ứng viên để con người gán nhãn**, không phải ground truth có sẵn.
Pilot Desktop hiện lấy một báo cáo môn AI và ba PDF đối chứng do nhóm cung cấp.
Các cặp được lấy từ Top-3 của runner, nên mẫu thiên về những gì hệ thống tìm
được; nó **không** đo được retrieval recall, không chứng minh rằng các nguồn
khác không chứa đoạn liên quan, và không đại diện cho mọi báo cáo sinh viên.
Nhiều cặp cùng trỏ đến một chunk sách Sudoku: chúng không độc lập thống kê.

## Bộ pilot Desktop đã tạo

Thư mục local (Git bỏ qua):
`var/datasets/derived/similarity/desktop-pair-pilot-v1/`.

- `annotations_quy.csv` và `annotations_yen.csv`: hai phiếu độc lập, đã có
  đoạn report/nguồn và vị trí trang nhưng **mọi ô nhãn đều trống**. Mỗi người
  chỉ sửa phiếu của mình.
- `pairs.jsonl`: văn bản cặp đoạn và provenance gốc cho việc kiểm tra lại.
- `model_predictions.jsonl`: nhãn/điểm dự đoán của máy, **không mở trước khi
  khóa hai phiếu độc lập**.
- `adjudication.csv`: phiếu giải quyết bất đồng sau vòng độc lập.
- `pack-manifest.json`: run ID, checksum đầu vào/đầu ra và trạng thái quyền
  `PENDING`.

Bộ hiện tại có 40 cặp từ 20 đoạn report, gồm cả tám cặp đã bị máy nghi là
paraphrase/summary; nguồn gồm 30 cặp từ PDF sách AI, 6 từ Go và 4 từ Sudoku.
Các cặp này được chọn để chẩn đoán lỗi, **không cân bằng theo nhãn thật**.
Trang đầu chứa thông tin tác giả/email được loại, trừ đoạn abstract đã được
kiểm tra; phần tên người trong mục đóng góp được cắt khỏi excerpt. Vẫn cần
người kiểm tra PII và quyền dữ liệu trước khi chia sẻ ra ngoài nhóm.

Pull repo **không** tải được bộ phiếu này vì `var/` bị Git bỏ qua. Nếu hai
người làm trên máy khác nhau, sau khi xác nhận quyền truy cập và kiểm tra PII,
chuyển riêng `annotations_yen.csv` cùng quyền xem các PDF cần thiết cho Yến
qua kênh nội bộ được phép. Không gửi `model_predictions.jsonl` hoặc phiếu của
Quý trước khi hai người khóa nhãn độc lập; không commit dữ liệu gốc vào Git.

Nếu cần tạo lại từ đúng run này, chọn một thư mục output **mới** vì công cụ
không ghi đè phiếu đã tạo:

```bash
.venv-research/bin/python -m research.similarity_annotation.pilot_pack \
  --similarity-report var/results/core-mvp/desktop-test-all-evidence-gate-v2/similarity-report.json \
  --run-manifest var/results/core-mvp/desktop-test-all-evidence-gate-v2/run-manifest.json \
  --output-dir var/datasets/derived/similarity/desktop-pair-pilot-v2 \
  --target-pairs 40 \
  --safe-page-one-chunk-id chk-15469062fadbe3ef1993956b875fc2a091273b74b3cd2897fa663d4d89ec1980
```

## Bốn nhãn ở cấp cặp đoạn

| Nhãn | Khi dùng | Không dùng khi |
| --- | --- | --- |
| `VERBATIM` | Có một đoạn chữ đủ đặc thù được dùng lại gần nguyên văn; hai vị trí evidence phải chỉ được phần dùng lại. | Chỉ trùng thuật ngữ, tên thuật toán, công thức chuẩn hoặc câu rất ngắn/phổ biến. |
| `PARAPHRASE` | Cùng một ý/khẳng định hoặc các chi tiết cụ thể được trình bày lại bằng từ ngữ/cấu trúc khác. | Chỉ cùng chủ đề nhưng mô tả phương pháp, dữ kiện hoặc kết luận khác nhau. |
| `SUMMARY` | Đoạn report cô đọng nhiều ý/chi tiết cụ thể trong đoạn nguồn mà vẫn giữ nội dung chính. | Chỉ vì đoạn report ngắn hơn đoạn nguồn; độ dài không tự chứng minh tóm tắt. |
| `NONE` | Không có bằng chứng dùng lại nội dung ở cặp này; gồm cả hard negative cùng chủ đề. | Chưa đọc đủ ngữ cảnh để quyết định. Dùng `UNSURE` tạm thời và ghi lý do. |

`UNSURE` là trạng thái gán nhãn tạm, không phải lớp thứ năm để tính F1. Nếu
một cặp có cả đoạn chép gần nguyên văn và đoạn diễn giải, chọn nhãn cho **span
được chỉ ra**; nếu không thể tách span rõ, ghi `UNSURE` để adjudication. Không
gán nhãn dựa trên điểm Dense/Cross-Encoder hay nhãn máy dự đoán.

## Quy trình hai người

1. Quý và Yến mở **phiếu riêng**; không mở `model_predictions.jsonl` và không
   xem phiếu của nhau trước khi khóa vòng gán nhãn độc lập. Chỉ làm trên máy
   được phép truy cập dữ liệu; không đưa đoạn report hoặc PDF vào Git, dịch vụ
   bên ngoài hay bài báo khi chưa có quyền và kiểm tra PII.
2. Với mỗi cặp, đọc cả hai đoạn và trang nguồn. Điền `label`; với ba nhãn
   dương, điền `report_evidence_quote` và `source_evidence_quote` bằng đoạn
   chữ chính xác trong hai ô văn bản, cùng một câu `rationale`. Với `NONE`, ghi ngắn vì sao
   cùng chủ đề chưa đủ, hoặc khác phương pháp/chi tiết ở đâu.
   Ghi `quote_or_citation` là `YES`, `NO` hoặc `UNSURE`; ghi `confidence` là
   `HIGH`, `MEDIUM` hoặc `LOW`. Hai trường này không thay thế bằng chứng.
3. Đánh dấu trích dẫn/ngoặc kép nếu có. Nhãn tương đồng **không phải kết luận
   đạo văn**; cách sử dụng nguồn hợp lệ là một đánh giá khác của giảng viên.
4. Sau khi cả hai hoàn tất, đối chiếu bất đồng, đọc lại PDF và ghi nhãn cuối
   cùng vào phiếu adjudication kèm `decision_rationale`, `decision_by` và
   `decided_at` (ngày ISO `YYYY-MM-DD`). Không tự
   điền nhãn cuối từ dự đoán của hệ thống. Cặp còn mơ hồ được loại khỏi metric
   chính và ghi lý do loại.
5. Khóa phiên bản phiếu và manifest trước khi tính metric. Báo riêng số cặp
   từng lớp, tỷ lệ đồng thuận, confusion matrix và precision/recall/F1 từng
   lớp; không gọi kết quả trên một report là kết quả tổng quát của khóa luận.

Sau khi hai phiếu đã khóa, dùng
[`gold_annotation`](../gold_annotation/README.md) để kiểm tra phiếu, đo agreement
và xác nhận adjudication. Precision/recall/F1 của mô hình chỉ được tính sau
khi gold và quyền dùng dữ liệu đã được chốt.

## Ranh giới sử dụng

Các đoạn trích và phiếu có thể chứa văn bản sinh viên hoặc tài liệu có bản
quyền. Chúng phải nằm dưới `var/` (Git bỏ qua) và chỉ phục vụ gán nhãn nội bộ.
Manifest của pilot giữ `PENDING` cho quyền dữ liệu; việc tạo file **không** là
chấp thuận dùng cho huấn luyện, thí nghiệm công bố hoặc phát hành. Nguồn có
thể có tên người trong nội dung công khai; người review phải kiểm tra lần cuối
trước khi chia sẻ. Phiếu không bảo đảm có đủ bốn lớp vì nhãn chỉ được biết sau
khi hai người gán và adjudicate.

PAN-PC-11 hiện chỉ có qrels truy xuất nguồn cho pilot này, không cung cấp đáp
án bốn nhãn report–source của bộ Desktop. DEV0 không dùng để chỉnh mãi một
ngưỡng; DEV1/TEST0 chỉ chạy khi hoàn thành governance và khóa split theo
[`RQ1 protocol`](../protocols/rq1-similarity/README.md).
