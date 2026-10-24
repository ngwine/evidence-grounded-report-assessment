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
`final_quote_or_citation`, `decision_rationale`, `decision_by`, `decided_at`
(`YYYY-MM-DD`). Với nhãn tương đồng dương, còn phải điền
`final_report_evidence_quote` và `final_source_evidence_quote` đúng nguyên văn.
Với dòng hai người đồng ý **cả nhãn lẫn evidence**, có thể để `final_label`
trống: kết quả chung được dùng sau khi hai phiếu đã khóa. Nếu chỉ nhãn giống
nhưng quote/citation hoặc đoạn evidence khác nhau, vẫn phải phân xử. Mọi thay
đổi so với kết quả chung phải ghi đủ ba trường quyết định.
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
item_id,quy_label,yen_label,final_label,final_verification_relation,final_evidence_span_ids,decision_rationale,decision_by,decided_at
```

`quy_label`/`yen_label` có thể để trống hoặc chép đúng từ phiếu độc lập;
`final_verification_relation` có thể để trống ở dòng đồng thuận. Nếu hai người
chọn cùng nhãn nhưng khác evidence span thì vẫn phải phân xử; với nhãn cuối
`MET`/`UNMET`, điền `final_evidence_span_ids` (các ID cách nhau bằng `;`).
Dòng bất đồng phải có nhãn, quan hệ evidence hợp lệ, lý do, người quyết định
và ngày. Dùng
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

## Freeze gold và đánh giá dự đoán

[`evaluation.py`](evaluation.py) bổ sung hai lệnh `freeze` và `evaluate`.
`freeze` gọi lại `workflow.summarize()` và chỉ nhận `COMPLETE`, hai phiếu riêng,
adjudication đã cung cấp, context đã khóa và **pack thực sự được phê duyệt cho
`GOLD_EVALUATION`** qua `research.governance.registry.validate_pack_manifest`.
Nó không cấp quyền dữ liệu, tự phê duyệt pack, sinh nhãn hay biến review của
ứng dụng thành gold độc lập. `MODEL_VISIBLE_REVIEW` và phiếu đã thấy dự đoán
không được dùng cho quy trình này. Các trường khai báo độc lập bên dưới là
cam kết của người phụ trách; chương trình kiểm tra cấu trúc, không xác minh
được hành vi của con người.

Chưa có gold human đủ điều kiện trong repository để công bố precision/F1 thực
nghiệm. Test của runner chỉ dùng nhãn và approval **synthetic tự viết trong
thư mục tạm**, minh họa phép tính và các trường hợp bị từ chối.

Mọi đầu vào, config, dự đoán và đầu ra phải ở dưới `var/`. Mỗi file tối đa
16 MiB, toàn bộ file trong pack tối đa 64 MiB và mỗi JSONL/cohort tối đa
100.000 dòng. Không nhận symlink, đường dẫn `..`, file ngoài pack, hardlink
giữa các đầu vào annotation/context, file thiếu hoặc checksum sai. Đầu ra cần
thư mục mới, không ghi đè; file có mode `0400`, thư mục `0500`. Đây là bảo vệ
khỏi ghi nhầm của owner, không phải chữ ký chống người có quyền sửa file.
Lỗi CLI chỉ in thông báo chung, không in tên file, ID hoặc excerpt.

### Hợp đồng pack và context (schema 1)

Pack phải thỏa toàn bộ governance hiện có, kể cả quyền nguồn, split và
checksum nguồn theo registry. `files` cần khai báo đúng checksum của cả hai
phiếu, adjudication và context; không thể thay bằng CSV cùng nội dung ở đường
dẫn khác. Người có thẩm quyền phê duyệt bổ sung `GOLD_EVALUATION` và descriptor
`gold_evaluation` dưới đây. Đây là **template mô tả**, không phải approval để
sao chép vào dữ liệu thật:

```json
{
  "gold_evaluation": {
    "schema_version": 1,
    "task": "similarity",
    "gold_version": "SET_AFTER_HUMAN_SEALING",
    "annotation_mode": "BLINDED_INDEPENDENT",
    "predictions_visible": false,
    "annotator_ids": {"a": "ANNOTATOR_A_ID", "b": "ANNOTATOR_B_ID"},
    "sealed_at": "YYYY-MM-DD",
    "approved_by": "ACTUAL_APPROVER",
    "approved_at": "YYYY-MM-DD",
    "inputs": {
      "annotator_a": "annotations_a",
      "annotator_b": "annotations_b",
      "adjudication": "adjudication",
      "context": "annotation_context"
    }
  }
}
```

`inputs` trỏ tới **logical key trong `files`**, không phải đường dẫn tùy ý.
Hai annotator ID phải khác nhau. `gold_version` thực tế phải ổn định; giá trị
`SET_AFTER_*`, `UNFROZEN`, `PENDING`, `PLACEHOLDER` bị từ chối. Cohort/split
và protocol phải khóa trước khi xem dự đoán; cần bao gồm cả negative/no-source
cases phù hợp với câu hỏi nghiên cứu. Đừng chỉ lấy các cặp đã được máy tìm ra
rồi suy ra recall trên toàn corpus.

Context là JSONL UTF-8, đúng một record cho mỗi ID của hai phiếu (kể cả dòng
sẽ `EXCLUDE`), không thêm/bớt hoặc trùng ID. Các key không khai báo bị từ chối.
Mỗi record có `schema_version: 1`, `item_id` bằng `pair_id`/`item_id` CSV,
`task`, `metadata`, `report_text` và trường riêng theo task:

| Task | `metadata` bắt buộc, tất cả là chuỗi không rỗng | Trường context riêng |
| --- | --- | --- |
| `similarity` | `report_id`, `report_version`, `source_id`, `source_version`, `report_chunk_id`, `source_chunk_id`, `source_name`, `report_page`, `source_page` | `source_text` |
| `assessment` | `report_id`, `report_version`, `rubric_id`, `rubric_version`, `checklist_id` | `evidence_spans`: danh sách `{ "span_id": "…", "start": 0, "end": 5 }` |

Với similarity, context là **đúng chunk/excerpt đã đưa cho hai người gán**;
`report_text`/`source_text` phải khớp CSV sau khi bỏ một dấu quote bảo vệ
spreadsheet theo quy tắc exporter hiện có. Version và ID của document/chunk
phải lấy từ provenance đã được duyệt, không suy đoán từ tên file. Nếu exporter
cắt excerpt, offset dưới đây tính từ đầu excerpt đó, không từ đầu PDF.

Evidence similarity được lưu thành interval `[start, end)` theo **Python Unicode
character index**, không phải byte hay UTF-16 offset. Quote phải là substring
nguyên văn và xuất hiện **đúng một lần**, kể cả các occurrence chồng nhau;
quote lặp bị từ chối để người adjudicate chọn evidence không mơ hồ. Không chọn
occurrence đầu tiên một cách ngầm định. Không trim quote trước khi tính offset.
Policy này là schema 1; không suy rộng ra document offset khi thiếu alignment.

Assessment context khóa toàn bộ `report_text` của version và các ID span có
offset hợp lệ trong report đó. ID evidence human phải nằm trong context của
đúng item. Các context dùng cùng report/version phải có cùng text; cùng span
ID trong report/version phải có cùng offset. `rubric_id`, `rubric_version` và
`checklist_id` phải khớp chính xác phiếu. Context không chứng minh rằng nội dung
span thỏa rubric: đó vẫn là quyết định của hai người gán và adjudicator.

Freeze lưu `gold.jsonl` chứa ID ổn định, metadata/version, label, evidence và
context riêng tư; metadata thêm `context_sha256` của canonical context record.
`EXCLUDE` không có trong gold đánh giá nhưng được đếm trong manifest và summary.
Cohort rỗng/toàn `EXCLUDE` bị từ chối, không tạo metric. Dòng consensus sử dụng
evidence đã thống nhất; dòng dispute/override sử dụng final evidence đã kiểm
tra, không suy evidence từ model.

### Run metadata và lệnh chạy

Cả hai lệnh yêu cầu config file đã khóa và JSON run metadata với **đúng** các
key `run_id`, `commit`, `config_sha256`, `seed`, `pipeline_version`, `task`,
`labels`. `commit` là 40 hoặc 64 ký tự hex thường, `seed` là integer,
`pipeline_version` ổn định và `config_sha256` phải bằng hash byte thật của
`--config`. `labels` phải đúng thứ tự:

- similarity: `["VERBATIM", "PARAPHRASE", "SUMMARY", "NONE"]`.
- assessment: `["MET", "UNMET", "CANNOT_ASSESS"]`.

Freeze và model run có thể có run metadata/config khác nhau; provenance ghi
rõ từng run. Không tự điền commit/seed/config giả để tạo kết quả. Ví dụ đường
dẫn sau chỉ dùng sau khi có input và approval thật, không tự tạo chúng:

```bash
.venv-research/bin/python -m research.gold_annotation.evaluation freeze \
  --task similarity --gold-version report-gold-v1 \
  --pack-manifest var/gold-input/approved-pack.json \
  --annotator-a var/gold-input/annotations_a.csv \
  --annotator-b var/gold-input/annotations_b.csv \
  --adjudication var/gold-input/adjudication.csv \
  --context var/gold-input/context.jsonl \
  --run-metadata var/gold-input/freeze-run.json \
  --config var/gold-input/freeze-config.json \
  --output-dir var/results/gold/report-gold-v1

