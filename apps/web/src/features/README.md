# Features

Mỗi feature tự chứa page/component/hook/API/types riêng khi cần. Chỉ đưa UI
thật sự dùng chung sang `src/components`; tránh tạo một thư mục component toàn
cục quá lớn.

| Feature | Mô tả |
|---|---|
| `auth` | Xác thực, đăng nhập |
| `reports` | Upload, xem và quản lý báo cáo |
| `similarity` | Similarity Report – kết quả Pipeline 1 |
| `rubrics` | Quản lý rubric đánh giá |
| `analysis` | Kết quả đánh giá dựa trên bằng chứng – Pipeline 2 |
| `review` | Lecturer Review – giảng viên xem xét và quyết định |
| `questions` | Câu hỏi vấn đáp có mục tiêu |
| `feedback` | Feedback Log – lịch sử chỉnh sửa |

