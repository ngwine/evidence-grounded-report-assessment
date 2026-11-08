# Hướng dẫn kiểm chứng P2 bằng QASPER và chuẩn bị SEFORA

Cập nhật 30/10/2026. Hướng dẫn dùng các file đã có trên máy `/Users/ngwii/KLTN`.
Không cần tải lại dữ liệu. **Lượt QASPER xác nhận đã hoàn tất ngày 30/10**:
646 câu đủ điều kiện, toàn bộ aggregate metrics và byte của `metrics.json`
khớp lượt cũ. [Bảng đối chiếu đã kiểm](../../var/paper/p2-preparation-2026-10-30/qasper/new-run-comparison-v1.json).
**Cập nhật 02/11:** đã [nhận và đối chiếu hai phiếu SEFORA](../benchmarks/sefora-p2-return-review-2026-11-02.md),
mỗi phiếu 60 mục. Còn 25 UNSURE, mapping/checklist và phân xử evidence cần
hoàn tất; chưa chạy model SEFORA. Mở
[bảng phân xử mới](../../var/paper/p2-review-2026-11-02/v1/DOC_TRUOC.md)
để tiếp tục; các mô tả phiếu trống bên dưới là trạng thái packet ngày 30/10.
Các lệnh bên dưới được giữ để tái lập; thư mục `...revalidation-20261030-v1`
đã có kết quả nên không chạy lại với tên này.

Hai việc trả lời hai câu hỏi khác nhau:

| Việc | Câu hỏi cần trả lời | Đầu ra |
|---|---|---|
| Xác nhận lại QASPER | P2 tìm được đoạn bằng chứng đúng ở mức nào? Kết quả cũ có giữ được trên bản code đã khóa không? | Metrics mới, manifest và bảng so sánh với lượt cũ. |
| Chuẩn bị 10 bài SEFORA | Có thể biến rubric gốc thành yêu cầu kiểm chứng được không? Báo cáo đáp ứng yêu cầu dựa trên đoạn nào? | Bảng kiểm rubric, nhãn và bằng chứng do người kiểm; sau đó mới đo P2. |

QASPER không kiểm phần chấm rubric. SEFORA có điểm và feedback người chấm,
nhưng chưa có đầy đủ nhãn checklist–bằng chứng theo schema của project.

## A. Xác nhận lại QASPER

### 1. Hiểu đầu vào và đáp án

Mỗi câu hỏi QASPER đi cùng một paper. Hệ thống chỉ tìm các đoạn trong chính
paper đó; nhãn người chỉ ra đoạn nào là bằng chứng đúng. Runner dùng câu hỏi
để truy xuất, giữ nhãn bằng chứng riêng để tính metric.

Đầu vào trên máy:
`var/datasets/raw/qasper-v0.3/qasper-dev-v0.3.json`.
Lượt cũ gồm 281 paper, 1.005 câu hỏi, trong đó 646 câu đủ điều kiện ánh xạ
bằng chứng sang đoạn văn; 359 câu bị loại theo protocol. Giữ nguyên quy tắc
loại, không thay tập câu hỏi để kết quả đẹp hơn.

Đường dẫn kết quả cũ:
`research/results/rq2-qasper/local-paragraph-dev-v03-all281-s20261018-standalone-fix/`.

### 2. Chạy kiểm tra trước, chưa nạp model

Mở terminal trong VS Code và chạy:

```bash
cd /Users/ngwii/KLTN

.venv-research/bin/python \
  var/paper/p2-preparation-2026-10-30/qasper/launch_qasper.py \
  --check-only \
  --output-dir /Users/ngwii/KLTN/var/results/rq2-qasper/local-paragraph-dev-v03-revalidation-20261030-v1
```

Script đã được kiểm với dữ liệu hiện có. Nó kiểm checksum raw/archive,
model E5 đúng revision trong cache, worktree sạch tại commit `9b9721d`, và
thư mục kết quả chưa tồn tại. `model_inference_run: false` và
`output_created: false` là trạng thái đúng của lệnh kiểm này.

