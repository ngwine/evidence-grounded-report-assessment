# Ghi chú trao đổi: dữ liệu rubric (UI vs data-dictionary vs rubric-v1.md)

Tài liệu ngắn ghi lại các điểm đã bàn giữa Yến và trợ lý khi đối chiếu
`docs/rubric/rubric-v1.md` với `docs/architecture/data-dictionary.md`
(mục 8 — Rubric), trước khi code hoá trong `apps/web`. Mục đích: để Quý
và GVHD cùng xem lại, xác nhận hoặc điều chỉnh.

## 1. Khoảng trống giữa data-dictionary.md và rubric-v1.md

`data-dictionary.md` mục 8.1/8.2 mô tả rubric ở mức rất tổng quát:

- `rubrics`: `workspace_id`, `rubric_key`, `title`, `current_version_id`, `lifecycle_state`.
- `rubric_versions`: `workspace_id`, `rubric_id`, `version_no`, `status`,
  `criteria[]` với `criteria[].criterion_key`, `criteria[].weight`,
  `criteria[].checklists[]` ("Atomic condition/evidence/mode"),
  `criteria[].levels[]` ("Score rule/example").

`rubric-v1.md` yêu cầu chi tiết hơn, và có 3 điểm dictionary hiện
**chưa có chỗ chứa**:

1. **Tên mức dùng chung cho mọi tiêu chí** (2-6 mức, ví dụ
   Tốt/Khá/Trung bình/Yếu) — đây là khái niệm ở cấp `rubric_versions`,
   không phải cấp từng `criteria[]`. Dictionary hiện không có field nào ở
   cấp version cho việc này.
2. **Nhãn độ quan trọng của checklist** (Cốt lõi / Bắt buộc / Không bắt
   buộc) — dictionary chỉ ghi "Atomic condition/evidence/mode", không có
   chỗ cho nhãn này.
3. **Cấu trúc `[min, max]` theo từng tiêu chí/từng mức** + 3 ràng buộc số
   học (range nằm trong [0, weight]; mức cao nhất max = đúng weight;
   range giảm dần không chồng lắp) — dictionary chỉ ghi "Score rule/
   example", không đủ chi tiết.

Đây không phải là **mâu thuẫn** (dictionary viết chung nên không cấm gì
cả), mà là **chưa đủ chi tiết**. Đề xuất: bổ sung 1 bảng con dưới mục 8.2
liệt kê rõ sub-field của `criteria[].levels[]`, `criteria[].checklists[]`,
và thêm field `level_names` ở cấp `rubric_versions`.

## 2. Các quyết định đã thống nhất (trong UI tạo rubric)

- **Nhãn độ quan trọng checklist**: hệ thống tự gán dựa vào **từ khóa**
  trong nội dung tiêu chí/checklist. Mặc định là **Bắt buộc** (vì "thường
  thì mọi tiêu chí đều bắt buộc nếu không có gì đặc biệt trong câu từ nội
  dung tiêu chí" — theo Yến). GV luôn sửa lại nhãn này được.
  - Bộ từ khóa cụ thể hiện là **GIẢ ĐỊNH để demo** (xem
    `lib/api.ts` — `CORE_KEYWORDS`/`OPTIONAL_KEYWORDS`): chứa "phải có",
    "bắt buộc tuyệt đối", "cần phải"... → Cốt lõi; chứa "nên", "khuyến
    khích", "tùy chọn", "có thể"... → Không bắt buộc; còn lại → Bắt buộc.
  - **Cần Quý/GVHD chốt lại bộ từ khóa thật** trước khi dùng thật.
- **Tổng trọng số rubric KHÔNG cố định** ở 10 hay 100. GV tự quyết định
  theo đúng thang điểm gốc của môn (ví dụ môn chấm thang 6 thì tổng trọng
  số các tiêu chí = 6, tiêu chí này chiếm 1, tiêu chí kia chiếm 2...). UI
  chỉ hiển thị tổng hiện tại để GV tự theo dõi, không chặn nhập.
- **Cách nhập [min,max] theo kiểu "điểm chia" (breakpoint)**: GV không tự
  nhập min/max hay nửa-mở/nửa-đóng. GV chỉ nhập (số mức - 1) điểm chia
  giữa các mức liền kề, giảm dần, hệ thống tự suy ra [min,max] + quy ước
  đóng/hở đầu theo đúng ví dụ ở `rubric-v1.md` mục 2 (mức cao nhất đóng cả
  2 đầu vì max = weight; các mức còn lại đóng ở min, hở ở max).

## 3. Điểm còn mở, cần Quý/GVHD xác nhận

1. Bộ từ khóa cụ thể để tự gán nhãn độ quan trọng checklist (mục 2, gạch
   đầu dòng 1) — bộ hiện tại chỉ để demo UI.
2. Cách nhập breakpoint ở trên có phải cách GV sẽ dùng thật không, hay
   cần UI khác (ví dụ nhập min/max trực tiếp).
3. Khi GV override kết quả tự động ở bước adjudication (`rubric-v1.md`
   mục 7), có cần lưu thêm gì ở `rubric_versions` không, hay để nguyên
   `reviews.decision` (ACCEPT/EDIT/REJECT) xử lý như data-dictionary đã
   có sẵn.

## 4. Trạng thái code (apps/web)

Đã cập nhật theo thiết kế ở mục 2 (đánh dấu GIẢ ĐỊNH trong comment code
ở những chỗ chưa được dictionary xác nhận):

- `src/lib/types.ts`: `RubricCriterionLevel` đổi thành `{min, max}`;
  thêm `level_names: string[]` vào `RubricVersion`; thêm
  `ChecklistImportance` + field `importance` vào `RubricChecklistItem`;
  `CreateRubricParams` đổi `levels[]` (score+description) thành
  `levelNames` (chung) + `breakpoints[]` (theo từng tiêu chí).
- `src/lib/api.ts`: `compileRubricChecklist` suy ra `[min,max]` từ
  breakpoints (`levelsFromBreakpoints`) và tự đoán `importance` theo từ
  khóa (`guessImportance`); `createRubric` lưu `level_names` vào
  `rubric_versions`.
- `src/features/rubrics/RubricCreatePage.tsx` + `rubrics.css`: viết lại
  bước 1 để GV chọn số mức (2-6) + đặt tên mức chung, mỗi tiêu chí chỉ
  nhập trọng số + điểm chia; bước 2 thêm cột chọn nhãn độ quan trọng cho
  từng checklist.
