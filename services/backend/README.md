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

## Local two-pipeline demo (provisional)

The first integrated slice lives at `/api/local/v1`, deliberately separate
from the reviewed `/api/v1` design. It uses a private file-backed queue in
`var/app-local/`; it does **not** implement MongoDB, account login, authenticated
lecturer review, publication, or an official grade/plagiarism verdict. Bind the
API to loopback only. Report, source, rubric and output bytes stay in ignored
`var/` with private file permissions; do not commit these inputs/results.

Install once from the repository root:

```bash
.venv-research/bin/python -m pip install -r services/backend/requirements-app.txt
```

Before submitting a comparison source, an authorized operator must check its
right to be used in a *private local test* and approve its exact SHA-256. This
is not a public-data license clearance. Sources still marked `PENDING` must
not be approved merely to make the demo run.

```bash
.venv-research/bin/python -m services.backend.src.kltn_ai.local_approvals \
  approve-source path/to/authorized-source.pdf \
  --approver "operator name" \
  --rationale "Basis for this private local test" \
  --attest-rights
```

Run the worker and API in separate terminals from the repository root:

```bash
HF_HOME=var/models/hf-home \
TRANSFORMERS_OFFLINE=1 \
HF_HUB_OFFLINE=1 \
TOKENIZERS_PARALLELISM=false \
.venv-research/bin/python -m services.backend.src.kltn_ai.worker.local_worker
.venv-research/bin/python -m uvicorn \
  services.backend.src.kltn_ai.api.local_app:app \
  --host 127.0.0.1 --port 8001
```

The API accepts `POST /api/local/v1/runs` as multipart `report`, repeated
`sources`, `rubric` (JSON), and optional `config_id`. `GET /api/local/v1/runs/{id}`
polls the job and exposes both evidence reports on success. A review decision
is stored by `POST /api/local/v1/runs/{id}/review` with `decision`, `comment`,
`expected_revision`, and `reviewer_name`; it remains an **unverified local demo
record** and never publishes or assigns an official grade. Unapproved sources
are rejected before queueing, and the worker checks approval before and after
processing. Results are withheld if approval is later revoked. Both POST
routes require `X-KLTN-Local-UI: 1` as a basic browser CSRF barrier alongside
loopback, Host and Origin checks. This header is **not** user authentication;
the local `reviewer_name` is user-entered text.

`bm25-smoke` (default) turns Dense, RRF, and Cross-Encoder off so the complete
upload → worker → result → review flow can be checked quickly with synthetic
fixtures. `research-v0` copies the locked `research/configs/core-mvp-v0.json`
into the run and loads the local E5 and mMARCO model revisions from
`var/models/hf-home`. Both revisions must be present before starting the
worker in offline mode; otherwise the job fails with a model-load error in
the local worker log. It is the research-method path but may require
substantial model setup/time. Neither
mode is scientifically validated or safe for unattended decisions.
There is no automatic retention policy in this provisional local queue;
the operator must manage private `var/app-local/` data after the demo.

```bash
.venv-research/bin/python -m pytest -q services/backend/tests/test_local_app.py
```
