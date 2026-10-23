"""Authenticated /api/v1 application, separate from the legacy local demo.

The factory requires an authoritative MongoDB database; it never falls back
to file state or anonymous lecturer access when MongoDB is unavailable.
Loopback-only deployment remains deliberate until a TLS/proxy ADR is approved.
"""

from __future__ import annotations

import re
import asyncio
import hashlib
import secrets
from typing import Any
from uuid import uuid4
from pathlib import Path

from bson import ObjectId
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pymongo.database import Database
from pymongo.errors import PyMongoError
from starlette.exceptions import HTTPException
from starlette.concurrency import run_in_threadpool

from ..auth.service import AuthService
from ..domain.errors import DomainError
from ..domain.rubrics import RubricService
from ..domain.documents import MAX_DOCUMENT_BYTES
from .document_routes import document_router
from .analysis_routes import analysis_router


PREFIX = "/api/v1"
COOKIE = "session"
ORIGINS = frozenset({"http://127.0.0.1:5173", "http://localhost:5173",
                     "http://127.0.0.1:8001", "http://localhost:8001"})
MAX_BODY = 1024 * 1024


def _failure(request: Request, status: int, code: str, message: str) -> JSONResponse:
    response = JSONResponse(status_code=status, content={"error": {
        "code": code, "message": message, "request_id": request.state.request_id,
    }})
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["Cache-Control"] = "no-store"
    if status == 429:
        response.headers["Retry-After"] = "300"
    return response


