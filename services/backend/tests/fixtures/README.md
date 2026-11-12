# Safe upload fixtures

Hai tệp trong thư mục này là dữ liệu tổng hợp, không phải báo cáo sinh viên và
không chứa thông tin cá nhân. Chúng được commit để kiểm tra parser, provenance,
upload validation và golden benchmark trên cùng nội dung có kiểm soát.

| Tệp | SHA-256 | Vai trò kiểm thử |
|---|---|---|
| `sample_thesis.pdf` | `8489b80e453e7a1ee181619ea8412c2ea5ade9ae0c956d5981d9fcbb9046f1b8` | Chữ ký PDF, page/span, layout hai trang |
| `sample_thesis.docx` | `59cd8b266fb60ac857a6bfc138ff9985c1285c007da8ca7c0333c8da3a80b81e` | DOCX container, heading/paragraph/table |

Expected structure và output digest được khóa riêng tại
`../golden/parser_chunking_v1/manifest.json`. Thay fixture hoặc expected output
phải qua review như một thay đổi benchmark; test không tự ghi đè manifest.

Các case input lỗi (sai signature, DOCX hỏng, UTF-8 chứa NUL, duplicate source,
report trùng source và rubric không hợp lệ) được tạo trong bộ test để tránh lưu
thêm binary độc hại trong repository.
