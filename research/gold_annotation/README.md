# Gán nhãn độc lập và chốt gold data

Công cụ này kiểm tra hai phiếu CSV sau khi Quý và Yến gán nhãn độc lập. Nó
kiểm tra ID/version, nhãn, evidence bắt buộc, tính agreement và Cohen's kappa,
rồi kiểm tra quyết định adjudication. Công cụ không sinh nhãn hộ người gán và
không đọc file dự đoán của mô hình. Kết quả là các số đếm và SHA-256 của phiếu;
không có đoạn report, ID cặp hay bằng chứng trong file kết quả.

## Pipeline 1: similarity

Dùng `annotations_quy.csv`, `annotations_yen.csv`, `adjudication.csv` từ
[`pilot_pack`](../similarity_annotation/README.md). Hai phiếu phải giữ nguyên
`pair_id`, metadata và các cột văn bản. Mỗi người điền phiếu của mình trước khi
xem nhãn người kia hoặc `model_predictions.jsonl`.

Với `VERBATIM`, `PARAPHRASE`, `SUMMARY`, hai cột evidence quote phải là chuỗi
con **nguyên văn** của report/source trong cùng dòng. `NONE` và `UNSURE` vẫn
cần lý do. Mọi dòng cần `confidence` và `quote_or_citation`. Kiểm tra chuỗi con
chưa chứng minh nội dung gán nhãn là đúng; người gán phải đọc PDF và provenance.

Sau khi khóa hai phiếu, chạy:

```bash
.venv-research/bin/python -m research.gold_annotation.workflow \
  --task similarity \
  --annotator-a var/datasets/derived/similarity/desktop-pair-pilot-v1/annotations_quy.csv \
  --annotator-b var/datasets/derived/similarity/desktop-pair-pilot-v1/annotations_yen.csv \
  --adjudication var/datasets/derived/similarity/desktop-pair-pilot-v1/adjudication.csv \
  --output-dir var/results/gold-annotation/similarity-review-v1
```

Nếu bất đồng hoặc có `UNSURE`, adjudicator đọc lại nguồn và điền `final_label`
(`VERBATIM`, `PARAPHRASE`, `SUMMARY`, `NONE` hoặc `EXCLUDE`),
`decision_rationale`, `decision_by`, `decided_at` (`YYYY-MM-DD`). Với dòng hai
người đồng ý, có thể để `final_label` trống: nhãn chung được dùng sau khi hai
phiếu đã khóa. Mọi thay đổi so với nhãn chung phải ghi đủ ba trường quyết định.
`EXCLUDE` dùng cho cặp không thể phân xử; nó không nằm trong gold metric. Phiếu
còn bất đồng chưa xử lý cho kết quả `INCOMPLETE` và không xuất phân bố gold.

## Pipeline 2: report–rubric assessment

Tạo hai phiếu riêng cùng danh sách checklist từ **một** report version và rubric
version đã khóa. Header tối thiểu của mỗi phiếu:

```csv
item_id,report_id,report_version,rubric_id,rubric_version,checklist_id,label,verification_relation,evidence_span_ids,rationale
```

`item_id` cần ổn định và duy nhất cho một cặp report-version + rubric-version +
checklist. `label` là `MET`, `UNMET`, `CANNOT_ASSESS` hoặc `UNSURE` tạm thời;
`verification_relation` tương ứng là `SUPPORTED`, `CONTRADICTED`,
`INSUFFICIENT`. Khi `MET`/`UNMET`, điền `evidence_span_ids` (các ID span cụ thể,
cách nhau bằng dấu `;`). Với `CANNOT_ASSESS`, ghi rõ lý do không đủ bằng chứng.
Validator kiểm tra ID span có mặt, nhưng muốn xác nhận chúng có thật và thuộc
đúng version vẫn cần đối chiếu với dữ liệu provenance đã khóa. Không suy `UNMET`
từ việc không tìm thấy evidence.

Phiếu adjudication của Pipeline 2 có header:

```csv
item_id,quy_label,yen_label,final_label,final_verification_relation,decision_rationale,decision_by,decided_at
```

`quy_label`/`yen_label` có thể để trống hoặc chép đúng từ phiếu độc lập;
`final_verification_relation` có thể để trống ở dòng đồng thuận. Dòng bất đồng
phải có cả nhãn, quan hệ evidence hợp lệ, lý do, người quyết định và ngày. Dùng
`EXCLUDE` nếu sau khi đối chiếu vẫn chưa giải quyết được. Chạy lệnh trên với
`--task assessment` và đường dẫn đến ba phiếu Pipeline 2; đặt output dưới
`var/results/gold-annotation/`.

## Đọc kết quả

`annotation-summary.json` chứa số phiếu, phân bố nhãn từng người, confusion
matrix A×B, tỷ lệ đồng thuận, Cohen's kappa, số bất đồng còn lại và phân bố nhãn
cuối nếu đã phân xử hết. Kappa có giá trị `null` khi không có cặp đủ hai nhãn
hoặc hai người chỉ dùng đúng một nhãn chung (mẫu số bằng 0). `UNSURE` được đếm
riêng và không nằm trong mẫu số agreement.

Đây là thống kê **giữa người gán nhãn** trên pilot, chưa phải precision/F1 của
hệ thống. Việc đối chiếu với dự đoán máy chỉ thực hiện sau khi chốt gold,
kiểm tra quyền dữ liệu, cố định split và khóa cấu hình. Giữ phiếu, PDF và
`annotation-summary.json` dưới `var/` (Git bỏ qua); mỗi lượt ghi một thư mục
mới để không ghi đè bằng chứng cũ. Không mở TEST0 trong quy trình pilot này.