.venv-research/bin/python -m research.gold_annotation.evaluation evaluate \
  --gold-dir var/results/gold/report-gold-v1 \
  --predictions var/model-run/predictions.jsonl \
  --run-metadata var/model-run/run.json --config var/model-run/config.json \
  --output-dir var/results/gold-evaluation/model-v1
```

### Prediction adapter cho hai pipeline

Prediction JSONL phải có **đúng toàn bộ tập ID của `gold.jsonl`**, mỗi ID đúng
một lần. Không inner join, bỏ dòng chưa chạy, tự thêm negative, sửa version hay
gộp checklist. Mỗi record có đúng các trường:

| Trường | Hợp đồng |
| --- | --- |
| `schema_version`, `item_id`, `task` | `1`, ID và task trùng gold |
| `metadata` | Object trùng **chính xác** metadata gold, bao gồm `context_sha256` |
| `run` | Object trùng chính xác run metadata của lần evaluate, khóa commit/config/seed/pipeline |
| `label` | Một label đã khai báo, hoặc JSON `null`/`"NOT_RUN"` để abstain |
| `score` | Số hữu hạn nếu có score thật; `null` nếu không có score; không chấp nhận boolean/NaN/Infinity |
| `evidence` | similarity: `{ "report_intervals": [[0, 5]], "source_intervals": [[2, 7]] }`; assessment: `{ "span_ids": ["span-1"] }` |

Abstention bắt buộc `score: null`, `evidence: {}`; không đổi thành `NONE` hoặc
`CANNOT_ASSESS`. Accepted prediction không có confidence vẫn có thể dùng
`score: null`; không chế tạo score. `NONE` có hai danh sách interval rỗng,
`CANNOT_ASSESS` có `span_ids: []`. Positive label được phép thiếu evidence
(danh sách rỗng), khi đó evidence recall bị giảm. Interval ngoài context,
span ID lạ/trùng, label lạ hoặc metadata sai đều làm hỏng cả lần đánh giá.

`similarity_annotation.pilot_pack` hiện xuất `model_predictions.jsonl` với
`pair_id`, `similarity_type`, `classification_status`, các heuristic/retrieval
score và provenance cặp; đó **chưa phải** format trên. Adapter riêng cần khóa
quy tắc chấp nhận status/label trong config trước khi xem gold, đổi `pair_id`
thành `item_id`, lấy đúng metadata/version từ provenance/context và đối chiếu
toàn bộ tập ID. Không dùng `provisional_similarity_type` như nhãn đã xác minh;
trạng thái chưa chạy/không đủ policy chấp nhận phải được xuất thành abstention.
`heuristic_score` chỉ được giữ như score heuristic thật, không gọi là xác suất
đã hiệu chuẩn. Exporter này không cung cấp alignment evidence hoàn chỉnh:
adapter chỉ điền interval khi có exact offset theo cùng chunk context; còn lại
để danh sách rỗng và chấp nhận evidence metric tương ứng. Không lấy evidence
hoặc label gold để điền prediction. Metadata gold có thể được sao chép cơ học
sau khi model predictions đã khóa, không dùng label/evidence để tuning.

Pipeline 2 cần adapter tương tự từ kết quả model theo checklist đã khóa,
giữ `CANNOT_ASSESS` là kết quả semantic và abstention là trạng thái không chạy/
không chấp nhận riêng. Chỉ dùng span ID thuộc report version/context đó;
không chuyển absence của span thành `UNMET`. Các review được nhập qua ứng dụng
sau khi thấy output máy chỉ là feedback vận hành, không phải phiếu human độc
lập cho `freeze`.

### Diễn giải metric và kiểm tra lại provenance

`metrics.json` chỉ chứa số tổng hợp và tên lớp, không có item ID, từng nhãn
thô, raw text hay excerpt. `evaluation-manifest.json` ghi hash gold/manifest,
pack hiện được duyệt, predictions, metrics, commit/config hash/seed/pipeline
và thời điểm chạy. Trước và sau khi tính, runner kiểm tra lại approval hiện
tại, toàn bộ file của pack, context/config/prediction hash; gold được dựng lại
từ phiếu đã duyệt và phải khớp byte/checksum. Thay gold **và** sửa hash trong
manifest cũng không thay được nhãn từ input được phê duyệt. Thay approval,
phiếu, context, config hoặc version cần một lần freeze/run mới; không sửa bundle
cũ. Cơ chế này không phải chữ ký xác thực danh tính người phê duyệt.

Classification gồm P/R/F1 và TP/FP/FN/support từng lớp, confusion matrix đầy đủ
với cột `ABSTAIN`, accuracy trên toàn gold, coverage = accepted/all, và
selective accuracy = correct/accepted. Abstention tạo FN cho lớp thật; không
được bỏ khỏi accuracy hay recall. Precision/recall có mẫu số 0 trả `null`.
F1 trả `null` chỉ khi cả predicted count lẫn gold support của lớp bằng 0;
trường hợp có support nhưng chỉ abstain có F1 = 0. `macro_f1` lấy trung bình
**toàn bộ lớp cấu hình**, lớp hoàn toàn vắng đóng góp 0, đồng thời công bố
`macro_f1_present_gold` trên các lớp có gold support và
`zero_gold_support_classes`. Pilot một lớp vì thế không bị hiểu nhầm là đã
kiểm tra đủ bốn/ba lớp.

Evidence được tính **riêng** với classification, micro trên mọi item gold,
kể cả abstention, không chỉ các prediction đúng label. Similarity lấy độ dài
union của các interval ký tự và phần giao chính xác, cộng report/source riêng
trong từng pair context; interval chồng nhau không đếm hai lần. Assessment
lấy giao/hợp theo span ID trong từng item context. Predicted evidence trên item
không có gold evidence vẫn tạo FP. Báo cáo ghi số item có evidence, tổng gold,
tổng predicted và overlap; P = overlap/predicted, R = overlap/gold,
F1 = 2×overlap/(predicted+gold). Không có evidence cả hai phía cho kết quả
`null`, không phải điểm hoàn hảo. Các cặp/checklist lặp context vẫn được đếm
theo item, không tự coi là các document độc lập.

Mẫu số chỉ là cohort pair/checklist đã chọn và được phê duyệt. Các số này không
đo full-corpus source-retrieval recall, tỷ lệ đạo văn hay chất lượng end-to-end
trên report chưa thấy. Review các cặp đã retrieve không đếm được positive mà
retrieval bỏ sót. Không dùng kết quả pilot để tuyên bố năng lực rộng hơn split,
nguồn và lớp thực sự có gold support.

Kiểm tra cục bộ (không cần mạng):

```bash
.venv-research/bin/python -m pytest research/tests/test_gold_evaluation.py -q
```
