"""Additive, idempotent and fenced Mongo schema migration for controlled local use.

Pause application writers first. No documents are repaired, deleted or dropped.
An existing invalid document aborts before any collection validator is changed.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
import time
from typing import Any
from uuid import uuid4

from pymongo import ReturnDocument
from pymongo.database import Database
from pymongo.errors import CollectionInvalid, DuplicateKeyError
from pymongo.write_concern import WriteConcern

from .schema import INDEXES, VALIDATORS


MIGRATION_ID = "001-identity-and-job-validators-v1"
LOCK_ID = "__lock__"
LEASE_SECONDS = 300


class MigrationError(RuntimeError):
    """Safe migration failure; never includes documents or credentials."""


def schema_checksum() -> str:
    payload = json.dumps({"validators": VALIDATORS, "indexes": INDEXES}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def _check_indexes(database: Database[dict[str, Any]], name: str, *, require_all: bool) -> None:
    present = {item["name"]: item for item in database[name].list_indexes()}
    for expected in INDEXES[name]:
        actual = present.get(expected["name"])
        if actual is None:
            if require_all:
                raise MigrationError(f"Missing expected index in {name}")
            continue
        if (list(actual["key"].items()) != list(expected["key"].items())
                or bool(actual.get("unique", False)) != bool(expected.get("unique", False))
                or bool(actual.get("sparse", False))
                or actual.get("partialFilterExpression") != expected.get("partialFilterExpression")
                or actual.get("expireAfterSeconds") != expected.get("expireAfterSeconds")
                or actual.get("collation", {}).get("locale", "simple") != "simple"):
            raise MigrationError(f"Index options drift in {name}; no automatic drop/rebuild")


def apply_schema_v1(
    database: Database[dict[str, Any]], *, code_commit: str, applied_by: str,
) -> dict[str, str]:
    """Run against a maintenance database using migration/admin credentials.

    A five-minute renewable lease coordinates maintenance clients. DDL commands
    have a thirty-second server limit. Retry after a crash resumes additive operations.
    Migration source checksum changes under the same ID are rejected.
    This is NOT atomic DDL fencing: a suspended admin process can resume after
    losing its lease. Operators must stop old migrators before resuming a run.
    """

    if database.name in {"admin", "config", "local"}:
        raise ValueError("Never migrate MongoDB system databases")
    if (not re.fullmatch(r"[0-9a-f]{40,64}", code_commit)
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", applied_by)):
        raise ValueError("Explicit code commit and safe operator identifier are required")
    started = time.monotonic()
    database = database.with_options(write_concern=WriteConcern(w="majority", wtimeout=30000))
    ledger = database.schema_migrations
    owner = uuid4().hex
    now = datetime.now(timezone.utc)
    try:
        ledger.insert_one({
            "_id": LOCK_ID, "kind": "LOCK",
            "lease_owner": None, "lease_expires_at": now, "revision": 0,
        })
    except DuplicateKeyError:
        pass
    lock = ledger.find_one_and_update(
        {"_id": LOCK_ID, "lease_expires_at": {"$lte": now}},
        {"$set": {"lease_owner": owner, "lease_expires_at": now + timedelta(seconds=LEASE_SECONDS)},
         "$inc": {"revision": 1}}, return_document=ReturnDocument.AFTER,
    )
    if lock is None:
        raise MigrationError("Another migration holds the lease")

    def renew() -> None:
        instant = datetime.now(timezone.utc)
        result = ledger.update_one(
            {"_id": LOCK_ID, "lease_owner": owner, "revision": lock["revision"],
             "lease_expires_at": {"$gt": instant}},
            {"$set": {"lease_expires_at": instant + timedelta(seconds=LEASE_SECONDS)}},
        )
        if result.matched_count != 1:
            raise MigrationError("Migration lease lost; retry from a fresh process")

    checksum = schema_checksum()
    try:
        existing = ledger.find_one({"_id": MIGRATION_ID})
        if existing is not None and existing.get("checksum") != checksum:
            raise MigrationError("Migration checksum mismatch; add a new migration version")
        names = set(database.list_collection_names())
        for name, validator in VALIDATORS.items():
            renew()
            if name in names and database[name].find_one(
                {"$nor": [validator]}, projection={"_id": 1}, max_time_ms=30000,
            ) is not None:
                raise MigrationError(f"Existing documents fail validator in {name}; no automatic repair")
            if name in names:
                _check_indexes(database, name, require_all=False)
                for index in INDEXES[name]:
                    if not index.get("unique"):
                        continue
                    pipeline = []
                    if "partialFilterExpression" in index:
                        pipeline.append({"$match": index["partialFilterExpression"]})
                    pipeline.extend([
                        {"$group": {"_id": {str(i): {"$ifNull": ["$" + field, None]}
                                               for i, field in enumerate(index["key"])},
                                    "count": {"$sum": 1}}},
                        {"$match": {"count": {"$gt": 1}}}, {"$limit": 1},
                    ])
                    if next(database[name].aggregate(pipeline, maxTimeMS=30000), None) is not None:
                        raise MigrationError(f"Duplicate values block a unique index in {name}; no automatic repair")
        for name, validator in VALIDATORS.items():
            renew()
            if name not in names:
                try:
                    database.create_collection(name, validator=validator,
                                               validationLevel="strict", validationAction="error")
                except CollectionInvalid:
                    # Another administrative client could create the collection;
                    # collMod below still applies the exact versioned validator.
                    pass
            renew()
            database.command({"collMod": name, "validator": validator,
                              "validationLevel": "strict", "validationAction": "error",
                              "maxTimeMS": 30000})
            renew()
            database.command({"createIndexes": name, "indexes": INDEXES[name], "maxTimeMS": 30000})
            renew()
            options = database[name].options()
            if (options.get("validator") != validator or options.get("validationLevel") != "strict"
                    or options.get("validationAction") != "error"):
                raise MigrationError(f"Validator read-back failed in {name}")
            _check_indexes(database, name, require_all=True)
        renew()
        applied = datetime.now(timezone.utc)
        duration = round((time.monotonic() - started) * 1000)
        ledger.update_one(
            {"_id": MIGRATION_ID},
            {"$setOnInsert": {"created_at": now, "kind": "ENTRY",
                       "checksum": checksum, "status": "APPLIED", "applied_at": applied,
                       "description": "Identity and queue shape/index baseline; four collections only",
                       "applied_by": applied_by, "code_commit": code_commit,
                       "duration_ms": duration,
                       "verification_summary": {"validated_collections": sorted(VALIDATORS),
                                                "validator_and_index_readback": True}},
             "$set": {"last_verified_at": applied, "last_verified_by": applied_by,
                      "last_verified_code_commit": code_commit,
                      "last_verification_duration_ms": duration}}, upsert=True,
        )
        return {"migration_id": MIGRATION_ID, "checksum": checksum, "status": "APPLIED"}
    finally:
        ledger.update_one(
            {"_id": LOCK_ID, "lease_owner": owner, "revision": lock["revision"]},
            {"$set": {"lease_owner": None, "lease_expires_at": datetime.now(timezone.utc)}},
        )
