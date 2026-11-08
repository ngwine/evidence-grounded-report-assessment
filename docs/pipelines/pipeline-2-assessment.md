# Pipeline 2 – Phân tích và đánh giá báo cáo dựa trên bằng chứng

## Tổng quan

Pipeline đánh giá bắt đầu bằng **Template-based Rubric Definition** nhằm chuẩn
hóa đầu vào rubric trước khi thực hiện phân tích.

## Luồng xử lý

```
Template-based Rubric Definition
→ Rubric Compiler
→ Checklist Classification: LOCAL / GRAPH
→ Evidence Retrieval
→ Evidence Verification
→ MET / UNMET / CANNOT_ASSESS
→ Evidence-grounded Rationale
→ Deterministic Decision Rules
→ Proposed Score
→ Lecturer Review
→ Feedback Log
```

## Chi tiết

### Rubric Compiler
Rubric được chuẩn hóa theo cấu trúc gồm tiêu chí, checklist, yêu cầu bằng
chứng, mức đánh giá, trọng số và quy tắc quyết định. Compiler chuyển thông tin
này thành các checklist có thể truy xuất và kiểm chứng.

### Checklist Classification
Mỗi checklist được xác định thuộc một trong hai nhóm:
- **LOCAL**: có thể đánh giá dựa trên một hoặc một số đoạn nội dung cụ thể.
- **GRAPH**: cần đối chiếu thông tin và quan hệ giữa nhiều phần của báo cáo
  hoặc nhiều nguồn dữ liệu.

### Evidence Retrieval

**LOCAL checklist**: Hybrid Retrieval kết hợp BM25, embedding và reranker.

**GRAPH checklist**: Evidence Graph biểu diễn claim, concept, entity và quan hệ.
Graph-based retrieval theo hướng HippoRAG-style truy xuất bằng chứng nhiều bước.

Các dạng quan hệ cần kiểm tra:
- Mục tiêu ↔ Kết quả
- Phương pháp ↔ Thực nghiệm
- Kết luận ↔ Dữ liệu hỗ trợ
- Claim ↔ Evidence từ tài liệu đối chứng

### Evidence Verification

Verification tách hai tầng để không đánh đồng “không tìm thấy bằng chứng” với
“có bằng chứng chứng minh claim sai”:

1. Quan hệ giữa từng claim và evidence:
   - **SUPPORTED**: evidence trực tiếp hỗ trợ claim;
   - **CONTRADICTED**: evidence trực tiếp mâu thuẫn với claim;
   - **INSUFFICIENT**: evidence thiếu, mơ hồ, khác ngữ cảnh hoặc chưa đủ thẩm
     quyền để xác định hỗ trợ hay mâu thuẫn.
2. Kết quả checklist:
   - **MET**: có đủ evidence `SUPPORTED` theo yêu cầu rubric;
   - **UNMET**: evidence đáng tin cậy cho thấy yêu cầu không đạt, bao gồm trường
     hợp claim bị `CONTRADICTED`;
   - **CANNOT_ASSESS**: chỉ có evidence `INSUFFICIENT` hoặc xung đột chưa thể
     phân xử đáng tin cậy.

Mapping mặc định:

| Claim–evidence | Checklist |
|---|---|
| `SUPPORTED` | `MET` |
| `CONTRADICTED` | `UNMET` |
| `INSUFFICIENT` | `CANNOT_ASSESS` |

Trường hợp “báo cáo nói A, tài liệu đối chứng nói B” chỉ được đánh dấu
`CONTRADICTED → UNMET` khi tài liệu đối chứng đã được duyệt cho đúng purpose,
đủ thẩm quyền và A/B nói về cùng đối tượng, thời điểm, đơn vị, dataset và điều
kiện. Nếu chưa xác định được nguồn nào đúng hoặc khác ngữ cảnh thì phải dùng
`INSUFFICIENT → CANNOT_ASSESS`, không tự chọn một phía.

Verifier phải lưu cả evidence span chứa A và B, source/version/locator và lý do
mapping. Claim gồm nhiều ý nên được compiler tách thành checklist nguyên tử;
không dùng trạng thái `PARTIALLY_SUPPORTED` để che một mâu thuẫn trực tiếp.

Baseline `SCOPED_PHRASE_CONTEXT_V4` kiểm tra từng lần khớp phrase trước khi
tính support. `no/without` mở đối tượng phía sau không tự phủ định một phát
biểu khẳng định phía trước. Các lần nhắc tới trong kế hoạch, trạng thái đang
chờ hoặc điều kiện giả định được giữ trong `non_asserted_evidence_spans`,
kèm đoạn trích và `context_reason`, thay vì tính là công việc đã hoàn thành.
Checklist yêu cầu một kế hoạch có thể nhận bằng chứng kế hoạch. Mẫu phản
chứng cũng được kiểm tra ngữ cảnh: một phản chứng chỉ xuất hiện trong giả
định không chứng minh hiện trạng không đạt. Các mẫu bị giữ lại được ghi
trong `withheld_contradiction_spans`.

