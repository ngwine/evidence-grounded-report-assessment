# Feedback – Ghi nhận phản hồi giảng viên

Module quản lý **Feedback Log** – ghi nhận mọi chỉnh sửa, chấp nhận hoặc loại
bỏ của giảng viên đối với kết quả hệ thống.

## Trách nhiệm

- Lưu trữ Feedback Log: giảng viên chấp nhận, chỉnh sửa hoặc loại bỏ nhận xét
  và điểm số đề xuất.
- Mỗi entry ghi nhận: kết quả gốc của hệ thống, hành động của giảng viên,
  giá trị sau chỉnh sửa, timestamp và lý do (tùy chọn).
- Phục vụ phân tích sai số giữa kết quả hệ thống và đánh giá thực tế.
- Cung cấp dữ liệu cho đánh giá thực nghiệm và cải tiến hệ thống về sau.

## Ranh giới

- Chỉ ghi nhận dữ liệu; **không** thay đổi logic đánh giá của `assessment` hoặc
  `similarity`.
- Giảng viên phải có quyền tương ứng (RBAC) để tạo feedback entry.

## Cấu trúc dự kiến

```
feedback/
├── schemas.py        # FeedbackEntry, FeedbackAction enum
├── service.py        # FeedbackService
├── repository.py     # CRUD feedback logs
└── policy.py         # Quyền tạo/xem feedback
```
