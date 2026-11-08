# Kiểm tra hai phiếu SEFORA trả về — 02/11/2026

Đã nhận phiếu Quý trong ZIP `SEFORA_REVIEW_LABELS_AND_MAPPING_UPDATED.zip`
và phiếu/mapping Yến. Mỗi phiếu có 60 mục theo 6 tiêu chí gốc của cùng
10 bài. ID và phiên bản bài/rubric đều khớp packet chuẩn bị. Các bản trả
về được lưu riêng, có SHA-256; không ghi đè phiếu trống hoặc context cũ.

## Kết quả đối chiếu

| Hạng mục | Kết quả |
|---|---|
| Quý | 32 MET, 18 UNMET, 10 CANNOT_ASSESS; phiếu ghi AI-assisted human review. |
| Yến | 17 MET, 8 UNMET, 10 CANNOT_ASSESS, 25 UNSURE. |
| So nhãn khi cả hai đã có nhãn xác định | 35/35 cùng nhãn; còn 25 mục UNSURE chưa được đưa vào mẫu số này. |
| So bằng chứng | 25 mục cùng MET/UNMET nhưng chọn evidence khác nhau; 10 mục cùng thiếu ảnh. |
| Mapping | Quý còn 6 quyết định trống; Yến giữ 1, đề nghị EXCLUDE 1 và SPLIT 4. |
| Model P2 trong lượt kiểm này | Chưa chạy; chưa có metric chất lượng chấm hoặc gold được khóa. |

Người dùng xác nhận ngày 02/11 rằng hai người chưa xem nhãn nhau hoặc dự
đoán P2 trước khi lưu phiếu riêng. Ghi nhận đúng tuyên bố này cùng chế độ AI
hỗ trợ của Quý; không suy thành hai người gán hoàn toàn thủ công hoặc tự
khẳng định chưa tiếp xúc điểm/nhận xét nguồn. Số 35/35 chỉ mô tả nhãn của
phần đã có quyết định ở cả hai phiếu, không phải accuracy P2, độ đúng của
evidence hay agreement cuối cùng của cả bộ.

## Kiểm tra evidence

50 quote Quý khớp nguyên văn paragraph đã dẫn. 48 ô quote không trống của
Yến chứa 251 đoạn: sau tách dấu `|`, cả 251 truy được duy nhất về body gốc,
trong đó 21 cần chuẩn hóa kiểu dấu nháy/NBSP. Đã tạo đề xuất span với offset
Unicode `[start,end)`, giữ nguyên toàn bộ phiếu/quote gốc. Có một đoạn đúng
nhưng thiếu paragraph ID trong danh sách; đề xuất bổ sung được ghi riêng.
Hai UNMET của Yến chưa có quote/span, cần giải quyết quy tắc thiếu nội dung
và bằng chứng phù hợp trước khi chuyển schema.

Một bài chứa hai marker `Commented [...]` và URL chen giữa câu trong body
nguồn. Cần kiểm lỗi xuất văn bản trước khi đánh giá lỗi viết. Chưa có căn
cứ khẳng định đây là feedback giảng viên; không tự sửa context hoặc version
đã gửi cho người gán.

## Phần cần hoàn thành để đo P2

1. Thống nhất checklist nguyên tử và quy tắc MET/UNMET/CANNOT_ASSESS. Bốn
   tiêu chí được đề nghị tách chưa thể lấy nguyên nhãn rộng hiện tại làm
   đáp án của từng mục con. Không tự bổ sung ngưỡng số lượng/điểm vào rubric.
2. Chốt phạm vi text/ảnh và các yêu cầu cần bài nguồn bên ngoài. Phân xử
   25 UNSURE, bằng chứng khác nhau và các trường hợp thiếu span/nguồn.
3. Chuẩn hóa context/phiếu theo gold evaluator, khóa split/config và hồ sơ
   pack; sau đó mới chạy P2 và đối chiếu nhãn/bằng chứng. G-05 vẫn OPEN.

Artifact riêng tư tại
[`var/paper/p2-review-2026-11-02/v1/DOC_TRUOC.md`](../../var/paper/p2-review-2026-11-02/v1/DOC_TRUOC.md):
bản gốc, receipts, provenance, summary, bảng đối chiếu 60 mục, danh sách
25 UNSURE, mapping hợp nhất chờ quyết định và đề xuất span. Có kiểm tra độc
lập lại 301 span, checksum nguồn và các cột quyết định cuối vẫn trống.
Chưa thêm số liệu chấm SEFORA vào bảng kết quả bài báo.

