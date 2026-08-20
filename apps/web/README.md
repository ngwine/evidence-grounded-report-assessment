# Web

Frontend dự kiến dùng React, Vite và TypeScript. Chỉ khởi tạo `package.json`
và source code sau khi chốt wireframe/API ở W02.

- `src/app`: bootstrap, router, providers và layout.
- `src/features`: code theo nghiệp vụ như auth, reports, analysis và review.
- `src/components`: UI dùng chung, không chứa nghiệp vụ riêng của feature.
- `src/lib`: API client, helpers và cấu hình frontend.

Frontend chỉ gọi API; không truy cập MongoDB, model hoặc Search Provider trực tiếp.

