# Đối chứng P2: một bước và hai bước

## Lượt DEV retrieval và chuẩn bị thực nghiệm chính ngày 08/11

Theo [protocol mới](../protocols/rq2-assessment/p2-main-study-v1.md), dùng
`retrieval_study.py` để so **không retrieval / LOCAL BM25** với cùng
model/verifier/scorer nhưng evidence pack khác nhau. Bộ 15 bài SEFORA đã
xem lỗi giờ là DEV cho những thay đổi mới, không đổi tên thành holdout.
Guard trong runner DEV cũ bên dưới vẫn giữ, không nới lặng lẽ.

Profile mới `context-one-step-v1.json` (và biến thể two-step riêng) thêm
`source_unit_policy: context_bundles_v1`. Mỗi unit giữ một source span liền
mạch, tối đa 1.800 ký tự, không cắt ở dấu câu của initials; span/chunk dài
vẫn bị chia theo budget, không được gọi là luôn giữ nguyên toàn bộ paragraph.
Prompt yêu cầu đúng tác giả/người được trích và nguồn quotation; đây là
thay đổi cần đo, không bảo đảm chất lượng chỉ bằng tests/prompt. Profile app
và mode cũ không đổi khi không khai setting mới.

Runner prepare khóa nguồn/config/code/prompt/schema trước call; lưu mọi
kết quả riêng, không tự retry call dở. Nhánh semantic GRAPH ghi rõ
`NOT_IMPLEMENTED_NOT_RUN`; không thêm dòng điểm bằng structure/term PPR.
Đường chạy DEV hiện chỉ BM25, chưa phải toàn bộ hybrid/GRAPH của đề cương.

`retrieval_study_analysis.py` kiểm proof geometry và độ phủ vị trí evidence
tham chiếu của từng pack; đó chưa phải semantic precision/support rate.
`evidence_review.py` xuất phiếu người kiểm trên **mọi quyết định MET/UNMET**,
che tên phương pháp, mapping riêng, rating/người kiểm để trống. CA và lỗi
kỹ thuật đếm riêng; không chọn chỉ mục bất đồng để suy tỷ lệ toàn bộ.

```sh
.venv-research/bin/python -m research.p2_comparison.evidence_review prepare \
  --prepared-dir var/paper/p2-main-study-preparation-2026-11-08/context-retrieval-dev-prepared-v1 \
  --predictions var/paper/p2-main-study-preparation-2026-11-08/context-retrieval-dev-run-v1/all-methods-predictions.json \
  --output-dir var/paper/p2-main-study-preparation-2026-11-08/semantic-review-v1
```

Sau khi người thực sự kiểm trả file CSV riêng, dùng subcommand `summarize`
với `--review-dir`, `--completed-csv`, `--output-dir` mới. Không có phiếu
thật thì chỉ có trạng thái pending, không tự tạo tỷ lệ semantic support.

## Bộ tham chiếu một người — đường đánh giá thăm dò riêng

`single_reference.py` nhận yêu cầu tường minh chạy cohort thực, một phiếu
đã kiểm cùng canonical của chính phiếu đó, rubric runtime và protocol.
Nó lưu nhãn tham chiếu riêng, khóa toàn bộ bài/evidence pack/cấu hình/mã
trước request đầu tiên, rồi truyền **chỉ checklist và pack** cho verifier.
Không yêu cầu phiếu thứ hai hoặc nới guard DEV/gold-v1 hiện có.

```sh
.venv-research/bin/python -m research.p2_comparison.single_reference prepare \
  --packet-dir var/paper/p2-annotation-2026-11-05/v2 \
  --workbook path/to/source-exact-return.xlsx \
  --canonical-reference path/to/canonical.json \
  --rubric path/to/authored-rubric.json \
  --protocol path/to/protocol.json --authorization path/to/user-request.json \
  --output-dir var/paper/new-single-reference/prepared

.venv-research/bin/python -m research.p2_comparison.single_reference run \
  --prepared-dir var/paper/new-single-reference/prepared \
  --output-dir var/paper/new-single-reference/run --allow-real-model
```

Mỗi checklist có file kết quả riêng và marker bắt đầu. Chạy tiếp cùng thư
mục bỏ qua kết quả đã lưu; một request đã bắt đầu nhưng chưa có kết quả sẽ
bị từ chối tự retry để giữ lần chạy đầu. Không chỉnh các input/method đã
khóa hoặc xóa marker để thay một dự đoán không mong muốn.

`single_reference_metrics.py` đối chiếu đủ từng item/version. Technical
abstention để nhãn `null`, vẫn tính vào mẫu số đầy đủ; coverage và tỷ lệ
khớp chỉ trên quyết định được chấp nhận được lưu riêng. Báo baseline MET,
F1 trên lớp có mẫu và các lớp chưa thể đo; không tự tính IAA hay gọi đây
là gold đồng thuận.

`single_reference_evidence.py` kiểm source spans/offset về body gốc và
overlap vị trí người gán. Giữ DOCUMENT_ABSENCE tách khỏi span, không xem
evidence rỗng thành chứng minh vắng nội dung. Các kiểm tra này không tự
chứng minh bằng chứng hỗ trợ đúng ý nghĩa của checklist.

Lượt dùng thiết kế này:
[SEFORA 15 bài ngày 07/11](../../docs/benchmarks/sefora-p2-single-reference-result-2026-11-07.md).

## Chuẩn bị DEV trong lúc chờ nhãn