Nếu báo output đã có, giữ nó lại và đổi hậu tố `v1` thành `v2` ở **mọi lệnh
liên quan tới lượt mới**. Nếu báo sai checksum, thiếu cache hoặc worktree bị
thay đổi, sửa đúng nguyên nhân; không bỏ điều kiện kiểm.

Lưu ý provenance: benchmark/BM25/Dense hiện khớp hash của lượt chuẩn cũ,
nhưng source RRF đã thay đổi. Vì vậy đây là **xác nhận lại aggregate trên
implementation hiện tại đã khóa**, chưa phải chạy lại nguyên xi mọi byte
source của tháng 10. So metrics bằng nhau cũng chưa chứng minh mọi thứ hạng
theo câu hỏi giống nhau.

### 3. Chạy model thật

Chạy cùng lệnh nhưng bỏ `--check-only`:

```bash
.venv-research/bin/python \
  var/paper/p2-preparation-2026-10-30/qasper/launch_qasper.py \
  --output-dir /Users/ngwii/KLTN/var/results/rq2-qasper/local-paragraph-dev-v03-revalidation-20261030-v1
```

Helper tự chạy CLI từ worktree sạch; dùng E5 CPU đã cache, chế độ offline,
seed `20261018`, đủ 281 paper và ba phương pháp BM25 / E5 / RRF. Giữ terminal
cho đến khi lệnh kết thúc. Không phải thao tác trên màn hình web demo.

Kết quả được ghi vào thư mục mới: `metrics.json`, `run_manifest.json`,
`launch-record.json`, `launch-completion.json`. Helper từ chối output có sẵn
**trước khi nạp model** vì writer của runner gốc có thể ghi đè file.
Một attempt bị lỗi vẫn được giữ; dùng thư mục khác cho lần sau.

### 4. So với kết quả cũ

Sau khi lượt chạy kết thúc thành công:

```bash
.venv-research/bin/python \
  var/paper/p2-preparation-2026-10-30/qasper/compare_qasper.py \
  --baseline /Users/ngwii/KLTN/research/results/rq2-qasper/local-paragraph-dev-v03-all281-s20261018-standalone-fix \
  --candidate /Users/ngwii/KLTN/var/results/rq2-qasper/local-paragraph-dev-v03-revalidation-20261030-v1 \
  --output /Users/ngwii/KLTN/var/paper/p2-preparation-2026-10-30/qasper/new-run-comparison-v1.json
```

Comparator kiểm checksum artifact và sự trùng khớp của dữ liệu, cấu hình,
model, phạm vi và số câu được chấm trước khi tính chênh lệch. Nó giữ rõ các
code hash khác nhau, không tự gọi hai lượt là cùng implementation.

Bảng cũ dùng để đối chiếu, **không phải kết quả vừa chạy lại**:

| Phương pháp | Hit@10 | Complete@10 |
|---|---:|---:|
| BM25 | 76,93% | 61,76% |
| E5 Dense | 86,69% | 74,30% |
| BM25 + E5 + RRF | 87,15% | 72,45% |

`Hit@10` là tìm ít nhất một đoạn đúng trong 10 đoạn đầu. `Complete@10` là
tìm đủ bộ bằng chứng của ít nhất một annotation hợp lệ. Cả hai không phải
độ chính xác chấm điểm. Nếu có chênh lệch, xem nguồn/config/code rồi ghi lại;
không sửa con số cũ hoặc chọn chỉ những metric tăng.

### 5. Khi nào dùng vào bài báo?

Viết dưới phạm vi **đánh giá sơ bộ thành phần truy xuất bằng chứng LOCAL**.
Ghi số câu được chấm/loại, cách ánh xạ evidence, metric, model và code snapshot.
Đây là DEV đã xem; chưa phải holdout hoặc so sánh LOCAL–GRAPH.

