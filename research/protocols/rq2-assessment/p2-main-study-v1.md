# P2 — thiết kế thực nghiệm chính và lượt chuẩn bị DEV v1

Đây là thiết kế theo phạm vi đề tài ngày 08/11/2026, **chưa phải kết quả
thực nghiệm chính đã hoàn thành**. Không đặt ngày hạn hoặc tự xác nhận dữ
liệu/giám khảo. [Kiểm kê đầu vào](../../../docs/benchmarks/p2-experiment-readiness-2026-11-08.md)
phân biệt thứ sẵn sàng cho DEV với phần chưa sẵn sàng đánh giá độc lập.

## Câu hỏi và phép so

Trên cùng báo cáo–rubric, evidence retrieval có cải thiện nhãn checklist
và mức hỗ trợ của rationale so với LLM đọc báo cáo không truy xuất không?
Graph quan hệ có giúp nhóm checklist cần đối chiếu nhiều phần không?

| Cấu hình | Đầu vào được phép chọn | Trạng thái lúc lập protocol |
| --- | --- | --- |
| Luôn MET | Không đọc báo cáo; chỉ là đối chứng nhãn | Metrics đã có. |
| LLM không retrieval | Báo cáo theo chính sách context khóa trước | Runner DEV mới thực hiện toàn bộ parsed chunks nếu dưới giới hạn; vượt giới hạn từ chối chuẩn bị, không âm thầm fallback retrieval/crop. |
| LOCAL | Evidence truy xuất từ cùng nguồn hợp lệ | Runner DEV hiện **BM25**, chưa gọi là hybrid hoàn chỉnh. |
| LOCAL + GRAPH chọn lọc | Evidence cục bộ và quan hệ liên phần có provenance | **Chưa triển khai ngữ nghĩa, chưa chạy**. Structure/term PPR không thay phương pháp này. |

Giữ model/digest, rubric/compiler, verifier và scorer chung khi so retrieval;
cho phép evidence pack khác nhau. Khai token/budget và tổng calls thực tế,
không khẳng định công bằng compute chỉ từ cùng num_ctx/num_predict.
Một bước/hai bước là phép so verifier khác; nếu thay cả verifier và retrieval
thì không quy toàn bộ chênh lệch cho riêng retrieval hoặc auditor.

## Dữ liệu và đơn vị quan sát

- Theo chỉ đạo dùng SEFORA trong lượt này, tập chính có thể là bài viết
  sinh viên tiếng Anh SEFORA chưa dùng sửa phương pháp, với rubric phù hợp.
  Không bắt buộc R1/R2 hoặc báo cáo mới bên ngoài để bắt đầu. Kết quả đó
  không tự xác nhận độ đúng trên báo cáo kỹ thuật tiếng Việt.
- Tập chính cần report–rubric trong miền truy cập được, version/quyền dùng
  rõ, nhãn checklist và evidence/lý do cùng rule với verifier. Có checklist
  LOCAL và liên phần phù hợp câu hỏi; không tự ép nhãn để cân lớp.
- Khóa nhóm DEV/evaluation theo báo cáo và nguồn liên quan, giữ draft cùng
  nhóm; lựa chọn dữ liệu không dựa trên phương pháp nào thắng.
- Báo nhãn từng lớp và số report, không tính checklist tương quan thành
  những report độc lập. Bất định/paired contrasts resample theo report/group.
- Không đặt số bài tối thiểu tùy ý. Quy mô cần căn cứ số nhóm độc lập,
  class support, độ bất định mong muốn và khả năng gán nhãn thực tế.
- Các phiếu thực sự chỉ có một người/AI hỗ trợ phải khai đúng. Không tạo
  IAA, điểm giảng viên, người duyệt hoặc gold đồng thuận bằng công cụ.
- UNMET do vắng nội dung cần rule cho phép và kiểm đủ phạm vi; retrieved
  evidence rỗng không chứng minh vắng toàn văn. CA ngữ nghĩa và lỗi kỹ thuật
  tách biệt, không biến timeout thành quyết định CA đúng.

## Lượt DEV có thể chạy ngay

`research.p2_comparison.retrieval_study` tái sử dụng snapshot nguồn của 15
bài SEFORA đã được xem lỗi, gọi rõ PREVIOUSLY_INSPECTED_DEV. Đây là 45 mục
tham chiếu một người có Claude hỗ trợ; 42 MET/3 UNMET/0 CA. Không được đổi
tên thành tập chính/holdout mới sau khi sửa bằng các lỗi này.

Chế độ `context_bundles_v1` giữ evidence trong từng source span, giới hạn
1.800 ký tự mỗi unit, không cắt câu ở dấu chấm của initials. Prompt yêu cầu
đúng người nói/nguồn, không đếm title/term thành quotation. Đây là thay đổi
phương pháp, không tự chứng minh model đã hết lỗi. Lượt cũ không bị sửa.