Công cụ này chuẩn bị một bộ evidence chung **trước khi gọi model**, dành cho
ca tự soạn hoặc DEV đã xem. Nó không nhận phiếu người gán/gold, không tự duyệt
dataset hoặc tính accuracy. Bộ 15 bài mới đang chờ gán nhãn được chặn theo
đường dẫn và hash body trong metadata packet; kể cả copy body sang tên khác
cũng bị chặn. Không chạy công cụ này trên bộ đó để sửa phương pháp.

## Hai cấu hình được đối chiếu

- [`one-step.json`](../configs/p2-comparison/one-step.json): một lượt đọc pack
  chung rồi đề xuất relation, rationale và citation.
- [`two-step.json`](../configs/p2-comparison/two-step.json): chọn source units
  từ pack chung, sau đó xác minh chỉ trên các unit đã chọn.

Model/digest, parser/chunker, BM25/context policy, seed, giới hạn mỗi lượt và
**tối đa ba citation mỗi requirement** đều bằng nhau. Runner từ chối cặp
config khác nhau ngoài `citation_audit` và định danh lần chạy.

Đây là so sánh hai kiến trúc verifier trên **cùng evidence đầu vào**, không
phải khẳng định chúng chọn cùng các câu cuối cùng. Những unit được chọn khác
nhau là một phần hành vi cần đo. Thay cả selector/prompt/luồng xác minh không
cô lập được hiệu quả riêng của auditor. Nếu muốn kiểm riêng auditor, cần một
protocol khác dùng cố định cùng tập unit đã chọn.

Giới hạn là **cùng budget mỗi lượt**, không phải cùng tổng compute: phương
pháp hai bước dùng tối đa hai lượt. Output ghi actual chat calls, prompt/output
token telemetry và thời gian; telemetry thiếu được ghi rõ, không bù số giả.
Thứ tự thực thi hai phương pháp được chọn xác định từ hash report và seed,
ghi trong manifest. Máy và trạng thái cache vẫn có thể ảnh hưởng thời gian;
không diễn giải một lần chạy thành thí nghiệm latency có kiểm soát.

## Chuẩn bị trước, không gọi model

Ví dụ dùng ca tổng hợp có sẵn từ smoke test cũ:

```sh
.venv-research/bin/python -m research.p2_comparison.runner prepare \
  --report var/quality/p2-llm-v2-2026-11-04/smoke-v3/inputs/unnamed-specific-experience.txt \
  --rubric var/quality/p2-llm-v2-2026-11-04/smoke-v3/inputs/rubric.json \
  --cohort AUTHOR_WRITTEN_SYNTHETIC \
  --output-dir var/paper/p2-comparison-dev/new-preparation \
  --prepare-only
```

Với ca đã dùng phát triển, dùng `--cohort PREVIOUSLY_INSPECTED_DEV`. Cohort
là lời khai của người gọi, không chứng nhận đó là tập độc lập. Các output luôn
nằm dưới `var/`, từ chối ghi đè và không có nhãn kỳ vọng.

Parser và retrieval chạy một lần. `common-evidence.json` giữ canonical
chunk, source spans, Evidence Pack và source-unit catalog của từng checklist.
`preparation-manifest.json` giữ hash input/config/code, các pack chung, thứ tự
thực thi và giới hạn claim. Code liên quan được chụp riêng trong `code-snapshot/`.

Hiện chỉ hỗ trợ checklist LOCAL, BM25 và bounded short-report context; Dense,
reranker hoặc GRAPH bị từ chối thay vì đổi phương pháp ngầm. Đọc hết các
parsed chunks không chứng minh đã giữ đủ mọi text/ảnh của bản gốc.

## Chạy DEV khi chủ động yêu cầu

```sh
.venv-research/bin/python -m research.p2_comparison.runner run-development \
  --prepared-dir var/paper/p2-comparison-dev/new-preparation \
  --output-dir var/paper/p2-comparison-dev/new-replay \
  --allow-real-model
```

Không có `--allow-real-model` thì runner không tạo hoặc gọi model. Chạy thật
dùng service local đã cài và digest đã khóa; không tải model hoặc đổi dịch vụ.
Các bound từng request/max checklist của verifier vẫn được áp dụng. Đây là
runner DEV đồng bộ, không phải thay thế worker có hard wall deadline của app.

Mỗi phương pháp nhận bản sao cùng checklist/pack đã freeze. Runner kiểm lại
catalog, hash trước/sau và từ chối nếu verifier thay input. Method output có
assessment report chuẩn, qua kiểm tra schema/proof/provenance và phép tính
điểm bằng code. Điểm đề xuất đó không phải đối chiếu điểm giảng viên.

Trong kết quả đối chứng:

- `VALIDATED` + CANNOT_ASSESS là quyết định semantic của model.
- `WITHHELD` do timeout/schema/proof/budget là **technical abstention**,
  `accepted_label: null`; không biến thành CA đúng để làm đẹp metric.
- Hash pack/catalog chung được đối chiếu giữa hai phương pháp.
- Không có accuracy/F1 vì runner không đọc gold; kết quả DEV không tự trở
  thành thí nghiệm nghiên cứu độc lập hoặc approved pack.

## Sau khi nhận phiếu

Chốt guideline, nhãn và evidence đúng version, xử lý bất đồng/exposure rồi
hoàn thiện pack approval, config và split trước khi freeze/evaluate theo
[`gold_annotation`](../gold_annotation/README.md). Cơ chế phê duyệt hiện có
không bị bypass bởi runner DEV này. Nhãn UNMET do kiểm toàn văn và xác nhận
vắng nội dung cần evidence contract riêng; không tạo quote/span giả cho nó.

Kiểm tra phần mềm không gọi model:

```sh
.venv-research/bin/python -m pytest -q research/tests/test_p2_comparison.py
```
