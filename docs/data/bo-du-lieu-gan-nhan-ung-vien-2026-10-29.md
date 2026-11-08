# Bộ dữ liệu gán nhãn ứng viên cho hai pipeline

Kiểm tra nguồn công khai ngày 29/10/2026; cập nhật tải dữ liệu ngày 30/10/2026.
Đã tải PAWS-Wiki Labeled Final và SEFORA theo yêu cầu người dùng, kiểm tra
checksum/cấu trúc và xuất thêm PAWS dạng TSV. Chưa chạy model, tạo pack thực
nghiệm hoặc đưa thêm số liệu chất lượng vào bài.

[Hướng dẫn mở dữ liệu trên máy](../../var/datasets/PAWS_VA_SEFORA_CACH_MO.md)
có đường dẫn file và cặp bài–rubric mẫu. PAWS có 49.401/8.000/8.000 cặp ở
train/dev/test. SEFORA có 564 JSON bài viết, 37 TXT và 5.684 annotation inline.
Link PAWS Google Storage gốc trả 403 trong lượt tải; bản Parquet thay thế
được lấy từ [kho phân phối công khai](https://huggingface.co/datasets/google-research-datasets/paws)
và kiểm với LFS SHA-256, giữ riêng hồ sơ nguồn và bản TSV chuyển đổi. SEFORA
khóa theo commit `8a134b0c9fe1fb943121e2a6474b8941c0f05fd3` của repo tác giả.

## Ưu tiên P2: SEFORA

[Repo tác giả](https://github.com/ShayanPey/SEFORA) cung cấp JSON bài viết sinh
viên và TXT đề/rubric, điểm rubric cùng nhận xét giảng viên gắn vào văn bản.
[Giấy phép dataset](https://raw.githubusercontent.com/ShayanPey/SEFORA/main/LICENSE)
là CC BY-NC 4.0. Theo [paper, mục 3](https://arxiv.org/html/2607.00274v1),
có 564 bản nháp từ 371 bài của 155 sinh viên; chỉ 295 bản có điểm theo trait,
205 bản có điểm tổng. Không giả định mọi bản đều đầy đủ điểm.

Đánh giá của dự án: đây là ứng viên dễ tiếp cận để khởi đầu pilot P2 với
bài thật và nhãn người. Miền là bài viết tiếng Anh, chưa phải báo cáo kỹ thuật.
Điểm theo tiêu chí và comment chưa tự trở thành ba nhãn checklist hoặc gold
evidence liên kết đầy đủ cho từng mục. Cần kiểm tra ánh xạ trước khi so máy.

README tác giả mô tả các trường `paragraphs[].body`, annotation có
`text/context_left/context_right/comment`, và `annotations[].grades` với tên
tiêu chí cùng giá trị số. Trong khi đó, [compiler hiện tại](../../research/core_mvp/rubric.py)
yêu cầu checklist nguyên tử, `requirements[].any_of`, mode và trọng số;
[gold workflow](../../research/gold_annotation/README.md) yêu cầu outcome,
quan hệ evidence và span theo đúng version. Vì vậy, tải SEFORA về chưa thể
đưa trực tiếp vào evaluator P2 và gọi điểm của nó là gold cho checklist của
dự án. Phải giữ riêng điểm gốc, feedback gốc, các ánh xạ được người kiểm tra
và những mục chưa ánh xạ được.

Đã đối chiếu một [JSON mẫu thực tế](https://github.com/ShayanPey/SEFORA/blob/main/SEFORA/Batch_1/Course_1/Class_1/Essay_1/Revision/Batch_1_Course_1_Class_1_Essay_1_Revision_ID0007.json)
với [rubric đi kèm](https://github.com/ShayanPey/SEFORA/blob/main/SEFORA/Batch_1/Course_1/Class_1/Essay_1/Batch_1_Course_1_Class_1_Essay_1_rubric.txt):
rubric có sáu mục với mức tối đa cộng thành 100, JSON chứa điểm số theo tên
từng mục. Trong mẫu này, annotation inline có text/context/comment nhưng
không có `criterion_id` hoặc offset `start/end`, cũng không có liên kết trực
tiếp từ điểm tiêu chí tới highlight. Đây là phát hiện trên mẫu đã kiểm, chưa
phải audit đầy đủ 564 bản. Cần kiểm tính duy nhất của quote/context và nhãn
liên kết trước khi chuyển thành evidence span cho evaluator của dự án.

## Các nguồn bổ sung

| Nguồn chính thức | Nhãn và khả năng sử dụng | Giới hạn cần giữ |
|---|---|---|
| [ContractNLI](https://stanfordnlp.github.io/contract-nli/) | 607 hợp đồng, 17 giả thuyết cố định; Entailment / Contradiction / NotMentioned và evidence span. JSON tải công khai, CC BY 4.0. | Kiểm bước truy xuất/xác minh theo tài liệu; miền hợp đồng, không xác nhận chất lượng chấm báo cáo sinh viên. Không tự đồng nhất quan hệ NLI với điểm rubric. |
| [HARMOGEN-R v2](https://zenodo.org/records/19534458) | 770 câu trả lời sinh viên, rubric và đánh giá người/LLM được phân biệt; ZIP SQL/CSV/JSON 42,7 MB, CC BY 4.0. | 68.948 là số bản ghi nhiều bảng, không phải số bài. Nội dung chấm chủ yếu tiếng Bồ Đào Nha theo [paper](https://www.nature.com/articles/s41597-026-07397-8). Rationale LLM không phải gold người; chưa xác minh evidence-span gold. |
| [PAWS-Wiki](https://github.com/google-research-datasets/paws) | Chọn bản Labeled Final có nhãn người paraphrase / khác nghĩa và train/dev/test. Các ca cùng từ nhưng đảo quan hệ phù hợp kiểm lỗi P1 hiện tại. | Tiếng Anh, cặp câu; không có span nguồn trong báo cáo dài. Không dùng bản Unlabeled như nhãn người. |
| [ViSP](https://huggingface.co/datasets/ngwgsang/ViSP) | Cặp câu tiếng Việt gốc–paraphrase công khai, hữu ích kiểm recall. | Có bước tạo tự động; không gọi toàn bộ là gold người độc lập. Chủ yếu cặp dương, thiếu NONE và gold span báo cáo. HF gắn MIT nhưng [README tác giả](https://github.com/ngwgsang/ViSP) nêu mục đích nghiên cứu/giáo dục; cần đối chiếu trước khi đóng pack. |
| [PAN13](https://zenodo.org/records/3715980) | Cặp tài liệu và vị trí đoạn tái sử dụng ở hai phía; dự án đã có converter. | Đánh giá alignment; không phải nhãn chấm rubric hay bộ phân loại bốn loại tương đồng sẵn dùng. Chưa xác nhận license cụ thể từ metadata hiển thị trong lượt tìm này. |

## Gần miền báo cáo hơn nhưng chưa tải tự do

[Exposía](https://aclanthology.org/2026.emnlp-main.49/) có đề cương nghiên cứu
của sinh viên CNTT, feedback theo đoạn và điểm tiêu chí của người chấm.
[Kho chính thức TU Darmstadt](https://tudatalib.ulb.tu-darmstadt.de/items/fd9881c0-fb48-40fe-aaa4-31bcaae5c5ea)
ghi CC BY-NC 4.0 và **File access restricted**. Trang trực tiếp trả 403 trong
lượt kiểm tra; chưa coi đây là nguồn có thể tải ngay. Giấy phép paper và quyền
truy cập file dataset là hai thông tin khác nhau.

## Hướng dùng đề xuất

1. Khảo sát SEFORA trên subset có đủ bài, rubric và điểm người để xác định
   tiêu chí nào ánh xạ được, tiêu chí nào cần gán nhãn bổ sung.
2. Dùng PAWS-Wiki có nhãn người để đo khả năng phân biệt paraphrase và ca khác
   nghĩa trước khi chỉnh P1 tiếp; PAN13 kiểm riêng alignment trên tài liệu.
3. ContractNLI là phép kiểm riêng cho verifier/evidence. Chưa thêm tất cả các
   bộ chỉ để có nhiều bảng kết quả.

Bước tích hợp đầu tiên nên là audit cấu trúc và mức đầy đủ của subset, trước
khi chạy model: bài có text, rubric, nhãn người, bằng chứng gì; bản nháp nào
cùng tác giả/bài; mục nào thiếu dữ liệu. Đầu ra của bước này là thống kê và
descriptor ánh xạ, không phải nhãn do máy tự hoàn thiện. Các bộ công khai
giảm công gán từ đầu nhưng không bảo đảm model sẽ có kết quả tốt hơn.

Giữ rubric/checklist là đặc tả yêu cầu; gold là kết luận người trên một tài
liệu cụ thể. Không chuyển comment vắng mặt hoặc điểm thấp thành UNMET bằng
một ngưỡng tự đặt. Không dịch bộ tiếng Anh rồi coi nhãn/spans cũ tự hợp lệ
cho tiếng Việt. Chia theo bài/nhóm nguồn, giữ các draft cùng bài trong cùng
split. Các nguồn này giúp giảm công gán từ đầu; chưa nguồn nào ở đây được
xác minh là bộ gold đầy đủ cho cả hai pipeline trên báo cáo kỹ thuật Việt.
