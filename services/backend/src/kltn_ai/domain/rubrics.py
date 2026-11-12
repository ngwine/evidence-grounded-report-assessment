"""Workspace-scoped Mongo rubric authoring and immutable publication.

Production writes use replica-set transactions; ``transaction_mode=False`` is
an explicit unit-test adapter, not an automatic standalone-Mongo fallback.
The service never infers evidence requirements from a criterion description.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from jsonschema import Draft202012Validator
from pymongo import ReturnDocument
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern

from research.core_mvp.rubric_api import compile_api_rubric_definition

from .access import AccessPolicy, object_id
from .audit import append_event
from .errors import DomainError


def _object(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {"type": "object", "additionalProperties": False,
            "required": required, "properties": properties}


_ID = {"type": "string", "pattern": r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"}
_TEXT = {"type": "string", "minLength": 1, "maxLength": 10000}
_REQUIREMENT = _object({
    "requirement_id": _ID, "description": _TEXT,
    "any_of": {"type": "array", "minItems": 1, "maxItems": 100, "items": _TEXT},
}, ["requirement_id", "any_of"])
_CHECKLIST = _object({
    "checklist_key": _ID, "statement": _TEXT, "requirement": _TEXT,
    "evidence_mode": {"enum": ["LOCAL", "GRAPH"]},
    "importance": {"enum": ["CORE", "REQUIRED", "OPTIONAL"]}, "query": _TEXT,
    "requirements": {"type": "array", "minItems": 1, "maxItems": 100, "items": _REQUIREMENT},
    "contradiction_patterns": {"type": "array", "maxItems": 100, "items": _TEXT},
}, ["checklist_key", "statement", "evidence_mode", "requirements"])
_CRITERION = _object({
    "criterion_key": _ID, "title": _TEXT,
    "weight": {"type": "number", "exclusiveMinimum": 0},
    "scoring_mode": {"enum": ["PROPORTIONAL_CHECKLIST_V0"]},
    "checklists": {"type": "array", "minItems": 1, "maxItems": 100, "items": _CHECKLIST},
    "levels": {"type": "array", "maxItems": 20, "items": _object({
        "level_key": _TEXT, "score": {"type": "number"}, "rule": _TEXT,
    }, ["level_key", "score", "rule"])},
}, ["criterion_key", "title", "weight", "scoring_mode", "checklists"])
_DEFINITION = _object({
    "max_score": {"type": "number", "exclusiveMinimum": 0},
    "criteria": {"type": "array", "minItems": 1, "maxItems": 100, "items": _CRITERION},
    "decision_rules": _object({
        "rule_version": _TEXT,
        "cannot_assess_count_threshold": {"type": "integer", "minimum": 1},
        "cannot_assess_ratio_threshold": {"type": "number", "minimum": 0, "maximum": 1},
        "required_unmet_score": {"type": "number", "minimum": 0},
    }, []),
}, ["max_score", "criteria"])
_CREATE = _object({
    "rubric_key": {"type": "string", "minLength": 1, "maxLength": 128},
    "title": {"type": "string", "minLength": 1, "maxLength": 500},
    "definition": _DEFINITION,
}, ["rubric_key", "title", "definition"])
_CLONE = {**_object({
    "clone_from_version_id": {"type": "string", "pattern": "^[0-9a-f]{24}$"},
    "definition": _DEFINITION,
}, []), "oneOf": [{"required": ["clone_from_version_id"]}, {"required": ["definition"]}]}


def _canonical(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, ensure_ascii=False,
                          separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError, RecursionError):
        raise DomainError(422, "VALIDATION_FAILED", "Invalid JSON payload") from None


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _validation(value: Any, schema: dict[str, Any], prefix: str) -> None:
    if len(_canonical(value).encode()) > 1_000_000:
        raise DomainError(422, "VALIDATION_FAILED", "Rubric payload exceeds the authoring limit")
    issue = next(Draft202012Validator(schema).iter_errors(value), None)
    if issue is not None:
        # Paths, unlike jsonschema.message, cannot include arbitrary authored text.
        # Map object keys to declared schema fields only, not malicious keys.
        path = prefix
        for part in issue.absolute_path:
            if isinstance(part, int):
                path += f"[{part}]"
            elif isinstance(part, str) and re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", part):
                path += "." + part
        raise DomainError(422, "VALIDATION_FAILED", f"Invalid field: {path}")


def _revision(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise DomainError(422, "VALIDATION_FAILED", "A positive expected revision is required")
    return value


def _rubric(record: dict[str, Any]) -> dict[str, Any]:
    return {"id": str(record["_id"]), "workspace_id": str(record["workspace_id"]),
            "rubric_key": record["rubric_key"], "title": record["title"],
            "current_version_id": str(record["current_version_id"]),
            "lifecycle_state": record["lifecycle_state"], "revision": record["revision"]}


def _version(record: dict[str, Any]) -> dict[str, Any]:
    return {"id": str(record["_id"]), "rubric_id": str(record["rubric_id"]),
            "version_no": record["version_no"], "status": record["status"],
            "definition": deepcopy(record["definition"]),
            "rubric_sha256": record["rubric_sha256"], "revision": record["revision"]}


class RubricService:
    def __init__(self, database: Database[dict[str, Any]], *, transaction_mode: bool = True):
        self.db = database
        self.access = AccessPolicy(database)
        self.transaction_mode = transaction_mode

    def _scope(self, actor_id: ObjectId, workspace_id: str | ObjectId, session: Any = None) -> ObjectId:
        return self.access.require(actor_id, workspace_id, "rubric.manage", session=session)["_id"]

    @staticmethod
    def _session(session: Any) -> dict[str, Any]:
        return {} if session is None else {"session": session}

    def _audit(self, *, actor_id: ObjectId, workspace_id: ObjectId, action: str,
               resource_id: ObjectId, request_id: str, session: Any) -> None:
        if not isinstance(request_id, str) or re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", request_id) is None:
            raise DomainError(422, "VALIDATION_FAILED", "Invalid request identifier")
        append_event(self.db, actor_id=actor_id, workspace_id=workspace_id,
                     action=action, resource_type="RUBRIC", resource_id=resource_id,
                     request_id=request_id, session=session)

    def _operation(self, actor_id: ObjectId, workspace_id: str | ObjectId, *,
                   operation_key: str, idempotency_key: str, payload: Any,
                   action: Callable[[Any, ObjectId], dict[str, Any]]) -> dict[str, Any]:
        workspace = self._scope(actor_id, workspace_id)
        if (not isinstance(idempotency_key, str)
                or re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", idempotency_key) is None):
            raise DomainError(422, "VALIDATION_FAILED", "Invalid idempotency key")
        identity = {"workspace_id": workspace, "actor_id": actor_id,
                    "operation_key": operation_key, "idempotency_key": idempotency_key}
        request_sha = _sha(payload)

        def replay(record: dict[str, Any]) -> dict[str, Any]:
            if record["request_sha256"] != request_sha:
                raise DomainError(409, "IDEMPOTENCY_CONFLICT", "Idempotency key used for a different request")
            return deepcopy(record["response"])

        def run(session: Any) -> dict[str, Any]:
            # Recheck authority for every retry and idempotency replay.
            self._scope(actor_id, workspace, session)
            opts = self._session(session)
            previous = self.db.rubric_operations.find_one(identity, **opts)
            if previous is not None:
                return replay(previous)
            response = action(session, workspace)
            now = datetime.now(UTC)
            self.db.rubric_operations.insert_one({
                "_id": ObjectId(), **identity, "request_sha256": request_sha,
                "response": deepcopy(response), "status": "SUCCEEDED", "schema_version": 1,
                "created_at": now, "created_by": actor_id,
            }, **opts)
            return response

        try:
            if not self.transaction_mode:
                return run(None)
            with self.db.client.start_session() as session:
                return session.with_transaction(
                    run, read_concern=ReadConcern("snapshot"),
                    write_concern=WriteConcern("majority", wtimeout=30000),
                )
        except DuplicateKeyError:
            previous = self.db.rubric_operations.find_one(identity)
            if previous is not None:
                self._scope(actor_id, workspace)
                return replay(previous)
            raise DomainError(409, "RUBRIC_CONFLICT", "Rubric key or version already exists") from None

    @staticmethod
    def _new_version(*, actor_id: ObjectId, workspace: ObjectId,
                     rubric_id: ObjectId, version_id: ObjectId, number: int,
                     definition: dict[str, Any], now: datetime) -> dict[str, Any]:
        return {"_id": version_id, "schema_version": 1, "workspace_id": workspace,
                "rubric_id": rubric_id, "version_no": number, "status": "DRAFT",
                "definition": deepcopy(definition), "rubric_sha256": _sha(definition),
                "compiled": None, "compiled_id": None, "compiled_sha256": None,
                "compiler_version": None, "published_at": None, "published_by": None,
                "revision": 1, "created_at": now, "created_by": actor_id,
                "updated_at": now, "updated_by": actor_id}

    def create(self, actor_id: ObjectId, workspace_id: str | ObjectId,
               body: dict[str, Any], *, idempotency_key: str, request_id: str) -> dict[str, Any]:
        self._scope(actor_id, workspace_id)
        _validation(body, _CREATE, "body")

        def action(session: Any, workspace: ObjectId) -> dict[str, Any]:
            now = datetime.now(UTC)
            rubric_id, version_id = ObjectId(), ObjectId()
            record = {"_id": rubric_id, "schema_version": 1, "workspace_id": workspace,
                      "rubric_key": body["rubric_key"], "title": body["title"],
                      "current_version_id": version_id, "lifecycle_state": "ACTIVE",
                      "version_counter": 1, "revision": 1, "created_at": now,
                      "created_by": actor_id, "updated_at": now, "updated_by": actor_id}
            self.db.rubrics.insert_one(record, **self._session(session))
            version = self._new_version(actor_id=actor_id, workspace=workspace,
                                        rubric_id=rubric_id, version_id=version_id,
                                        number=1, definition=body["definition"], now=now)
            self.db.rubric_versions.insert_one(version, **self._session(session))
            self._audit(actor_id=actor_id, workspace_id=workspace, action="RUBRIC_CREATED",
                        resource_id=rubric_id, request_id=request_id, session=session)
            return _rubric(record)

        return self._operation(actor_id, workspace_id, operation_key="create",
                               idempotency_key=idempotency_key, payload=body, action=action)

    def list(self, actor_id: ObjectId, workspace_id: str | ObjectId, *,
             limit: int = 20, cursor: str | None = None) -> dict[str, Any]:
        workspace = self._scope(actor_id, workspace_id)
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise DomainError(422, "VALIDATION_FAILED", "Limit must be between 1 and 100")
        query: dict[str, Any] = {"workspace_id": workspace, "lifecycle_state": "ACTIVE"}
        if cursor is not None:
            query["_id"] = {"$gt": object_id(cursor)}
        records = list(self.db.rubrics.find(query).sort("_id", 1).limit(limit + 1))
        more = len(records) > limit
        visible = records[:limit]
        return {"items": [_rubric(record) for record in visible],
                "page": {"limit": limit, "has_more": more,
                         "next_cursor": str(visible[-1]["_id"]) if more else None}}

    def get(self, actor_id: ObjectId, workspace_id: str | ObjectId,
            rubric_id: str | ObjectId) -> dict[str, Any]:
        workspace = self._scope(actor_id, workspace_id)
        record = self.db.rubrics.find_one({"_id": object_id(rubric_id), "workspace_id": workspace,
                                           "lifecycle_state": "ACTIVE"})
        if record is None:
            raise DomainError(404, "RESOURCE_NOT_FOUND", "Resource not found")
        return _rubric(record)

    def _find_version(self, workspace: ObjectId, version_id: str | ObjectId,
                      session: Any = None) -> dict[str, Any]:
        record = self.db.rubric_versions.find_one({"_id": object_id(version_id),
                                                 "workspace_id": workspace}, **self._session(session))
        if record is None or self.db.rubrics.find_one({
            "_id": record["rubric_id"], "workspace_id": workspace, "lifecycle_state": "ACTIVE",
        }, **self._session(session)) is None:
            raise DomainError(404, "RESOURCE_NOT_FOUND", "Resource not found")
        return record

    def get_version(self, actor_id: ObjectId, workspace_id: str | ObjectId,
                    version_id: str | ObjectId) -> dict[str, Any]:
        workspace = self._scope(actor_id, workspace_id)
        return _version(self._find_version(workspace, version_id))

    def list_versions(self, actor_id: ObjectId, workspace_id: str | ObjectId,
                      rubric_id: str | ObjectId, *, limit: int = 20,
                      cursor: str | None = None) -> dict[str, Any]:
        workspace = self._scope(actor_id, workspace_id)
        rubric = object_id(rubric_id)
        if self.db.rubrics.find_one({"_id": rubric, "workspace_id": workspace,
                                     "lifecycle_state": "ACTIVE"}) is None:
            raise DomainError(404, "RESOURCE_NOT_FOUND", "Resource not found")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise DomainError(422, "VALIDATION_FAILED", "Limit must be between 1 and 100")
        query: dict[str, Any] = {"workspace_id": workspace, "rubric_id": rubric}
        if cursor is not None:
            query["_id"] = {"$gt": object_id(cursor)}
        records = list(self.db.rubric_versions.find(query).sort("_id", 1).limit(limit + 1))
        more = len(records) > limit
        visible = records[:limit]
        return {"items": [_version(record) for record in visible],
                "page": {"limit": limit, "has_more": more,
                         "next_cursor": str(visible[-1]["_id"]) if more else None}}

    def clone_version(self, actor_id: ObjectId, workspace_id: str | ObjectId,
                      rubric_id: str | ObjectId, body: dict[str, Any], *,
                      expected_revision: int, idempotency_key: str, request_id: str) -> dict[str, Any]:
        self._scope(actor_id, workspace_id)
        rubric = object_id(rubric_id)
        expected_revision = _revision(expected_revision)
        _validation(body, _CLONE, "body")

        def action(session: Any, workspace: ObjectId) -> dict[str, Any]:
            opts = self._session(session)
            current = self.db.rubrics.find_one({"_id": rubric, "workspace_id": workspace,
                                                "lifecycle_state": "ACTIVE"}, **opts)
            if current is None:
                raise DomainError(404, "RESOURCE_NOT_FOUND", "Resource not found")
            if current["revision"] != expected_revision:
                raise DomainError(409, "REVISION_CONFLICT", "Rubric revision changed")
            if "clone_from_version_id" in body:
                source = self._find_version(workspace, body["clone_from_version_id"], session)
                if source["rubric_id"] != rubric:
                    raise DomainError(404, "RESOURCE_NOT_FOUND", "Resource not found")
                definition = source["definition"]
            else:
                definition = body["definition"]
            now = datetime.now(UTC)
            version_id = ObjectId()
            updated = self.db.rubrics.find_one_and_update({
                "_id": rubric, "workspace_id": workspace, "lifecycle_state": "ACTIVE",
                "revision": expected_revision,
            }, {"$inc": {"revision": 1, "version_counter": 1},
                "$set": {"updated_at": now, "updated_by": actor_id}},
                return_document=ReturnDocument.AFTER, **opts)
            if updated is None:
                raise DomainError(409, "REVISION_CONFLICT", "Rubric revision changed")
            record = self._new_version(actor_id=actor_id, workspace=workspace, rubric_id=rubric,
                                       version_id=version_id, number=updated["version_counter"],
                                       definition=definition, now=now)
            self.db.rubric_versions.insert_one(record, **opts)
            self._audit(actor_id=actor_id, workspace_id=workspace, action="RUBRIC_VERSION_CLONED",
                        resource_id=version_id, request_id=request_id, session=session)
            return _version(record)

        return self._operation(actor_id, workspace_id, operation_key=f"clone:{rubric}",
                               idempotency_key=idempotency_key,
                               payload={"body": body, "expected_revision": expected_revision}, action=action)

    def update_draft(self, actor_id: ObjectId, workspace_id: str | ObjectId,
                     version_id: str | ObjectId, definition: dict[str, Any], *,
                     expected_revision: int, request_id: str) -> dict[str, Any]:
        workspace = self._scope(actor_id, workspace_id)
        expected_revision = _revision(expected_revision)
        _validation(definition, _DEFINITION, "definition")

        def action(session: Any) -> dict[str, Any]:
            self._scope(actor_id, workspace, session)
            record = self._find_version(workspace, version_id, session)
            if record["status"] != "DRAFT":
                raise DomainError(409, "RUBRIC_IMMUTABLE", "Only a draft version may be edited")
            if record["revision"] != expected_revision:
                raise DomainError(409, "REVISION_CONFLICT", "Rubric version revision changed")
            updated = self.db.rubric_versions.find_one_and_update({
                "_id": record["_id"], "workspace_id": workspace, "status": "DRAFT",
                "revision": expected_revision,
            }, {"$set": {"definition": deepcopy(definition), "rubric_sha256": _sha(definition),
                         "updated_at": datetime.now(UTC), "updated_by": actor_id},
                "$inc": {"revision": 1}}, return_document=ReturnDocument.AFTER,
                **self._session(session))
            if updated is None:
                raise DomainError(409, "REVISION_CONFLICT", "Rubric version revision changed")
            self._audit(actor_id=actor_id, workspace_id=workspace, action="RUBRIC_DRAFT_UPDATED",
                        resource_id=record["_id"], request_id=request_id, session=session)
            return _version(updated)

        if not self.transaction_mode:
            return action(None)
        with self.db.client.start_session() as session:
            return session.with_transaction(action, read_concern=ReadConcern("snapshot"),
                                            write_concern=WriteConcern("majority", wtimeout=30000))

    @staticmethod
    def _compile(record: dict[str, Any], rubric: dict[str, Any]) -> dict[str, Any]:
        try:
            return compile_api_rubric_definition(
                rubric_key=rubric["rubric_key"], title=rubric["title"],
                rubric_version=str(record["version_no"]), definition=record["definition"],
            )
        except ValueError as exc:
            # Adapter-prefixed field paths are safe, compiler messages may echo
            # an authored identifier/phrase, so never return the latter.
            match = re.match(r"^(definition(?:\.[a-z_]+|\[[0-9]+\])*)", str(exc))
            field = match.group(1) if match is not None else "definition"
            raise DomainError(422, "RUBRIC_COMPILATION_FAILED", f"Rubric cannot be compiled: {field}") from None

    def publish_version(self, actor_id: ObjectId, workspace_id: str | ObjectId,
                        version_id: str | ObjectId, *, expected_revision: int,
                        idempotency_key: str, request_id: str) -> dict[str, Any]:
        self._scope(actor_id, workspace_id)
        version = object_id(version_id)
        expected_revision = _revision(expected_revision)

        def action(session: Any, workspace: ObjectId) -> dict[str, Any]:
            opts = self._session(session)
            record = self._find_version(workspace, version, session)
            if record["status"] != "DRAFT":
                raise DomainError(409, "RUBRIC_IMMUTABLE", "Rubric version is already immutable")
            if record["revision"] != expected_revision:
                raise DomainError(409, "REVISION_CONFLICT", "Rubric version revision changed")
            rubric = self.db.rubrics.find_one({"_id": record["rubric_id"], "workspace_id": workspace}, **opts)
            assert rubric is not None  # Parent checked by _find_version in this snapshot.
            compiled = self._compile(record, rubric)
            now = datetime.now(UTC)
            updated = self.db.rubric_versions.find_one_and_update({
                "_id": version, "workspace_id": workspace,
                "status": "DRAFT", "revision": expected_revision,
            }, {"$set": {"status": "PUBLISHED", "compiled": compiled,
                         "compiled_id": compiled["compiled_id"],
                         "compiled_sha256": compiled["compiled_sha256"],
                         "compiler_version": compiled["compiler"]["version"],
                         "published_at": now, "published_by": actor_id,
                         "updated_at": now, "updated_by": actor_id}, "$inc": {"revision": 1}},
                return_document=ReturnDocument.AFTER, **opts)
            if updated is None:
                raise DomainError(409, "REVISION_CONFLICT", "Rubric version revision changed")
            # Concurrent publications conflict on this parent write and retry
            # transactionally; existing immutable published snapshots stay intact.
            self.db.rubrics.update_one({"_id": rubric["_id"], "workspace_id": workspace},
                                      {"$set": {"current_version_id": version, "updated_at": now,
                                                "updated_by": actor_id}, "$inc": {"revision": 1}}, **opts)
            self._audit(actor_id=actor_id, workspace_id=workspace, action="RUBRIC_VERSION_PUBLISHED",
                        resource_id=version, request_id=request_id, session=session)
            return _version(updated)

        return self._operation(actor_id, workspace_id, operation_key=f"publish:{version}",
                               idempotency_key=idempotency_key,
                               payload={"expected_revision": expected_revision}, action=action)

    def get_compiled_published(self, actor_id: ObjectId, workspace_id: str | ObjectId,
                               version_id: str | ObjectId) -> dict[str, Any]:
        workspace = self._scope(actor_id, workspace_id)
        record = self._find_version(workspace, version_id)
        if record["status"] != "PUBLISHED" or record.get("compiled") is None:
            raise DomainError(409, "RUBRIC_NOT_PUBLISHED", "Analysis requires a published rubric version")
        compiled = record["compiled"]
        # Rebuild from the exact authored definition/version, not just a
        # self-consistent stored compiled hash. This detects a swapped compiled
        # snapshot whose attacker also rewrote its stored SHA and ID fields.
        rubric = self.db.rubrics.find_one({"_id": record["rubric_id"], "workspace_id": workspace})
        try:
            rebuilt = self._compile(record, rubric) if rubric is not None else None
            valid = (rebuilt == compiled
                     and compiled["compiled_sha256"] == record["compiled_sha256"]
                     and compiled["compiled_id"] == record["compiled_id"]
                     and compiled["compiler"]["version"] == record["compiler_version"]
                     and _sha(record["definition"]) == record["rubric_sha256"])
        except (DomainError, KeyError, TypeError, ValueError):
            valid = False
        if not valid:
            raise DomainError(409, "RUBRIC_INTEGRITY_FAILED", "Published rubric integrity check failed")
        self._scope(actor_id, workspace)
        return deepcopy(compiled)
