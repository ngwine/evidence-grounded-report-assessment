"""State and concurrency guards for the MongoDB queue adapter."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from bson import ObjectId
import mongomock
import pytest

from services.backend.src.kltn_ai.db.mongo_jobs import IdempotencyConflict, MongoJobQueue


BASE = datetime(2026, 10, 22, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def queue():
    collection = mongomock.MongoClient(tz_aware=True).kltn.jobs
    instance = MongoJobQueue(collection)
    instance.ensure_indexes()
    return instance


def enqueue(queue, *, key="one", workspace=None, max_attempts=3, priority=0):
    return queue.enqueue(
        workspace_id=workspace or ObjectId(), job_type="ANALYZE",
        resource_ref={"type": "DOCUMENT", "id": ObjectId(), "version_id": ObjectId()},
        config_ref=None, idempotency_scope="workspace:analysis", idempotency_key=key,
        correlation_id="test-correlation", max_attempts=max_attempts,
        priority=priority, now=BASE,
    )


def test_unique_idempotency_and_workspace_scoped_read(queue):
    workspace = ObjectId()
    original = enqueue(queue, workspace=workspace)
    same = queue.enqueue(
        workspace_id=workspace, job_type="ANALYZE",
        resource_ref=original["resource_ref"], config_ref=None,
        idempotency_scope="workspace:analysis", idempotency_key="one",
        correlation_id="another-request", now=BASE,
    )
    assert same["_id"] == original["_id"]
    assert queue.collection.count_documents({}) == 1
    with pytest.raises(IdempotencyConflict):
        enqueue(queue, key="one", workspace=ObjectId())
    assert queue.get(job_id=original["_id"], workspace_id=ObjectId()) is None
    assert queue.get(job_id=original["_id"], workspace_id=workspace) is not None


def test_claim_start_heartbeat_and_stale_worker_cannot_complete(queue):
    record = enqueue(queue)
    claimed = queue.claim(owner="worker-a", lease_seconds=10, now=BASE)
    assert claimed["_id"] == record["_id"]
    assert claimed["attempt"] == 1
    assert queue.claim(owner="worker-b", now=BASE) is None
    running = queue.start(job_id=record["_id"], owner="worker-a",
                          revision=claimed["revision"], now=BASE)
    assert running["state"] == "RUNNING"
    heartbeat = queue.heartbeat(job_id=record["_id"], owner="worker-a",
                                revision=running["revision"], lease_seconds=10,
                                now=BASE + timedelta(seconds=5))
    assert heartbeat["lease_expires_at"] == BASE + timedelta(seconds=15)
    assert queue.complete(job_id=record["_id"], owner="worker-a",
                          revision=running["revision"], now=BASE + timedelta(seconds=6)) is None
    reclaimed = queue.claim(owner="worker-b", lease_seconds=10,
                            now=BASE + timedelta(seconds=16))
    assert reclaimed["attempt"] == 2
    assert queue.complete(job_id=record["_id"], owner="worker-a",
                          revision=heartbeat["revision"], now=BASE + timedelta(seconds=16)) is None
    started = queue.start(job_id=record["_id"], owner="worker-b",
                          revision=reclaimed["revision"], now=BASE + timedelta(seconds=16))
    done = queue.complete(job_id=record["_id"], owner="worker-b",
                          revision=started["revision"], now=BASE + timedelta(seconds=17))
    assert done["state"] == "SUCCEEDED"
    assert queue.claim(owner="worker-c", now=BASE + timedelta(seconds=100)) is None


def test_retry_delay_and_finite_attempts(queue):
    record = enqueue(queue, max_attempts=2)
    first = queue.claim(owner="w", now=BASE)
    failed = queue.fail(job_id=record["_id"], owner="w",
                        revision=first["revision"], error_code="MODEL_TIMEOUT",
                        retryable=True, retry_delay_seconds=30, now=BASE)
    assert failed["state"] == "QUEUED"
    assert queue.claim(owner="w", now=BASE + timedelta(seconds=29)) is None
    second = queue.claim(owner="w", now=BASE + timedelta(seconds=30))
    assert second["attempt"] == 2
    final = queue.fail(job_id=record["_id"], owner="w",
                       revision=second["revision"], error_code="MODEL_TIMEOUT",
                       retryable=True, now=BASE + timedelta(seconds=31))
    assert final["state"] == "FAILED_FINAL"
    assert queue.claim(owner="w", now=BASE + timedelta(hours=1)) is None


def test_expired_final_lease_and_cancel_guard(queue):
    record = enqueue(queue, max_attempts=1)
    first = queue.claim(owner="w", lease_seconds=5, now=BASE)
    assert queue.claim(owner="other", now=BASE + timedelta(seconds=6)) is None
    assert queue.get(job_id=record["_id"], workspace_id=record["workspace_id"])["state"] == "FAILED_FINAL"
    assert queue.get(job_id=record["_id"], workspace_id=record["workspace_id"])["progress"] == {"step": "FAILED_FINAL"}
    assert queue.start(job_id=record["_id"], owner="w",
                       revision=first["revision"], now=BASE + timedelta(seconds=6)) is None
    cancellable = enqueue(queue, key="two")
    assert queue.cancel(job_id=cancellable["_id"], workspace_id=ObjectId(),
                        revision=cancellable["revision"], now=BASE) is None
    cancelled = queue.cancel(job_id=cancellable["_id"],
                             workspace_id=cancellable["workspace_id"],
                             revision=cancellable["revision"], now=BASE)
    assert cancelled["state"] == "CANCELLED"
    assert queue.claim(owner="w", now=BASE) is None


def test_queue_rejects_content_payload_and_unbounded_settings(queue):
    with pytest.raises(ValueError, match="resource_ref"):
        queue.enqueue(
            workspace_id=ObjectId(), job_type="ANALYZE",
            resource_ref={"type": "DOCUMENT", "id": ObjectId(),
                          "version_id": ObjectId(), "report_text": "private"},
            config_ref=None, idempotency_scope="x", idempotency_key="x",
            correlation_id="x", now=BASE,
        )
    with pytest.raises(ValueError, match="retry limit"):
        enqueue(queue, key="oversized", max_attempts=100)


@pytest.mark.parametrize("version", [True, False, 0, -1, 1.2, "1"])
def test_config_version_matches_bson_validator(queue, version):
    with pytest.raises(ValueError, match="config_ref"):
        queue.enqueue(
            workspace_id=ObjectId(), job_type="PARSE",
            resource_ref={"type": "DOCUMENT", "id": ObjectId(), "version_id": ObjectId()},
            config_ref={"id": ObjectId(), "version": version},
            idempotency_scope="x", idempotency_key="x", correlation_id="x",
        )


@pytest.mark.parametrize("options", [{"max_attempts": True}, {"priority": False},
                                     {"max_attempts": 1.5}, {"priority": 0.5}])
def test_queue_integer_settings_exclude_bool_and_float(queue, options):
    with pytest.raises(ValueError, match="retry limit"):
        enqueue(queue, **options)


@pytest.mark.parametrize("options", [{"owner": 12}, {"owner": None},
                                     {"owner": "w", "lease_seconds": True},
                                     {"owner": "w", "lease_seconds": 2.5}])
def test_claim_rejects_malformed_lease_settings(queue, options):
    with pytest.raises(ValueError):
        queue.claim(**options)
