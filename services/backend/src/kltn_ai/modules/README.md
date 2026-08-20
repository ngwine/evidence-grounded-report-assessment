# Business modules

Mỗi module sở hữu schema nghiệp vụ, service/policy và repository interface của
mình. Không gọi trực tiếp adapter ngoài từ route; route đi qua service/use case.

## Danh sách module

| Module | Vai trò |
|---|---|
| `auth` | Xác thực, phân quyền (RBAC) |
| `reports` | Upload, parse, quản lý báo cáo PDF/DOCX |
| `references` | Quản lý kho tài liệu nguồn đối chứng |
| `similarity` | **Pipeline 1** – Phát hiện nội dung tương đồng |
| `rubrics` | Quản lý rubric giảng viên (template, tiêu chí, trọng số) |
| `assessment` | **Pipeline 2** – Đánh giá báo cáo dựa trên bằng chứng |
| `reviews` | Lecturer Review – xem xét và quyết định cuối cùng |
| `questions` | Sinh câu hỏi vấn đáp có mục tiêu |
| `feedback` | Feedback Log – ghi nhận chỉnh sửa giảng viên |
| `datasets` | Quản lý metadata dataset thực nghiệm trong DB |
| `analysis` | Shared analysis logic dùng chung cho nhiều pipeline |