def _body(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DomainError(422, "VALIDATION_FAILED", "Request must be a JSON object")
    return value


def _revision(request: Request) -> int:
    match = re.fullmatch(r'"rev-([1-9][0-9]{0,8})"', request.headers.get("if-match", ""))
    if match is None:
        raise DomainError(428, "PRECONDITION_REQUIRED", "A valid If-Match revision is required")
    return int(match.group(1))


def _key(request: Request) -> str:
    value = request.headers.get("idempotency-key", "")
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{16,128}", value):
        raise DomainError(422, "VALIDATION_FAILED", "A valid Idempotency-Key is required")
    return value


def _etag(response: Response, value: dict[str, Any]) -> dict[str, Any]:
    response.headers["ETag"] = f'"rev-{value["revision"]}"'
    return value


def create_app(database: Database[dict[str, Any]], *, allow_test_client: bool = False,
               auth_service: AuthService | None = None, transaction_mode: bool = True,
               private_root: Path | None = None) -> FastAPI:
    auth = auth_service or AuthService(database)
    rubrics = RubricService(database, transaction_mode=transaction_mode)
    app = FastAPI(title="Evidence-Grounded Report Assessment", docs_url=None,
                  redoc_url=None, openapi_url=None)
    app.state.database = database
    login_slots = asyncio.Semaphore(2)

    @app.exception_handler(DomainError)
    async def domain_error(request: Request, error: DomainError):
        return _failure(request, error.status, error.code, error.message)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, _error: RequestValidationError):
        return _failure(request, 422, "VALIDATION_FAILED", "Request validation failed")

    @app.exception_handler(PyMongoError)
    async def database_error(request: Request, _error: PyMongoError):
        return _failure(request, 503, "SERVICE_UNAVAILABLE", "Database service unavailable")

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException):
        return _failure(request, error.status_code, "RESOURCE_NOT_FOUND" if error.status_code == 404
                        else "REQUEST_REJECTED", "Resource not found" if error.status_code == 404
                        else "Request rejected")

    @app.middleware("http")
    async def security_boundary(request: Request, call_next):
        supplied = request.headers.get("x-request-id", "")
        request.state.request_id = supplied if re.fullmatch(r"[A-Za-z0-9_.-]{8,128}", supplied) else "req-" + uuid4().hex
        peer = request.client.host if request.client else ""
        hosts, peers = {"127.0.0.1", "localhost", "::1"}, {"127.0.0.1", "::1"}
        if allow_test_client:
            peers.add("testclient")
            hosts.add("testserver")
        if peer not in peers or request.url.hostname not in hosts:
            return _failure(request, 403, "DEPLOYMENT_SCOPE_DENIED", "Loopback deployment only")
        origin = request.headers.get("origin")
        if origin is not None and origin not in ORIGINS:
            return _failure(request, 403, "ORIGIN_DENIED", "Origin not allowed")
        unsafe = request.method not in {"GET", "HEAD", "OPTIONS"}
        try:
            if unsafe and origin not in ORIGINS:
                return _failure(request, 403, "ORIGIN_REQUIRED", "An allowed Origin is required")
            if request.url.path != f"{PREFIX}/auth/sessions":
                session = await run_in_threadpool(auth.authenticate, request.cookies.get(COOKIE))
                request.state.session = session
                request.state.actor_id = session["user_id"]
                if unsafe:
                    auth.check_csrf(session, request.headers.get("x-csrf-token"))
            if unsafe:
                upload = request.method == "POST" and re.fullmatch(
                    r"/api/v1/workspaces/[0-9a-fA-F]{24}/(?:reports|sources)(?:/[0-9a-fA-F]{24}/versions)?",
                    request.url.path) is not None
                limit = MAX_DOCUMENT_BYTES + 65536 if upload else MAX_BODY
                length = request.headers.get("content-length", "0")
                if not length.isdecimal() or len(length) > 12 or int(length) > limit:
                    return _failure(request, 413, "PAYLOAD_TOO_LARGE", "Request exceeds endpoint limit")
                consumed = 0
                payload = bytearray()
                async for part in request.stream():
                    consumed += len(part)
                    if consumed > limit:
                        return _failure(request, 413, "PAYLOAD_TOO_LARGE", "Request exceeds endpoint limit")
                    payload.extend(part)
                request._body = bytes(payload)
            response = await call_next(request)
        except DomainError as error:
            return _failure(request, error.status, error.code, error.message)
        except PyMongoError:
            return _failure(request, 503, "SERVICE_UNAVAILABLE", "Database service unavailable")
        except Exception:
            return _failure(request, 500, "INTERNAL_ERROR", "Request could not be completed")
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    async def json_body(request: Request) -> dict[str, Any]:
        if request.headers.get("content-type", "").split(";", 1)[0] != "application/json":
            raise DomainError(415, "UNSUPPORTED_MEDIA_TYPE", "JSON content type required")
        try:
            return _body(await request.json())
        except (ValueError, UnicodeError, RecursionError):
            raise DomainError(422, "VALIDATION_FAILED", "Invalid JSON request") from None

    @app.post(f"{PREFIX}/auth/sessions")
    async def login(request: Request, response: Response):
        value = await json_body(request)
        if set(value) != {"email", "password"} or not all(isinstance(value[k], str) for k in value):
            raise DomainError(422, "VALIDATION_FAILED", "Email and password are required")
        if len(value["email"]) > 320 or not 1 <= len(value["password"]) <= 1024:
            raise DomainError(422, "VALIDATION_FAILED", "Credential input exceeds limits")
        try:
            await asyncio.wait_for(login_slots.acquire(), timeout=0.1)
        except TimeoutError:
            raise DomainError(429, "RATE_LIMITED", "Authentication service busy") from None
        try:
            outcome = await run_in_threadpool(
                auth.login, value["email"], value["password"], request.client.host if request.client else "unknown",
                old_token=request.cookies.get(COOKIE), request_id=request.state.request_id)
        finally:
            login_slots.release()
        response.set_cookie(COOKIE, outcome.pop("token"), httponly=True, secure=False,
                            samesite="lax", path="/api/v1", max_age=8 * 60 * 60)
        return outcome

    @app.get(f"{PREFIX}/auth/me")
    def current_actor(request: Request):
        return auth.actor(request.state.actor_id)

    @app.get(f"{PREFIX}/auth/csrf")
    def refresh_csrf(request: Request):
        # Same-origin GET permits a reload to recover a synchronizer token.
        # Cookie is HttpOnly; the raw token stays in browser memory, never URL.
        if request.headers.get("x-csrf-refresh") != "1":
            raise DomainError(403, "CSRF_REFRESH_DENIED", "Explicit session refresh required")
        token = secrets.token_urlsafe(32)
        current = request.state.session
        changed = database.auth_sessions.update_one({"_id": current["_id"], "revoked_at": None,
            "revision": current["revision"]}, {"$set": {"csrf_sha256": hashlib.sha256(token.encode()).hexdigest()},
            "$inc": {"revision": 1}})
        if changed.matched_count != 1:
            raise DomainError(409, "SESSION_CHANGED", "Session changed; reload authentication")
        return {"csrf_token": token}

    @app.delete(f"{PREFIX}/auth/session", status_code=204)
    def logout(request: Request):
        auth.revoke(request.cookies.get(COOKIE), request_id=request.state.request_id)
        response = Response(status_code=204)
        response.delete_cookie(COOKIE, path="/api/v1", httponly=True, samesite="lax")
        return response

    @app.get(f"{PREFIX}/workspaces")
    def workspaces(request: Request, limit: int = 25, cursor: str | None = None):
        if not 1 <= limit <= 100 or cursor is not None and not ObjectId.is_valid(cursor):
            raise DomainError(400, "INVALID_PAGINATION", "Invalid pagination")
        values = auth.list_workspaces(request.state.actor_id)
        values = sorted((row for row in values if cursor is None or row["id"] > cursor), key=lambda row: row["id"])
        page = values[:limit]
        return {"items": page, "page": {"limit": limit, "has_more": len(values) > limit,
                "next_cursor": page[-1]["id"] if len(values) > limit else None}}

    @app.post(f"{PREFIX}/workspaces/{{workspace_id}}/rubrics", status_code=201)
    async def create_rubric(workspace_id: str, request: Request, response: Response):
        value = rubrics.create(request.state.actor_id, workspace_id, await json_body(request),
                               idempotency_key=_key(request), request_id=request.state.request_id)
        return _etag(response, value)

    @app.get(f"{PREFIX}/workspaces/{{workspace_id}}/rubrics")
    def list_rubrics(workspace_id: str, request: Request, limit: int = 25, cursor: str | None = None):
        return rubrics.list(request.state.actor_id, workspace_id, limit=limit, cursor=cursor)

    @app.get(f"{PREFIX}/workspaces/{{workspace_id}}/rubrics/{{rubric_id}}")
    def get_rubric(workspace_id: str, rubric_id: str, request: Request, response: Response):
        return _etag(response, rubrics.get(request.state.actor_id, workspace_id, rubric_id))

    @app.post(f"{PREFIX}/workspaces/{{workspace_id}}/rubrics/{{rubric_id}}/versions", status_code=201)
    async def clone_rubric(workspace_id: str, rubric_id: str, request: Request, response: Response):
        return _etag(response, rubrics.clone_version(
            request.state.actor_id, workspace_id, rubric_id, await json_body(request),
            expected_revision=_revision(request), idempotency_key=_key(request),
            request_id=request.state.request_id))

    @app.get(f"{PREFIX}/workspaces/{{workspace_id}}/rubrics/{{rubric_id}}/versions")
    def list_rubric_versions(workspace_id: str, rubric_id: str, request: Request,
                            limit: int = 25, cursor: str | None = None):
        return rubrics.list_versions(request.state.actor_id, workspace_id, rubric_id,
                                    limit=limit, cursor=cursor)

    @app.get(f"{PREFIX}/workspaces/{{workspace_id}}/rubric-versions/{{version_id}}")
    def get_rubric_version(workspace_id: str, version_id: str, request: Request, response: Response):
        return _etag(response, rubrics.get_version(request.state.actor_id, workspace_id, version_id))

    @app.put(f"{PREFIX}/workspaces/{{workspace_id}}/rubric-versions/{{version_id}}")
    async def update_rubric(workspace_id: str, version_id: str, request: Request, response: Response):
        return _etag(response, rubrics.update_draft(
            request.state.actor_id, workspace_id, version_id, await json_body(request),
            expected_revision=_revision(request), request_id=request.state.request_id))

    @app.post(f"{PREFIX}/workspaces/{{workspace_id}}/rubric-versions/{{version_id}}:publish")
    def publish_rubric(workspace_id: str, version_id: str, request: Request, response: Response):
        return _etag(response, rubrics.publish_version(
            request.state.actor_id, workspace_id, version_id,
            expected_revision=_revision(request), idempotency_key=_key(request),
            request_id=request.state.request_id))

    storage_root = private_root or Path(__file__).resolve().parents[5] / "var/app-mongo"
    app.include_router(document_router(
        database, storage_root,
        transaction_mode=transaction_mode, prefix=PREFIX, key_reader=_key, revision_reader=_revision))
    app.include_router(analysis_router(database, storage_root, transaction_mode=transaction_mode,
        prefix=PREFIX, json_reader=json_body, key_reader=_key, revision_reader=_revision))
    return app
