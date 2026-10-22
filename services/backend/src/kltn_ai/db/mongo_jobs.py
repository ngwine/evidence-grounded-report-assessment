"""MongoDB queue lease transitions for the W2.2 storage design.

Only immutable references enter the queue. The caller must authorize the
workspace, purpose and resource version before enqueue and again after claim.
This adapter is not wired to the provisional localhost API.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
from typing import Any, Mapping

from bson import ObjectId
from pymongo import ASCENDING, DESCENDING, ReturnDocument
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError


JOB_TYPES = frozenset({"PARSE", "INDEX", "ANALYZE", "DELETE"})
ACTIVE_STATES = ("QUEUED", "CLAIMED", "RUNNING")
SAFE_ERROR_CODE = re.compile(r"[A-Z][A-Z0-9_]{0,63}\Z")


class IdempotencyConflict(ValueError):
    """One key was reused for different immutable input."""


def _utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("now must include timezone")
    return value.astimezone(timezone.utc)


class MongoJobQueue:
    """Atomic revision-and-lease guarded transitions over ``jobs``."""

    def __init__(self, collection: Collection[dict[str, Any]]) -> None:
        self.collection = collection

    def ensure_indexes(self) -> None:
        self.collection.create_index(
            [("idempotency_scope", ASCENDING), ("idempotency_key", ASCENDING)],
            unique=True, name="uq_job_idempotency",
        )
        self.collection.create_index(
            [("state", ASCENDING), ("available_at", ASCENDING),
             ("priority", DESCENDING), ("created_at", ASCENDING)], name="ix_job_claim",
        )
        self.collection.create_index(
            [("state", ASCENDING), ("lease_expires_at", ASCENDING)],
            name="ix_job_expired_lease",
        )
        self.collection.create_index(
            [("workspace_id", ASCENDING), ("resource_ref.id", ASCENDING),
             ("created_at", DESCENDING)], name="ix_job_workspace_resource",
        )

    def enqueue(
        self, *, workspace_id: ObjectId, job_type: str,
        resource_ref: Mapping[str, Any], config_ref: Mapping[str, Any] | None,
        idempotency_scope: str, idempotency_key: str, correlation_id: str,
        max_attempts: int = 3, priority: int = 0, created_by: ObjectId | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        if not isinstance(workspace_id, ObjectId) or job_type not in JOB_TYPES:
            raise ValueError("Invalid workspace or job type")
        if set(resource_ref) != {"type", "id", "version_id"} or (
            resource_ref["type"] not in {"DOCUMENT", "INDEX_GENERATION", "ANALYSIS_RUN"}
            or not isinstance(resource_ref["id"], ObjectId)
            or not isinstance(resource_ref["version_id"], ObjectId)
        ):
            raise ValueError("resource_ref needs type, id and immutable version_id")
        if config_ref is not None and (
            set(config_ref) != {"id", "version"}
            or not isinstance(config_ref["id"], ObjectId)
            or type(config_ref["version"]) is not int or config_ref["version"] < 1
        ):
            raise ValueError("config_ref needs id and integer version")
        if (type(max_attempts) is not int or type(priority) is not int
                or not 1 <= max_attempts <= 10 or not -10 <= priority <= 10):
            raise ValueError("Invalid retry limit or priority")
        if not all(isinstance(value, str) and 1 <= len(value) <= 128 for value in
                   (idempotency_scope, idempotency_key, correlation_id)):
            raise ValueError("Invalid idempotency or correlation field")
        if created_by is not None and not isinstance(created_by, ObjectId):
            raise ValueError("created_by must be ObjectId or None")
        instant = _utc(now)
        immutable = {
            "workspace_id": workspace_id, "job_type": job_type,
            "resource_ref": dict(resource_ref),
            "config_ref": dict(config_ref) if config_ref is not None else None,
        }
        record = {
            "_id": ObjectId(), "schema_version": 1, "created_at": instant,
            "created_by": created_by, "updated_at": instant, "updated_by": created_by,
            "revision": 1, **immutable,
            "idempotency_scope": idempotency_scope, "idempotency_key": idempotency_key,
            "correlation_id": correlation_id, "state": "QUEUED", "priority": priority,
            "available_at": instant, "lease_owner": None, "lease_expires_at": None,
            "heartbeat_at": None, "attempt": 0, "max_attempts": max_attempts,
            "progress": {"step": "QUEUED"}, "error_code": None,
        }
        try:
            self.collection.insert_one(record)
        except DuplicateKeyError:
            prior = self.collection.find_one({
                "idempotency_scope": idempotency_scope,
                "idempotency_key": idempotency_key,
            })
            if prior is None or any(prior.get(key) != value for key, value in immutable.items()):
                raise IdempotencyConflict("Key already belongs to another input") from None
            return prior
        return record

    def get(self, *, job_id: ObjectId, workspace_id: ObjectId) -> dict[str, Any] | None:
        return self.collection.find_one({"_id": job_id, "workspace_id": workspace_id})

    def claim(
        self, *, owner: str, lease_seconds: int = 120, now: datetime | None = None,
    ) -> dict[str, Any] | None:
        if (not isinstance(owner, str) or not owner or len(owner) > 128
                or type(lease_seconds) is not int or not 1 <= lease_seconds <= 3600):
            raise ValueError("Invalid lease owner or duration")
        instant = _utc(now)
        candidates = self.collection.find({"$or": [
            {"state": "QUEUED", "available_at": {"$lte": instant}},
            {"state": {"$in": ["CLAIMED", "RUNNING"]},
             "lease_expires_at": {"$lte": instant}},
        ]}).sort([("priority", DESCENDING), ("created_at", ASCENDING), ("_id", ASCENDING)])
        for candidate in candidates:
            expected = {"_id": candidate["_id"], "revision": candidate["revision"],
                        "state": candidate["state"], "attempt": candidate["attempt"]}
            if candidate["state"] == "QUEUED":
                expected["available_at"] = {"$lte": instant}
            else:
                expected["lease_expires_at"] = {"$lte": instant}
            if candidate["attempt"] >= candidate["max_attempts"]:
                self.collection.update_one(expected, {"$set": {
                    "state": "FAILED_FINAL", "error_code": "LEASE_EXHAUSTED",
                    "progress": {"step": "FAILED_FINAL"},
                    "lease_owner": None, "lease_expires_at": None,
                    "updated_at": instant, "finished_at": instant,
                }, "$inc": {"revision": 1}})
                continue
            claimed = self.collection.find_one_and_update(expected, {
                "$set": {"state": "CLAIMED", "lease_owner": owner,
                         "lease_expires_at": instant + timedelta(seconds=lease_seconds),
                         "heartbeat_at": instant, "updated_at": instant,
                         "progress": {"step": "CLAIMED"}},
                "$inc": {"attempt": 1, "revision": 1},
            }, return_document=ReturnDocument.AFTER)
            if claimed is not None:
                return claimed
        return None

    @staticmethod
    def _leased(job_id: ObjectId, owner: str, revision: int,
                instant: datetime, states: tuple[str, ...]) -> dict[str, Any]:
        return {"_id": job_id, "revision": revision, "lease_owner": owner,
                "lease_expires_at": {"$gt": instant}, "state": {"$in": states}}

    def start(self, *, job_id: ObjectId, owner: str, revision: int,
              now: datetime | None = None) -> dict[str, Any] | None:
        instant = _utc(now)
        return self.collection.find_one_and_update(
            self._leased(job_id, owner, revision, instant, ("CLAIMED",)),
            {"$set": {"state": "RUNNING", "updated_at": instant,
                      "progress": {"step": "RUNNING"}}, "$inc": {"revision": 1}},
            return_document=ReturnDocument.AFTER,
        )

    def heartbeat(self, *, job_id: ObjectId, owner: str, revision: int,
                  lease_seconds: int = 120,
                  now: datetime | None = None) -> dict[str, Any] | None:
        if type(lease_seconds) is not int or not 1 <= lease_seconds <= 3600:
            raise ValueError("Invalid lease duration")
        instant = _utc(now)
        return self.collection.find_one_and_update(
            self._leased(job_id, owner, revision, instant, ("CLAIMED", "RUNNING")),
            {"$set": {"heartbeat_at": instant,
                      "lease_expires_at": instant + timedelta(seconds=lease_seconds),
                      "updated_at": instant}, "$inc": {"revision": 1}},
            return_document=ReturnDocument.AFTER,
        )

    def complete(self, *, job_id: ObjectId, owner: str, revision: int,
                 now: datetime | None = None) -> dict[str, Any] | None:
        instant = _utc(now)
        return self.collection.find_one_and_update(
            self._leased(job_id, owner, revision, instant, ("RUNNING",)),
            {"$set": {"state": "SUCCEEDED", "lease_owner": None,
                      "lease_expires_at": None, "finished_at": instant,
                      "updated_at": instant, "progress": {"step": "SUCCEEDED"}},
             "$inc": {"revision": 1}},
            return_document=ReturnDocument.AFTER,
        )

    def fail(self, *, job_id: ObjectId, owner: str, revision: int,
             error_code: str, retryable: bool, retry_delay_seconds: int = 30,
             now: datetime | None = None) -> dict[str, Any] | None:
        if SAFE_ERROR_CODE.fullmatch(error_code) is None or not 0 <= retry_delay_seconds <= 3600:
            raise ValueError("Invalid safe error code or retry delay")
        instant = _utc(now)
        base = self._leased(job_id, owner, revision, instant, ("CLAIMED", "RUNNING"))
        current = self.collection.find_one(base, projection={"attempt": 1, "max_attempts": 1})
        if current is None:
            return None
        again = retryable and current["attempt"] < current["max_attempts"]
        state = "QUEUED" if again else "FAILED_FINAL"
        update: dict[str, Any] = {
            "state": state, "error_code": error_code,
            "lease_owner": None, "lease_expires_at": None,
            "updated_at": instant, "progress": {"step": state},
        }
        if again:
            update["available_at"] = instant + timedelta(seconds=retry_delay_seconds)
        else:
            update["finished_at"] = instant
        return self.collection.find_one_and_update(
            {**base, "attempt": current["attempt"]},
            {"$set": update, "$inc": {"revision": 1}},
            return_document=ReturnDocument.AFTER,
        )

    def cancel(self, *, job_id: ObjectId, workspace_id: ObjectId, revision: int,
               now: datetime | None = None) -> dict[str, Any] | None:
        instant = _utc(now)
        return self.collection.find_one_and_update(
            {"_id": job_id, "workspace_id": workspace_id, "revision": revision,
             "state": {"$in": ACTIVE_STATES}},
            {"$set": {"state": "CANCELLED", "lease_owner": None,
                      "lease_expires_at": None, "finished_at": instant,
                      "updated_at": instant, "progress": {"step": "CANCELLED"}},
             "$inc": {"revision": 1}},
            return_document=ReturnDocument.AFTER,
        )
