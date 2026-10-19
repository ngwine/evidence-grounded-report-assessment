# Backend service

FastAPI và worker là hai tiến trình nhưng dùng chung package `kltn_ai` để tránh
lặp model, policy và repository.

- `api`: HTTP routes, dependencies và error mapping.
- `core`: settings, auth, logging và security.
- `db`: MongoDB client, validators, indexes và migration/backfill.
- `modules`: nghiệp vụ theo feature (similarity, assessment, rubrics, feedback, ...).
- `integrations`: adapter parser, indexing, retrieval, graph, local AI, storage và provider.
- `worker`: task handlers cho Pipeline 1 (Similarity) và Pipeline 2 (Assessment),
  checkpoint, retry và idempotency.

API không chạy parse/AI dài trong request. Worker không có quyền tự công bố
điểm hoặc bỏ qua RBAC/evidence policy.

HTTP boundary dự kiến được mô tả tại
[`API_CONTRACT_V1.md`](../../docs/api/API_CONTRACT_V1.md) và
[`openapi-v1.yaml`](../../docs/api/openapi-v1.yaml). Đây là review candidate
`W2.3`, chưa phải bằng chứng endpoint đã được hiện thực.