Hồ sơ cũ còn `team_dataset_approval=NOT_RECORDED`; helper giữ nguyên thông
tin này, không tạo phê duyệt thay người phụ trách. Cần hoàn thiện hồ sơ pack
và review nguồn trước khi nâng thành thực nghiệm chính của bài. Hướng dẫn
không tự thay phạm vi hay các bảng PAN đang có.

## B. Chuẩn bị nhóm SEFORA nhỏ

### 1. Mở bộ đã chuẩn bị

Bắt đầu từ [README của packet](../../var/paper/p2-preparation-2026-10-30/sefora/README_VI.md).
Đã chọn 10 mã bài cùng assignment và cùng một rubric, theo quy tắc seed/hash
được ghi trước khi đọc nội dung/giá trị điểm. Không chọn theo điểm cao hay
thấp. Các phiên bản hiện gồm 4 Final, 5 Revision và 1 Initial; chưa được
coi như các bài hoàn thiện cùng một stage.

Mở hai file cạnh nhau:

- [Bài đầu tiên, bản dễ đọc](../../var/paper/p2-preparation-2026-10-30/sefora/inputs/01-ID0110/bai-viet.md).
- [Đề và rubric của bài](../../var/paper/p2-preparation-2026-10-30/sefora/inputs/01-ID0110/rubric.txt).

Các bài khác có trong [selected-essays.csv](../../var/paper/p2-preparation-2026-10-30/sefora/selected-essays.csv).
Chọn `Markdown: Open Preview to the Side` trong VS Code để đọc bài. Có thể
mở CSV bằng Excel/Numbers với UTF-8 và dấu phân cách comma; giữ nguyên các cột ID.

`inputs/` giữ bài và rubric. `references/` giữ điểm, highlight và nhận xét
giảng viên. Để chuẩn bị nhãn độc lập, đọc input trước; giữ reference riêng
đến sau vòng gán nhãn. Không đưa điểm/comment giảng viên vào đầu vào hệ thống.

### 2. Chốt rubric trước khi điền nhãn

Mở [rubric-mapping-review.csv](../../var/paper/p2-preparation-2026-10-30/sefora/rubric-mapping-review.csv).
Có sáu dòng, ứng với sáu tên tiêu chí của rubric nguồn. Điền:

| Cột | Cách điền |
|---|---|
| `human_reviewed_meaning` | Tiêu chí thực sự yêu cầu điều gì, đọc từ rubric gốc. |
| `atomic_checklist_statement` | Một yêu cầu cụ thể. Tiêu chí nhiều ý cần tách thành nhiều checklist. |
| `can_be_assessed_from_body_and_rubric` | YES / NO / UNCLEAR. Ghi rõ nếu cần ảnh, bố cục PDF hoặc tài liệu nguồn khác. |
| `requires_new_labels_or_evidence` | Nhãn hoặc liên kết bằng chứng còn thiếu. |
| `human_decision` | KEEP_AS_ATOMIC / SPLIT / EXCLUDE / NEEDS_CLARIFICATION. |
| `reviewer`, `notes` | Người kiểm thật và lý do. |

Chỉ chốt những mục có quy tắc đủ rõ. Ví dụ minh họa tự viết: yêu cầu “mô tả
phương pháp và báo cáo kết quả” có thể cần hai checklist. Đây không phải
nhãn hoặc checklist đã xác nhận cho các bài SEFORA.

Các yêu cầu về ảnh/bố cục hoặc chất lượng lập luận có thể không kiểm chứng
được chỉ bằng text và rule hiện tại. Ghi rõ phạm vi trước khi chạy; không
loại một tiêu chí sau khi nhìn thấy model làm sai. Không biến điểm số hoặc
màu highlight thành MET/UNMET bằng một ngưỡng tự đặt.

### 3. Điền hai phiếu riêng sau khi checklist rõ ràng

- [Phiếu Quý](../../var/paper/p2-preparation-2026-10-30/sefora/labels_quy.csv).
- [Phiếu Yến](../../var/paper/p2-preparation-2026-10-30/sefora/labels_yen.csv).

