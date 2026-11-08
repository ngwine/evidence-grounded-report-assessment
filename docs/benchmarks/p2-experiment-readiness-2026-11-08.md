# P2: đủ đầu vào để triển khai gì, còn thiếu gì cho thực nghiệm chính?

**Đủ để sửa code và đo trên DEV ngay. Chưa đủ để chạy và kết luận toàn bộ
thực nghiệm chính theo đề cương.** Đây là kiểm kê metadata ngày 08/11/2026,
không phải approval dữ liệu, lựa chọn TEST mới hoặc kết quả model mới.

**Chỉ đạo tiếp theo của người phụ trách: dùng SEFORA.** Không bắt buộc
khôi phục R1/R2 mới được đánh giá P2. Có thể dùng bài SEFORA chưa dùng sửa
phương pháp làm tập đánh giá trên **bài viết sinh viên tiếng Anh**, sau khi
chốt rubric/checklist và tham chiếu phù hợp. Báo cáo kỹ thuật Việt/Anh vẫn
cần cho kiểm định khả năng áp dụng trong miền đó; không dùng giới hạn này
để chặn phép đánh giá SEFORA hoặc tự gọi mọi essay là báo cáo kỹ thuật.

Đã lập thêm [danh sách ứng viên theo metadata](../../var/paper/p2-main-study-preparation-2026-11-08/sefora-candidates-v1/output/candidate-manifest.json):
149 nhóm bài–assignment thuộc 55 ID tên file tạm, đã loại các ID xuất hiện
trong 25 bài DEV và chọn một draft theo rule xác định. Đây **chưa phải**
149 mẫu độc lập hoặc yêu cầu gán nhãn toàn bộ; còn kiểm rubric phù hợp,
source-family/duplicate và nhóm sinh viên giữa assignment trước khi khóa
tập đánh giá. Chưa đọc nội dung/điểm bài mới hoặc chạy model trên chúng.

## Dữ liệu thực sự đang có

| Nguồn | Kiểm tra được | Sử dụng hợp lý |
| --- | --- | --- |
| SEFORA 10 bài cũ | Có báo cáo/rubric và các lượt phát triển đã xem | Giữ làm DEV cho sửa verifier; không tái gọi là đánh giá chưa xem. |
| SEFORA 15 bài mới đã chạy | 15 bài, 45 checklist; 42 MET/3 UNMET/0 CA; một người gán có Claude hỗ trợ; 90 dự đoán đã khóa | Tái sử dụng nguồn và lỗi đã biết để phát triển, giữ nguyên kết quả cũ. Chưa kiểm đủ ba trạng thái hoặc điểm toàn bài. |
| Kho SEFORA tải về | 564 bản thảo, 27 nhóm bài tập, 121 ID tên file tạm; 33 tệp tên rubric; 386 bản thảo có điểm số nguồn | Có nguyên liệu chuẩn bị nhóm khác sau khi kiểm nhóm/rubric/nhãn. Điểm nguồn không tự trở thành nhãn checklist hoặc điểm cho rubric ba checklist của nhóm. |
| Metadata SEFORA chưa nằm trong hai lượt chọn trên | 295 tệp đạt rule chuẩn bị cũ; 223 tệp có ID tên file ngoài các ID đã chọn | Đây là **số tệp ứng viên**, không phải số bài/nhóm độc lập hoặc holdout đã xác nhận. Có nhiều draft và ID lặp giữa bài tập; chưa chọn hoặc đọc nội dung cohort mới. |
| Pilot trong miền R1/R2 đã lưu từ tháng 10 | Có manifest và 26 nhãn nhập từ phiếu: 20 LOCAL/6 GRAPH; 15 MET/6 UNMET/5 CA | Có thông tin để khôi phục công việc; chưa đủ làm input chạy. Registry vẫn ghi chưa tìm được đúng file nguồn, quyền dùng và ẩn danh còn PENDING. Không bỏ sót bộ này chỉ vì thư mục công khai là template. |
| QASPER xác nhận lại | 281 paper được đưa vào lượt chuẩn bị, 1.005 câu; 646 câu đủ điều kiện thuộc 255 paper | Kiểm thành phần tìm đoạn bằng chứng. Không thay nhãn rubric, graph hoặc điểm báo cáo. |

