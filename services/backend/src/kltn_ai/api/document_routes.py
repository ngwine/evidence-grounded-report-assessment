"""Authenticated DTO boundary for private uploads and durable parse progress.

Never serialize Mongo records wholesale: storage keys, subjects and queue
configuration are not public fields. Full per-element spans are returned in
addition to the compact locator; a multi-page chunk has no single fake page.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from bson import ObjectId
from fastapi import APIRouter, Request, Response
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile

from ..domain.access import AccessPolicy, object_id
from ..domain.documents import DocumentService, MAX_DOCUMENT_BYTES
from ..domain.errors import DomainError


def _page(values: list[dict[str, Any]], limit: int, cursor: Callable) -> dict[str, Any]:
    more = len(values) > limit
    values = values[:limit]
    return {"items": values, "page": {"limit": limit, "has_more": more,
            "next_cursor": cursor(values[-1]) if more else None}}


def _pagination(limit: int, cursor: str | None) -> None:
    if not 1 <= limit <= 100 or cursor is not None and not ObjectId.is_valid(cursor):
        raise DomainError(400, "INVALID_PAGINATION", "Invalid pagination")


def document_router(database, private_root: Path, *, transaction_mode: bool, prefix: str,
                    key_reader: Callable, revision_reader: Callable) -> APIRouter:
    router = APIRouter(prefix=prefix)
    policy = AccessPolicy(database)

    def service() -> DocumentService:
        return DocumentService(database, private_root, transactional=transaction_mode)

    def governance(identifier: ObjectId) -> str:
        row = database.governance_records.find_one({"_id": identifier})
        if row is None:
            return "PENDING"
        for field, container in (("valid_until", row), ("expires_at", row.get("retention_policy") or {})):
            expiry = container.get(field)
            if expiry is not None and expiry.replace(tzinfo=expiry.tzinfo or UTC) <= datetime.now(UTC):
                return "EXPIRED"
        return row["status"]

    def document_dto(row: dict[str, Any]) -> dict[str, Any]:
        result = {"id": str(row["_id"]), **{key: str(row[key]) for key in (
            "workspace_id", "current_version_id")}, **{key: row[key] for key in (
            "document_key", "title", "lifecycle_state", "revision")}}
        if row["kind"] == "REPORT":
            result["owner_user_id"] = str(row["owner_user_id"])
        else:
            result["governance_state"] = governance(row["current_governance_record_id"])
        return result

    def version_dto(row: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {"id": str(row["_id"]), "document_id": str(row["document_id"]),
                  "governance_state": governance(row["governance_record_id"])}
        result.update({key: row[key] for key in ("version_no", "content_sha256", "processing_state",
            "lifecycle_state", "element_count", "chunk_count", "failure_code", "revision")})
        for field in ("parser_spec", "chunker_spec"):
            spec = row[field]
            result[field] = {key: spec[key] for key in ("name", "version", "config_sha256")} if spec else None
        return result

    def get_document(request: Request, workspace: str, identifier: str, kind: str):
        row = service().get(request.state.actor_id, workspace, identifier)
        if row["kind"] != kind:
            raise DomainError(404, "RESOURCE_NOT_FOUND", "Resource not found")
        return row

    def list_documents(request: Request, workspace_id: str, kind: str, limit: int, cursor: str | None):
        _pagination(limit, cursor)
        workspace = object_id(workspace_id)
        policy.require(request.state.actor_id, workspace, "report.read" if kind == "REPORT" else "source.read")
        query: dict[str, Any] = {"workspace_id": workspace, "kind": kind, "lifecycle_state": "ACTIVE"}
        if cursor:
            query["_id"] = {"$gt": ObjectId(cursor)}
        membership = database.memberships.find_one({"user_id": request.state.actor_id,
            "workspace_id": workspace, "status": "ACTIVE"})
        if membership is None:
            raise DomainError(404, "RESOURCE_NOT_FOUND", "Resource not found")
        if "LECTURER" not in membership["roles"]:
            query["owner_user_id"] = request.state.actor_id
        values = []
        documents = service()
        for row in database.documents.find(query).sort("_id", 1):
            try:
                values.append(document_dto(documents.get(request.state.actor_id, workspace, row["_id"])))
            except DomainError as error:
                if error.status != 404:
                    raise
            if len(values) > limit:
                break
        return _page(values, limit, lambda row: row["id"])

    async def upload(request: Request, workspace_id: str, kind: str, document_id: str | None = None):
        actor = request.state.actor_id
        policy.require(actor, workspace_id, "report.upload" if kind == "REPORT" else "source.upload")
        key = key_reader(request)
        existing = get_document(request, workspace_id, document_id, kind) if document_id else None
        revision = revision_reader(request) if existing else None
        if request.headers.get("content-type", "").split(";", 1)[0] != "multipart/form-data":
            raise DomainError(415, "UNSUPPORTED_MEDIA_TYPE", "Multipart upload required")
        async with request.form(max_files=1, max_fields=4, max_part_size=16384) as form:
            allowed = {"file", "governance_record_id"} if existing else {
                "file", "governance_record_id", "document_key", "title"}
            if (set(form) - allowed or any(len(form.getlist(field)) != 1 for field in form)
                    or not allowed <= set(form)):
                raise DomainError(422, "INVALID_DOCUMENT", "Required upload fields are missing or repeated")
            file = form.get("file")
            if not isinstance(file, UploadFile) or not file.filename:
                raise DomainError(422, "INVALID_DOCUMENT", "A document file is required")
            fields = {name: form[name] for name in allowed - {"file"}}
            text_fields: dict[str, str] = {}
            for name, value in fields.items():
                if not isinstance(value, str):
                    raise DomainError(422, "INVALID_DOCUMENT", "Invalid upload metadata")
                text_fields[name] = value
            payload = await file.read(MAX_DOCUMENT_BYTES + 1)
            result = await run_in_threadpool(service().upload, actor, workspace_id, kind=kind,
                document_key=existing["document_key"] if existing else text_fields["document_key"],
                title=existing["title"] if existing else text_fields["title"], filename=file.filename,
                payload=payload, idempotency_key=key, request_id=request.state.request_id,
                governance_record_id=text_fields["governance_record_id"], document_id=document_id,
                expected_revision=revision, create_only=existing is None)
        return {"document_id": str(result["document"]["_id"]),
                "document_version_id": str(result["version"]["_id"]),
                "job_id": str(result["job"]["_id"]), "state": result["job"]["state"]}

    @router.get("/workspaces/{workspace_id}/reports")
    def list_reports(workspace_id: str, request: Request, limit: int = 25, cursor: str | None = None):
        return list_documents(request, workspace_id, "REPORT", limit, cursor)

    @router.get("/workspaces/{workspace_id}/sources")
    def list_sources(workspace_id: str, request: Request, limit: int = 25, cursor: str | None = None):
        return list_documents(request, workspace_id, "CORPUS_SOURCE", limit, cursor)

    @router.post("/workspaces/{workspace_id}/reports", status_code=202)
    async def create_report(workspace_id: str, request: Request):
        return await upload(request, workspace_id, "REPORT")

    @router.post("/workspaces/{workspace_id}/sources", status_code=202)
    async def create_source(workspace_id: str, request: Request):
        return await upload(request, workspace_id, "CORPUS_SOURCE")

    @router.get("/workspaces/{workspace_id}/reports/{report_id}")
    def get_report(workspace_id: str, report_id: str, request: Request, response: Response):
        row = get_document(request, workspace_id, report_id, "REPORT")
        response.headers["ETag"] = f'"rev-{row["revision"]}"'
        return document_dto(row)

    @router.get("/workspaces/{workspace_id}/sources/{source_id}")
    def get_source(workspace_id: str, source_id: str, request: Request, response: Response):
        row = get_document(request, workspace_id, source_id, "CORPUS_SOURCE")
        response.headers["ETag"] = f'"rev-{row["revision"]}"'
        return document_dto(row)

    @router.post("/workspaces/{workspace_id}/reports/{report_id}/versions", status_code=202)
    async def report_version(workspace_id: str, report_id: str, request: Request):
        return await upload(request, workspace_id, "REPORT", report_id)

    @router.post("/workspaces/{workspace_id}/sources/{source_id}/versions", status_code=202)
    async def source_version(workspace_id: str, source_id: str, request: Request):
        return await upload(request, workspace_id, "CORPUS_SOURCE", source_id)

    def visible_version(request: Request, workspace_id: str, version_id: str):
        workspace = object_id(workspace_id)
        policy.require(request.state.actor_id, workspace, "workspace.read")
        row = database.document_versions.find_one({"_id": object_id(version_id), "workspace_id": workspace})
        if row is None:
            raise DomainError(404, "RESOURCE_NOT_FOUND", "Resource not found")
        return service().get_version(request.state.actor_id, workspace, row["document_id"], row["_id"])

    @router.get("/workspaces/{workspace_id}/document-versions/{version_id}")
    def get_version(workspace_id: str, version_id: str, request: Request, response: Response):
        row = visible_version(request, workspace_id, version_id)
        response.headers["ETag"] = f'"rev-{row["revision"]}"'
        return version_dto(row)

    @router.get("/workspaces/{workspace_id}/document-versions/{version_id}/chunks")
    def chunks(workspace_id: str, version_id: str, request: Request, limit: int = 25, cursor: str | None = None):
        if not 1 <= limit <= 100 or cursor is not None and not re_valid_order(cursor):
            raise DomainError(400, "INVALID_PAGINATION", "Invalid chunk cursor")
        row = visible_version(request, workspace_id, version_id)
        documents = service()
        # Read one extra separately so the public limit remains 100, not 99.
        after = int(cursor) if cursor is not None else -1
        values = documents.get_chunks(request.state.actor_id, workspace_id, row["document_id"], row["_id"], limit=limit, after=after)
        output = [chunk_dto(item) for item in values]
        more = bool(values and documents.get_chunks(request.state.actor_id, workspace_id, row["document_id"], row["_id"],
                                                    limit=1, after=values[-1]["order"]))
        return {"items": output, "page": {"limit": limit, "has_more": more,
                "next_cursor": str(values[-1]["order"]) if more else None}}

    @router.get("/workspaces/{workspace_id}/jobs/{job_id}")
    def job(workspace_id: str, job_id: str, request: Request, response: Response):
        workspace = object_id(workspace_id)
        policy.require(request.state.actor_id, workspace, "workspace.read")
        row = database.jobs.find_one({"_id": object_id(job_id), "workspace_id": workspace})
        if row is None or row["job_type"] != "PARSE":
            raise DomainError(404, "RESOURCE_NOT_FOUND", "Resource not found")
        service().get_version(request.state.actor_id, workspace, row["resource_ref"]["id"], row["resource_ref"]["version_id"])
        response.headers["ETag"] = f'"rev-{row["revision"]}"'
        return {"id": str(row["_id"]), "job_type": row["job_type"], "resource_id": str(row["resource_ref"]["id"]),
                "state": row["state"], "attempt": row["attempt"], "max_attempts": row["max_attempts"],
                "progress": {"step": row["progress"]["step"], "completed": 1 if row["state"] == "SUCCEEDED" else 0, "total": 1},
                "error_code": row["error_code"], "revision": row["revision"], "created_at": row["created_at"],
                "completed_at": row.get("finished_at")}

    return router


def re_valid_order(cursor: str) -> bool:
    return cursor.isascii() and cursor.isdecimal() and len(cursor) <= 10


def chunk_dto(row: dict[str, Any]) -> dict[str, Any]:
    locator_keys = ("locator_version", "page_index", "page_label", "section_path", "block_id", "raw_char_start", "raw_char_end")
    result = {"id": str(row["_id"]), "document_version_id": str(row["document_version_id"]),
              **{key: row[key] for key in ("chunk_key", "order", "normalized_text", "content_sha256")},
              "locator": {key: row["locator"].get(key) for key in locator_keys},
              "raw_text": row["raw_text"], "normalization_map": row["normalization_map"], "source_spans": []}
    for span in row["source_spans"]:
        result["source_spans"].append({"element_id": str(span["element_id"]),
            "stable_element_key": span["stable_element_key"],
            **{key: span[key] for key in ("element_raw_char_start", "element_raw_char_end",
                "chunk_raw_char_start", "chunk_raw_char_end")},
            "locator": {key: span["locator"].get(key) for key in locator_keys}})
    return result
