"""Optional live validator, migration and database privilege negative tests.

Only unique test databases/users/roles created here are removed in cleanup.
Credentials never enter an artifact, test assertion or printed command.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
import secrets
from uuid import uuid4

from bson import ObjectId
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError, OperationFailure, WriteError
import pytest

from services.backend.src.kltn_ai.db.migrations import LOCK_ID, MIGRATION_ID, MigrationError, apply_schema_v1
from services.backend.src.kltn_ai.db.mongo_jobs import MongoJobQueue
from services.backend.src.kltn_ai.db.roles import provision_roles


def _apply(database):
    return apply_schema_v1(database, code_commit="0" * 40, applied_by="synthetic-test")


@pytest.fixture
def live_database():
    uri = os.environ.get("KLTN_MONGO_TEST_URI")
    if not uri:
        pytest.skip("Set KLTN_MONGO_TEST_URI for live schema/role tests")
    with MongoClient(uri, serverSelectionTimeoutMS=3000, tz_aware=True) as client:
        database = client["kltn_schema_test_" + uuid4().hex]
        try:
            yield database
        finally:
            for user in database.command("usersInfo")["users"]:
                database.command("dropUser", user["user"])
            for role in database.command("rolesInfo")["roles"]:
                database.command("dropRole", role["role"])
            client.drop_database(database.name)


def _common() -> dict:
    now = datetime.now(timezone.utc)
    return {"_id": ObjectId(), "schema_version": 1, "created_at": now,
            "created_by": None, "updated_at": now, "updated_by": None, "revision": 1}


def _user() -> dict:
    return {**_common(), "email_normalized": "synthetic@example.invalid",
            "display_name": "Synthetic fixture", "system_roles": [], "status": "ACTIVE"}


def test_live_schema_reapply_unique_validator_and_queue(live_database) -> None:
    database = live_database
    first = _apply(database)
    original_entry = database.schema_migrations.find_one({"_id": MIGRATION_ID})
    assert _apply(database) == first
    assert database.schema_migrations.count_documents({"_id": MIGRATION_ID}) == 1
    after = database.schema_migrations.find_one({"_id": MIGRATION_ID})
    assert after["applied_at"] == original_entry["applied_at"]
    assert after["last_verified_at"] >= original_entry["last_verified_at"]
    user = _user()
    database.users.insert_one(user)
    with pytest.raises(DuplicateKeyError):
        database.users.insert_one({**user, "_id": ObjectId()})
    with pytest.raises(WriteError) as error:
        database.users.insert_one({**_user(), "system_roles": ["LECTURER"]})
    assert error.value.code == 121
    with pytest.raises(WriteError) as error:
        database.users.update_one({"_id": user["_id"]}, {"$set": {"password": "not-allowed"}})
    assert error.value.code == 121
    queue = MongoJobQueue(database.jobs)
    job = queue.enqueue(workspace_id=ObjectId(), job_type="PARSE",
                        resource_ref={"type": "DOCUMENT", "id": ObjectId(), "version_id": ObjectId()},
                        config_ref=None, idempotency_scope="synthetic", idempotency_key="one",
                        correlation_id="req-synthetic")
    claimed = queue.claim(owner="synthetic-worker")
    assert claimed is not None
    running = queue.start(job_id=job["_id"], owner="synthetic-worker", revision=claimed["revision"])
    assert running is not None
    done = queue.complete(job_id=job["_id"], owner="synthetic-worker", revision=running["revision"])
    assert done is not None and done["state"] == "SUCCEEDED"


def test_live_migration_preflight_and_fencing(live_database) -> None:
    database = live_database
    database.users.insert_one({"_id": ObjectId(), "invalid": True})
    with pytest.raises(MigrationError, match="Existing documents fail"):
        _apply(database)
    assert "validator" not in database.users.options()
    assert database.schema_migrations.count_documents({"_id": MIGRATION_ID}) == 0
    database.schema_migrations.update_one(
        {"_id": LOCK_ID}, {"$set": {"lease_owner": "another-migrator",
                                    "lease_expires_at": datetime.now(timezone.utc) + timedelta(minutes=5)}},
    )
    with pytest.raises(MigrationError, match="holds the lease"):
        _apply(database)


def test_live_unique_preflight_and_checksum_drift(live_database) -> None:
    database = live_database
    database.users.insert_many([_user(), _user()])
    with pytest.raises(MigrationError, match="Duplicate values"):
        _apply(database)
    assert "validator" not in database.users.options()
    # Remove only one synthetic duplicate created by this test to retry.
    database.users.delete_one({"_id": database.users.find_one({})["_id"]})
    _apply(database)
    database.schema_migrations.update_one({"_id": MIGRATION_ID}, {"$set": {"checksum": "0" * 64}})
    with pytest.raises(MigrationError, match="checksum mismatch"):
        _apply(database)


def test_live_roles_restrict_api_worker_and_migration(live_database) -> None:
    database = live_database
    _apply(database)
    provision_roles(database)
    provision_roles(database)
    assert database.client.address is not None
    host, port = database.client.address
    for name, role in (("synthetic_api", "kltn_api"), ("synthetic_worker", "kltn_worker"),
                       ("synthetic_migrator", "kltn_migration")):
        password = secrets.token_urlsafe(32)
        database.command("createUser", name, pwd=password, roles=[{"role": role, "db": database.name}])
        with MongoClient(host=host, port=port, username=name, password=password,
                         authSource=database.name, directConnection=True,
                         serverSelectionTimeoutMS=3000, tz_aware=True) as runtime:
            scoped = runtime[database.name]
            assert scoped.users.find_one({"_id": ObjectId()}) is None
            if role == "kltn_migration":
                assert _apply(scoped)["status"] == "APPLIED"
                denied = lambda: scoped.command("createUser", "forbidden", pwd=secrets.token_urlsafe(32), roles=[])
            elif role == "kltn_worker":
                scoped.evidence_items.insert_one({"_id": ObjectId(), "synthetic": True})
                denied = lambda: scoped.users.insert_one(_user())
                with pytest.raises(OperationFailure) as error:
                    scoped.publications.insert_one({"_id": ObjectId()})
                assert error.value.code == 13
                with pytest.raises(OperationFailure) as error:
                    scoped.reviews.find_one({})
                assert error.value.code == 13
            else:
                scoped.users.insert_one(_user())
                denied = lambda: scoped.evidence_items.insert_one({"_id": ObjectId()})
            with pytest.raises(OperationFailure) as error:
                denied()
            assert error.value.code == 13
            if role != "kltn_migration":
                for action in (
                    lambda: scoped.command("collMod", "users", validationAction="warn"),
                    lambda: scoped.users.create_index("status"),
                    lambda: scoped.users.delete_many({}),
                    lambda: scoped.audit_events.update_one({}, {"$set": {"changed": True}}),
                ):
                    with pytest.raises(OperationFailure) as error:
                        action()
                    assert error.value.code == 13
                with pytest.raises(OperationFailure) as error:
                    runtime[database.name + "_other"].users.find_one({})
                assert error.value.code == 13