V4 bổ sung nhận diện công việc pending trong một số dạng bảng và chủ ngữ
phối hợp, phân biệt công cụ có sẵn với hành động đã hoàn tất, và giới hạn
phủ định vào hành động/đối tượng tương ứng. Các yêu cầu bảo toàn dữ liệu hoặc
công khai hạn chế có thể dùng bằng chứng phủ định phù hợp do người soạn khai
báo. Một phát biểu khẳng định và phủ định thực sự về cùng hành động vẫn giữ
`CANNOT_ASSESS`; không coi mọi câu phủ định là bằng chứng đạt.

Các modal mơ hồ như `may/should` cần đi với động từ công việc; tháng `May`
hoặc cụm dẫn lời `should be noted` không làm mất phản chứng. Phủ định ở một
vế phối hợp khác cũng không tự phủ định mẫu phản chứng đã khớp; chỉ các
cấu trúc bác bỏ trực tiếp như `not true that` được giữ riêng ở bước này.
Khi có đủ support nhưng một mẫu phản chứng chỉ bị giữ lại vì cue tương lai/
điều kiện có phạm vi chưa chắc chắn, kết quả là `CANNOT_ASSESS` với lý do
`UNRESOLVED_COUNTERCLAIM_SCOPE`, tránh bỏ qua phản chứng thực ở mệnh đề khác.

Đây vẫn là bộ quy tắc từ vựng, chưa có semantic entailment. Nó chưa giải quyết
đầy đủ phạm vi phủ định, quan hệ giữa danh từ và hành động, hay mọi dạng trạng
thái kế hoạch ở bảng/tiêu đề khác mệnh đề. Mâu thuẫn thực và thiếu bằng chứng tiếp
tục giữ `CANNOT_ASSESS`; quy tắc tính điểm không đổi. Khi so phiên bản, giữ
nguyên đầu vào và nhãn tham chiếu, tạo lượt chạy mới và lưu cả kết quả cũ.
Xem [kiểm tra phát triển V4 và giới hạn nhãn](../benchmarks/output-quality-development-2026-10-29.md).
NLI trong các profile mới chỉ phục vụ P1; hai profile NLI v2 giữ P2 ở BM25
và bộ quy tắc V4 này.

Từ 03/11 có thêm chế độ riêng `bm25-p2-llm-v1` dùng
[verifier LLM local](../architecture/p2-local-llm-verifier.md). Qwen3.5 4B
đề xuất relation cho từng requirement cùng quote/evidence ID; code kiểm
JSON, phạm vi, quote và provenance trước khi tự tổng hợp nhãn. V4 vẫn là
baseline. Lỗi model hoặc proof không hợp lệ trả CANNOT_ASSESS, không tự
chạy lại bằng V4; scoring và quy trình giảng viên duyệt được giữ nguyên.
Đã có kiểm tra tổng hợp bằng model thật, chưa có độ chính xác P2 trên
gold người chốt hoặc kết quả SEFORA đưa vào bài báo.

### Kiểm tra liên kết bằng chứng trước khi xuất kết quả

Evidence Pack được đối chiếu với chunk gốc của đúng report/version trước khi
xác minh. Tọa độ normalized phải là số nguyên trong chunk; hợp các source span
phải phủ nội dung chữ của chunk. Khoảng trắng do chunker ghép các element được
chấp nhận, nhưng không chấp nhận một cụm từ có thể tạo support nằm ngoài vùng
có provenance. Kiểm tra này ở `_validated_evidence_pack` trong
`research/core_mvp/assessment.py`.

Runtime contract trong `research/core_mvp/contracts.py` kiểm tra thêm liên kết
từ proof của kết luận về Evidence Pack: `MET` cần span hỗ trợ, `UNMET` cần span
phản chứng. Xóa bằng chứng hoặc đổi liên kết sang chunk/report/version khác
phải bị từ chối trước khi lưu/xuất. `CANNOT_ASSESS` vẫn cho phép không có
bằng chứng và giữ nguyên chính sách không đề xuất điểm tổng. Đây là kiểm tra
tính toàn vẹn, chưa chứng minh kết luận đúng về mặt ngữ nghĩa.

### Deterministic Decision Rules
Điểm đề xuất được suy ra bằng decision rules định nghĩa trong rubric, **không**
để LLM trực tiếp quyết định điểm.

### Lecturer Review
Giảng viên chấp nhận, chỉnh sửa hoặc loại bỏ nhận xét và điểm đề xuất.

### Feedback Log
Mọi thay đổi của giảng viên được lưu phục vụ phân tích sai số và cải tiến.