Kiểm tra hash có giới hạn trong repo trên **83 PDF/DOCX** không tìm thấy
file khớp ba SHA-256 của R1 DOCX và R2 PDF/DOCX trong registry. Không đọc/
phân tích nội dung các file này; không quét lại Desktop/Downloads. Vì vậy
đây không phải khẳng định file không tồn tại ở nơi khác. Hai báo cáo chỉ
được nối lại với nhãn khi xác định đúng phiên bản thực sự.

## Có thể làm ngay

1. Sửa cách giữ ngữ cảnh/người nói/nguồn của evidence; thêm kiểm thử hồi quy
   từ các loại lỗi đã biết. Dùng version/profile và output DEV riêng.
2. Chuẩn bị runner no-retrieval/LOCAL với model/verifier/scorer chung,
   manifests và cách đo nhất quán. Nhánh GRAPH phải ghi đúng trạng thái,
   không thêm số giả từ structure/term PageRank.
3. Chuẩn bị thiết kế tập chính, mẫu nhãn và semantic evidence audit. Không
   tự điền nhãn, người duyệt, quyền dùng hoặc điểm giảng viên.

## Còn thiếu cho kết luận chính của bài báo

- **Tập SEFORA chưa dùng sửa phương pháp và tham chiếu phù hợp:** nguồn/
  rubric đã có, còn cần xác định cohort/split, xử lý feedback đúng version
  và tạo/kiểm nhãn đúng nhiệm vụ. Không cần file R1/R2 để làm nhánh này.
  Muốn kết luận riêng trên báo cáo kỹ thuật thì cần dữ liệu miền đó.
- **Tham chiếu đúng yêu cầu:** nhãn và evidence/lý do theo cùng rule với
  verifier, có những trạng thái/loại checklist muốn kết luận. Không bắt
  người phụ trách gán lại toàn bộ 15 bài hoặc tự bắt buộc hai giám khảo;
  cách tạo tham chiếu phải khai thật và giới hạn kết luận tương ứng.
- **GRAPH ngữ nghĩa:** contract/store có sẵn, nhưng extraction quan hệ và
  tích hợp P2 thực sự chưa được chứng minh bằng nhánh chạy chính. Graph
  cấu trúc/từ chung hiện tại giữ vai trò baseline.
- **Mức đánh giá và điểm tham chiếu:** compiler hiện từ chối `levels`;
  chưa có điểm chuyên môn theo cùng rubric trong các pack đã kiểm. Không
  so ba checklist tự định nghĩa với tổng điểm khác rubric của SEFORA.
  Nếu dùng đúng rubric gốc và trục điểm nguồn của SEFORA, có thể tận dụng
  điểm đã có thay vì yêu cầu chấm lại mọi bài; phải kiểm mapping/scale và
  những mục cần ảnh/nguồn ngoài. Ba checklist text-only hiện không đại
  diện đầy đủ rubric gốc sáu tiêu chí, nên chưa làm phép so tổng điểm đó.
- **Độ đúng về ngữ nghĩa của rationale:** 179 proof đúng nguồn/offset chỉ
  là truy vết. Chưa có semantic-support audit đầy đủ của toàn bộ 90 quyết
  định; các quan sát từ mục bất đồng không tạo tỷ lệ lỗi toàn cohort.

## Hồ sơ tái tạo

Tất cả input được giữ nguyên. Thống kê và receipts nằm riêng tại:

- [Inventory JSON](../../var/paper/p2-main-study-preparation-2026-11-08/readiness-v1/inventory.json).
- [Kiểm chứng](../../var/paper/p2-main-study-preparation-2026-11-08/readiness-v1/verification.json).
- [Script kiểm kê](../../var/paper/p2-main-study-preparation-2026-11-08/readiness-v1/build_inventory.py).

Script chỉ đọc metadata có sẵn, aggregate của cohort đã dùng và hash file;
không đọc nội dung/điểm của bài mới, không chọn holdout, gọi model hay sửa
nhãn. Không ghi đè output: dùng output directory mới nếu tái kiểm tra.

```bash
python3 var/paper/p2-main-study-preparation-2026-11-08/readiness-v1/build_inventory.py \
  --output-dir var/paper/p2-main-study-preparation-2026-11-08/readiness-recheck-v2
```

Các thiếu sót dữ liệu không chặn việc sửa và kiểm thử DEV. Kế hoạch thực
hiện vẫn theo [toàn phạm vi đề tài](../planning/KE_HOACH_HOAN_THANH_PHAM_VI_DE_TAI.md).