Hiện mỗi phiếu có 60 dòng **tạm theo tiêu chí gốc**, chưa có đáp án nào được
điền. Nếu bước 2 tách/đổi tiêu chí, phải tạo lại phiếu theo checklist đã chốt.
Chưa dùng phiếu tạm này với lệnh gold freeze/evaluate.

Mỗi người tự đọc bài và điền phiếu của mình trước khi xem phiếu người kia,
reference giảng viên hoặc dự đoán máy. Nếu đã xem, ghi đúng việc đã xem và
dùng case chưa xem cho vòng kiểm độc lập tiếp theo.

| Cột cần điền | Nội dung |
|---|---|
| `label` | MET / UNMET / CANNOT_ASSESS; dùng UNSURE tạm khi cần phân xử. |
| `verification_relation` | SUPPORTED / CONTRADICTED / INSUFFICIENT theo policy rubric đã chốt. |
| `evidence_paragraph_ids` | Mã đoạn như `P0003;P0007` từ bài đọc. |
| `exact_evidence_quote` | Chép đúng câu/đoạn chứng minh kết luận, không viết lại bằng lời mình. |
| `rationale` | Tại sao bằng chứng đáp ứng, không đáp ứng hoặc chưa đủ cho yêu cầu. |
| `annotator_id` | Người gán thực tế. |
| `needs_rubric_clarification` | Điều nào của rubric cần hỏi lại. |

Theo policy hiện tại, MET/UNMET cần bằng chứng phù hợp; thiếu bằng chứng hoặc
chỉ không tìm thấy từ khóa chưa đủ để suy UNMET. Nếu rubric gốc quy định
khác, thống nhất và ghi rõ mapping trước khi đo.

### 4. Phân xử, khóa dữ liệu rồi mới chạy P2

Sau khi hai người hoàn thành và lưu bản riêng, so cả nhãn lẫn bằng chứng.
Cùng nhãn nhưng chọn đoạn khác nhau vẫn cần kiểm. Ghi quyết định cuối và
lý do, không tự điền danh tính người duyệt hay đáp án thay người gán.

Sau đó mới chuẩn hóa checklist, report/rubric version, exact evidence spans
và phiếu theo [gold workflow](../../research/gold_annotation/README.md).
Các mã `CRIT...` và paragraph hiện tại là hỗ trợ chuẩn bị, chưa phải schema
gold hợp lệ. `context.json` có Unicode offsets để chuyển đổi có kiểm tra.

Chốt nhóm DEV/TEST trước khi xem dự đoán. Giữ mọi draft/revision cùng bài
trong cùng nhóm; mã nguồn hiện chưa chứng minh danh tính xuyên các assignment,
nên cần kiểm thêm trước khi gọi split là không rò rỉ theo sinh viên.

Khi có pack và rubric đã chốt, chạy P2 trên đúng đầu vào đó rồi đánh giá:
tìm đúng evidence hay không; kết luận đúng nhãn hay không; từ chối có hợp lý
không. Điểm tổng là phép kiểm sau cùng khi quy tắc chấm đã thống nhất, không
phải điều kiện để gọi pilot thành công.

## Thứ tự bắt đầu

1. Chạy QASPER `--check-only`, sau đó lệnh chạy thật và comparator.
2. Trong lúc chờ, đọc bài SEFORA đầu tiên và điền sáu dòng bảng kiểm rubric.
3. Chốt phạm vi/checklist rồi mới tạo hoặc sử dụng hai phiếu gán nhãn.
4. Chưa chạy hàng loạt SEFORA hoặc sửa threshold dựa trên đáp án.

Phần mềm/script và kiểm artifact có thể tự động hóa. Việc xác nhận ý nghĩa
rubric và nhãn độc lập phải do người kiểm thật thực hiện. LIP 10/10 chỉ là
khớp kỳ vọng tự soạn trên ca đã dùng sửa code, không thay các bước này.