```bash
.venv-research/bin/python -m research.p2_comparison.retrieval_study prepare \
  --source-prepared-dir var/paper/p2-single-reference-eval-2026-11-07/prepared-v1 \
  --config research/configs/p2-comparison/context-one-step-v1.json \
  --cohort PREVIOUSLY_INSPECTED_DEV \
  --output-dir var/paper/p2-main-study-preparation-2026-11-08/context-retrieval-dev-prepared-v1

.venv-research/bin/python -m research.p2_comparison.retrieval_study run \
  --prepared-dir var/paper/p2-main-study-preparation-2026-11-08/context-retrieval-dev-prepared-v1 \
  --output-dir var/paper/p2-main-study-preparation-2026-11-08/context-retrieval-dev-run-v1 \
  --allow-real-model
```

Prepare khóa input/config/code/prompt/schema trước model call. Run giữ kết
quả từng checklist và marker bắt đầu, không tự retry request đang dở, không
ghi đè một dự đoán xấu. Chạy tiếp bỏ qua kết quả đã hoàn tất. Sửa phương pháp
cần thư mục preparation/run mới, không xóa marker hoặc thay config trong lượt.

## Chỉ số và bằng chứng cần thu

1. **Nhãn:** macro/per-class F1, confusion matrix, false MET và recall CA;
   lớp không có nhãn tham chiếu là chưa đánh giá, không báo F1 giả cho nó.
   Technical abstentions vẫn nằm trong mẫu số đầy đủ, coverage báo riêng.
2. **Truy xuất:** evidence recall/precision tại budget đã khóa, xét các tập
   bằng chứng thay thế hợp lệ; DOCUMENT_ABSENCE không tạo span giả.
3. **Rationale:** kiểm đúng nguồn/offset là cơ học; người đánh giá kiểm
   bằng chứng thực sự hỗ trợ kết luận trên toàn bộ conclusive predictions
   hoặc mẫu được khóa trước, không chỉ các mục máy khác người.
4. **Điểm:** chỉ so với điểm có chuyên môn trên **cùng rubric**, sau khi
   mức/rule scorer đã hỗ trợ; báo MAE/độ lệch và coverage cho điểm. Điểm danh
   nghĩa 3 checklist SEFORA không thay tổng điểm bài viết theo rubric khác.
5. **Tài nguyên:** số calls, prompt/output tokens, thời gian/RAM theo điều
   kiện thực thi. Timing DEV một lượt có cache không phải latency benchmark.

Phân tích DEV bổ sung paired report bootstrap (5.000 lượt, seed 20261108,
percentile type-7) cho chênh khớp nhãn LOCAL trừ không retrieval. Đây là
**hậu kiểm mô tả**, không phải contrast/seed đã đăng ký trước request đầu
tiên, không tính bất định của nhãn và không tạo claim significance.
Lượt đánh giá chính cần khóa lựa chọn metric/contrast/resampling trước chạy.

`evidence_review.py` xuất phiếu che tên phương pháp, mapping riêng và nguồn
ngữ cảnh. Trường người kiểm/rating để trống; summary chỉ tính đánh giá người
thực sự nhập, không suy semantic support từ model tự chấm hoặc nhãn khớp.
CA và technical không đưa vào mẫu số citation support nhưng coverage/đếm
riêng. UNCERTAIN không bị loại để làm tăng support rate.

## Điều kiện trước lượt đánh giá chính

Đầu vào còn thiếu: cohort SEFORA chưa dùng sửa phương pháp, nhãn phù hợp,
graph quan hệ thực nếu báo kết quả GRAPH, mức rubric và điểm tham chiếu thật
nếu báo agreement điểm. Nguồn và rubric SEFORA đã có; điểm nguồn phải được
đối chiếu đúng rubric, không đổi thành nhãn ba trạng thái bằng threshold
tùy ý. Thông tin R1/R2 giữ để mở rộng kiểm định trong miền sau, không chặn
SEFORA hoặc tự điền approval còn thiếu.

Khóa config/router/metrics trên DEV rồi mới chạy tập đánh giá. Giữ đủ kết
quả và contrasts, kể cả kết quả âm; không chạy nhiều biến thể trên tập đó
rồi chỉ lấy phương án thắng. GRAPH có thể dùng chọn lọc khi có lợi, không
bắt buộc mọi checklist phải đi qua graph.

## Đưa vào bài báo

Methods mô tả dữ liệu/nhãn/split/budget; Results tách retrieval, label,
semantic support và điểm; Discussion giải thích lỗi và trade-offs. SEFORA
cũ/mới dùng phát triển phải ghi DEV và giữ giới hạn. Chỉ có đánh giá chính
thực sự mới tạo claim cho chuỗi P2 tương ứng; QASPER không thay phép đo này.