## Bản Yến sửa ngày 04/11/2026

Đã nhận `labels_yen (1).csv`, giữ riêng bản gốc và chạy lại audit. Đủ 60
mục theo đúng ID/phiên bản, không còn UNSURE: 24 MET, 10 UNMET và 26
CANNOT_ASSESS. Có 29 nhãn thay đổi so với bản Yến trước. Cả 276 đoạn trích
đều khớp nguyên văn, duy nhất và đúng paragraph của bài nguồn.

So với phiếu Quý, 39/60 mục cùng nhãn; còn 21 khác biệt, gồm 16 khác về khả
năng đánh giá và 5 khác MET/UNMET. Đây là đối chiếu người gán, không phải
độ chính xác hệ thống. Hai UNMET do vắng trích dẫn/summary ở bài 08 vẫn
chưa có span; không tạo phản chứng giả để chuyển thành gold.

Rationale mới có quy tắc gộp theo ngưỡng 60%, số mục CANNOT_ASSESS và mục
bắt buộc. Chưa tự áp dụng các quy tắc này vào rubric hay code: mapping bốn
tiêu chí vẫn đề nghị SPLIT, chưa có quyết định gộp đã được hai người chốt.
Xác nhận không xem nhãn nhau/dự đoán ngày 02/11 không được tự mở rộng sang
lần sửa này.

Hồ sơ mới ở `var/paper/p2-review-2026-11-04/v1/`, có CSV 21 khác biệt với
cột phân xử để trống. Chỉ CRIT001 được chọn cho một lượt P2 local chẩn đoán
trên cả 10 bài; rubric dùng nguyên câu hỏi nguồn, nhãn/evidence/rationale
người gán và điểm/feedback giảng viên không vào inference. Lượt này không
phải approved benchmark hay gold đã khóa; toàn bộ nhãn CRIT001 của cả hai
phiếu đều MET nên không đo được chất lượng ba lớp hoặc chất lượng chấm
toàn bộ rubric. Artifact tại `var/paper/sefora-p2-diagnostic-2026-11-04/`.

Lượt chẩn đoán đã hoàn tất: LLM có 3 MET khớp hai phiếu, 7 CANNOT_ASSESS
(2 timeout, 3 quote bị từ chối, 2 model kết luận thiếu evidence). Giữ mọi
thất bại trong mẫu số; không đổi prompt/config hoặc chọn lần chạy đẹp hơn.
10 proof của 3 MET được giải về body/paragraph nguồn. Đã tìm thấy riêng
một lỗi verifier đòi thêm thông tin rubric không yêu cầu và một lỗi bỏ sót
đoạn ở retrieval. Đây chưa phải kết quả ba lớp, chấm điểm hay full P2; xem
`KET_QUA_P2.md` trong thư mục artifact để đọc và mở bảng đối chiếu.

## Vòng sửa P2 ngày 04/11

Profile riêng `bm25-p2-llm-v2` thêm context có giới hạn cho báo cáo ngắn,
source-unit IDs do code giải về quote/offset và hai lượt model: chọn unit,
rồi xác minh chỉ trên các unit đã chọn. Không đổi body, rubric hoặc hai
phiếu tham chiếu. Exact-quote/profile v1 và lượt gốc 3/10 vẫn được giữ riêng.

Lượt cuối `improvement/replay-v2-2` khớp 9/10 nhãn CRIT001, có 9 MET,
1 CANNOT_ASSESS; không timeout/quote lỗi và 23 proof qua kiểm tra nguồn,
offset và version. Bài 04 còn thiếu bằng chứng phù hợp trong các unit được
chọn. Citation vẫn chưa đồng đều: một số câu về gắn bó gia đình/âm nhạc còn
chung chung dù label MET. Đây chưa phải xác nhận ngữ nghĩa của 23 proof.

Bộ kiểm tra tổng hợp cuối đạt 9/10, không có ca âm nào được thưởng MET;
ca outline tương lai vẫn UNMET thay vì CANNOT_ASSESS kỳ vọng. Lượt trung
gian 10/10 nhãn nhưng citation sai/yếu được lưu và không dùng thay số cuối.
Chi tiết tại `improvement/KET_QUA_SUA_P2.md` trong thư mục artifact.

Các số này là development replay trên 10 nhãn MET của một tiêu chí,
không phải full P2 accuracy, gold độc lập, chất lượng đủ 60 mục hoặc bảng
kết quả chấm rubric của bài báo. Mapping, khác biệt 21 mục và hồ sơ pack
vẫn cần được chốt riêng.
