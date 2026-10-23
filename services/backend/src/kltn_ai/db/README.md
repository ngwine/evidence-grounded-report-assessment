# MongoDB queue slice (`W3.1`, `W3.6`)

Executable schema/roles baseline ở
[`mongodb-executable-baseline.md`](../../../../../docs/architecture/mongodb-executable-baseline.md).
Migration cài job indexes; runtime API/worker không có quyền `createIndex`,
nên không gọi `ensure_indexes()` bằng runtime credential.
[Authenticated app](../../../../../docs/architecture/authenticated-mongo-app.md)
đã nối upload → PARSE worker → MongoDB, tách biệt demo local cũ;
database role không thay thế actor/workspace authorization.

[Index và analysis](../../../../../docs/architecture/version-locked-analysis-app.md)
đã nối tiếp bằng migration004: index_generations/heads/operations,
analysis_runs/results/operations, evidence_items và reviews. Worker lưu AI
outputs; API chỉ đọc và ghi review/command, không ghi analysis_results/evidence.
Immutable payload và current scope được service kiểm, không chỉ dựa validator.

`mongo_jobs.py` implements the `jobs` state transitions from ADR-001: unique
idempotency key, atomic claim with a bounded lease, revision-guarded heartbeat
and completion, finite retry, cancellation and the indexes used by those
operations. It writes only immutable resource/config references and safe error
codes. An expired worker cannot publish a terminal result after another worker
reclaims the job.

The adapter is independent of the local file-backed demo. `MongoParseWorker`
now reloads workspace, ownership, document/version and current/pinned governance
after claim and before its transaction-fenced generation commit. Auth/session,
rubric and document catalogs are additive migrations 002/003; migration 001's
checksum stays fixed. INDEX/ANALYZE now have durable type-scoped handlers and
transaction-fenced index/result commits. Graph, full retention/purge and
backup/restore remain separate work packages.

`ensure_indexes()` belongs in a migration/setup command using migration
credentials; do not call it per request. The tests use `mongomock` to exercise
state transitions without a database server:

```bash
.venv-research/bin/python -m pytest services/backend/tests/test_mongo_jobs.py -q
```

Before wiring this adapter into `/api/v1`, run a separate integration suite
against the pinned single-node replica set from ADR-001. That suite must cover
real concurrent claims, restart/lease expiry, majority write concern and the
file-metadata transaction boundary.
