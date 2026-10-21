# MongoDB queue slice (`W3.1`, `W3.6`)

`mongo_jobs.py` implements the `jobs` state transitions from ADR-001: unique
idempotency key, atomic claim with a bounded lease, revision-guarded heartbeat
and completion, finite retry, cancellation and the indexes used by those
operations. It writes only immutable resource/config references and safe error
codes. An expired worker cannot publish a terminal result after another worker
reclaims the job.

The adapter is independent of the local file-backed demo. A production worker
must still reload and authorize workspace, document version, current governance
decision and requested purpose **after claim**; it must stop processing after
a failed heartbeat or a cancellation. Upload transaction, checkpoint artifact
commit, MongoDB deployment, API authentication/RBAC, index rebuild and retention
are separate work packages and are not implied by this module.

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
