"""Optional real-MongoDB queue test; set KLTN_MONGO_TEST_URI to run it."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import os
from uuid import uuid4

from bson import ObjectId
from pymongo import MongoClient
from pymongo.errors import OperationFailure
from pymongo.write_concern import WriteConcern
import pytest

from services.backend.src.kltn_ai.db.mongo_jobs import MongoJobQueue


def test_real_mongo_atomic_claim_and_stale_lease() -> None:
    uri = os.environ.get("KLTN_MONGO_TEST_URI")
    if not uri:
        pytest.skip("Set KLTN_MONGO_TEST_URI for the real MongoDB test")
    client = MongoClient(uri, serverSelectionTimeoutMS=3000, tz_aware=True)
    # The caller must supply a dedicated test server. This unique database is
    # the only state this test creates or removes.
    database_name = f"kltn_queue_test_{uuid4().hex}"
    database = client[database_name]
    queue = MongoJobQueue(database.jobs)
    instant = datetime(2026, 10, 22, tzinfo=timezone.utc)
    try:
        client.admin.command("ping")
        queue.ensure_indexes()
        job = queue.enqueue(
            workspace_id=ObjectId(), job_type="ANALYZE",
            resource_ref={"type": "DOCUMENT", "id": ObjectId(), "version_id": ObjectId()},
            config_ref=None, idempotency_scope="test", idempotency_key="same",
            correlation_id="test", max_attempts=2, now=instant,
        )
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(
                lambda owner: queue.claim(owner=owner, lease_seconds=5, now=instant),
                ("worker-a", "worker-b"),
            ))
        claimed = [item for item in results if item is not None]
        assert len(claimed) == 1
        first = claimed[0]
        reclaimed = queue.claim(owner="worker-c", lease_seconds=5,
                                now=instant + timedelta(seconds=6))
        assert reclaimed is not None and reclaimed["attempt"] == 2
        assert queue.start(job_id=job["_id"], owner=first["lease_owner"],
                           revision=first["revision"], now=instant + timedelta(seconds=6)) is None
        running = queue.start(job_id=job["_id"], owner="worker-c",
                              revision=reclaimed["revision"], now=instant + timedelta(seconds=6))
        assert running is not None
        done = queue.complete(job_id=job["_id"], owner="worker-c",
                              revision=running["revision"], now=instant + timedelta(seconds=7))
        assert done is not None and done["state"] == "SUCCEEDED"
    finally:
        client.drop_database(database_name)
        client.close()


def test_replica_set_transactions_majority_writes_and_unauthenticated_denial() -> None:
    uri = os.environ.get("KLTN_MONGO_TEST_URI")
    if not uri:
        pytest.skip("Set KLTN_MONGO_TEST_URI for the real MongoDB test")
    client = MongoClient(uri, serverSelectionTimeoutMS=3000)
    name = f"kltn_transaction_test_{uuid4().hex}"
    database = client.get_database(name, write_concern=WriteConcern(w="majority", wtimeout=3000))
    try:
        hello = client.admin.command("hello")
        assert hello.get("setName") == "kltn-rs"
        assert client.server_info()["version"].startswith("8.0.")
        database.create_collection("records")
        with client.start_session() as session:
            with session.start_transaction(write_concern=WriteConcern(w="majority")):
                database.records.insert_one({"_id": "committed"}, session=session)
            session.start_transaction()
            database.records.insert_one({"_id": "aborted"}, session=session)
            session.abort_transaction()
        assert database.records.find_one({"_id": "committed"}) is not None
        assert database.records.find_one({"_id": "aborted"}) is None
        assert client.address is not None
        with MongoClient(host=client.address[0], port=client.address[1],
                         directConnection=True, serverSelectionTimeoutMS=3000) as anonymous:
            with pytest.raises(OperationFailure) as error:
                anonymous[name].records.find_one({})
            assert error.value.code == 13
    finally:
        client.drop_database(name)
        client.close()
