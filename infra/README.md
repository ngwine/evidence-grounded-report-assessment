# Infrastructure

Thư mục dành cho Docker và cấu hình MongoDB. Chưa tạo `compose.yaml` vì
MongoDB deployment, Search/Vector Search và queue vẫn chờ OQ-04/G-02.

Không được mặc định một image MongoDB thông thường đã hỗ trợ cấu hình search
cần thiết. Mọi cấu hình được thêm sau phải có health check và được chạy thử
trên môi trường sạch trước khi ghi lệnh vào README gốc.

