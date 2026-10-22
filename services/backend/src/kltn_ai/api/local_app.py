"""Provisional localhost API for a two-pipeline feasibility vertical slice.

This endpoint set is intentionally NOT the reviewed /api/v1 contract: there is
no account authentication, MongoDB, publishing, or official grading here.
"""

from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
import json
from pathlib import Path, PureWindowsPath
from typing import Any
import zipfile
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from research.core_mvp.rubric import compile_rubric
from services.backend.src.kltn_ai.local_store import (
    LocalStore,
    METHOD_WARNINGS,
    read_json,
    sha256_bytes,
)


API_PREFIX = "/api/local/v1"
ALLOWED_ORIGINS = {"http://127.0.0.1:5173", "http://localhost:5173"}
LOCAL_MUTATION_HEADER = "x-kltn-local-ui"
ALLOWED_SUFFIXES = {".pdf", ".docx", ".txt", ".md"}
MAX_DOCUMENT_BYTES = 10 * 1024 * 1024
MAX_RUBRIC_BYTES = 256 * 1024
MAX_SOURCES = 5
MAX_REQUEST_BYTES = (MAX_SOURCES + 1) * MAX_DOCUMENT_BYTES + MAX_RUBRIC_BYTES + 1024 * 1024


def _display_name(filename: str | None) -> str:
    # Browsers can submit either POSIX basenames or Windows-style fake paths.
    name = PureWindowsPath(filename or "unnamed").name
    name = Path(name).name
    printable = "".join(char for char in name if char.isprintable()).strip()
    return printable[:120] or "unnamed"


class ReviewRequest(BaseModel):
    decision: str
    comment: str = Field(default="", max_length=2000)
    expected_revision: int = Field(ge=0)
    reviewer_name: str = Field(min_length=1, max_length=120)


async def _read_bounded(file: UploadFile, limit: int) -> bytes:
    payload = await file.read(limit + 1)
    if not payload:
        raise HTTPException(status_code=422, detail="Uploaded file is empty")
    if len(payload) > limit:
        raise HTTPException(status_code=413, detail="Uploaded file exceeds local demo limit")
    return payload


def _validated_document(filename: str | None, payload: bytes) -> str:
    suffix = Path(filename or "").suffix.casefold()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=422, detail="Document must be PDF, DOCX, TXT or MD")
    if suffix == ".pdf":
        if not payload.startswith(b"%PDF-"):
            raise HTTPException(status_code=422, detail="PDF signature is invalid")
    elif suffix == ".docx":
        if not payload.startswith(b"PK"):
            raise HTTPException(status_code=422, detail="DOCX signature is invalid")
        try:
            with zipfile.ZipFile(BytesIO(payload)) as archive:
                names = set(archive.namelist())
                if not {"word/document.xml", "[Content_Types].xml"} <= names:
                    raise ValueError("Missing DOCX entries")
                if len(names) > 1000 or sum(item.file_size for item in archive.infolist()) > 80 * 1024 * 1024:
                    raise ValueError("DOCX expansion exceeds local limit")
        except (OSError, ValueError, zipfile.BadZipFile):
            raise HTTPException(status_code=422, detail="DOCX container is invalid or too large") from None
    else:
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(status_code=422, detail="Text document must be UTF-8") from None
        if "\x00" in text:
            raise HTTPException(status_code=422, detail="Text document contains NUL bytes")
    return suffix


def _validated_rubric(filename: str | None, payload: bytes) -> None:
    if Path(filename or "").suffix.casefold() != ".json":
        raise HTTPException(status_code=422, detail="Rubric must be a JSON file")
    try:
        value = json.loads(payload.decode("utf-8"))
        compile_rubric(value)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid rubric: {exc}") from None


def _run_response(store: LocalStore, run_id: str) -> dict[str, Any]:
    try:
        job = store.get_job(run_id)
    except (ValueError, FileNotFoundError):
        raise HTTPException(status_code=404, detail="Run not found") from None
    review_record = store.get_review(run_id)
    result: dict[str, Any] = {
        "run_id": run_id,
        "job_id": job["job_id"],
        "status": job["status"],
        "config_id": job["config_id"],
        "method_warning": job["method_warning"],
        "human_review_required": True,
        "inputs": job.get("input_display_names", job["input_names"]),
        "summary": None,
        "similarity_report": None,
        "assessment_report": None,
        "review": review_record["review"],
        "revision": review_record["revision"],
        "error": job.get("error"),
        "error_code": job.get("error_code"),
        "request_id": job.get("request_id"),
    }
    if job["status"] == "SUCCEEDED":
        # A completed artifact does not grant permission to keep exposing it.
        if not _job_sources_approved(store, job):
            result["status"] = "BLOCKED"
            result["error"] = "Source approval was revoked; results are withheld."
            result["review"] = None
            return result
        output = store.run_dir(run_id) / "output"
        # These are fixed server-owned filenames, never caller-supplied paths.
        for key, filename in (
            ("summary", "mvp-summary.json"),
            ("similarity_report", "similarity-report.json"),
            ("assessment_report", "assessment-report.json"),
        ):
            result[key] = read_json(output / filename)
        if not _job_sources_approved(store, job):
            result.update(
                status="BLOCKED",
                error="Source approval was revoked; results are withheld.",
                summary=None,
                similarity_report=None,
                assessment_report=None,
                review=None,
            )
    return result


def _job_sources_approved(store: LocalStore, job: dict[str, Any]) -> bool:
    hashes = job.get("input_hashes", {}).get("sources", [])
    return bool(hashes) and all(store.source_is_approved(digest) for digest in hashes)


def create_app(*, root: Path | str | None = None, allow_test_client: bool = False) -> FastAPI:
    store = LocalStore(root)
    app = FastAPI(
        title="KLTN private local demo",
        description="Provisional localhost-only API; not an official assessment service.",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=sorted(ALLOWED_ORIGINS),
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-KLTN-Local-UI"],
        allow_credentials=False,
    )

    @app.middleware("http")
    async def local_only(request: Request, call_next):  # type: ignore[no-untyped-def]
        request.state.request_id = "req-" + uuid4().hex
        peer = request.client.host if request.client is not None else ""
        permitted_peers = {"127.0.0.1", "::1"}
        permitted_hosts = {"127.0.0.1", "localhost"}
        if allow_test_client:
            permitted_peers.add("testclient")
            permitted_hosts.add("testserver")
        host = request.headers.get("host", "").split(":", 1)[0]
        origin = request.headers.get("origin")
        if peer not in permitted_peers or host not in permitted_hosts:
            return JSONResponse(status_code=403, content={"detail": "Localhost access only"})
        if origin is not None and origin not in ALLOWED_ORIGINS:
            return JSONResponse(status_code=403, content={"detail": "Origin not allowed"})
        if request.method == "POST":
            if request.headers.get(LOCAL_MUTATION_HEADER) != "1":
                return JSONResponse(status_code=403, content={"detail": "Local mutation header required"})
            length = request.headers.get("content-length", "")
            if not length.isdecimal():
                return JSONResponse(status_code=411, content={"detail": "Content-Length required"})
            if int(length) > MAX_REQUEST_BYTES:
                return JSONResponse(status_code=413, content={"detail": "Request exceeds local demo limit"})
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    @app.get(f"{API_PREFIX}/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "scope": "private-local-demo"}

    @app.post(f"{API_PREFIX}/runs", status_code=202)
    async def create_run(
        request: Request,
        report: UploadFile = File(...),
        sources: list[UploadFile] = File(...),
        rubric: UploadFile = File(...),
        config_id: str = Form("bm25-smoke"),
    ) -> dict[str, Any]:
        if config_id not in METHOD_WARNINGS:
            raise HTTPException(status_code=422, detail="Unknown config_id")
        if not 1 <= len(sources) <= MAX_SOURCES:
            raise HTTPException(status_code=422, detail=f"Provide 1–{MAX_SOURCES} sources")
        report_data = await _read_bounded(report, MAX_DOCUMENT_BYTES)
        report_suffix = _validated_document(report.filename, report_data)
        source_data: list[tuple[str, bytes]] = []
        source_hashes: list[str] = []
        for source in sources:
            payload = await _read_bounded(source, MAX_DOCUMENT_BYTES)
            suffix = _validated_document(source.filename, payload)
            source_data.append((suffix, payload))
            source_hashes.append(sha256_bytes(payload))
        if len(set(source_hashes)) != len(source_hashes):
            raise HTTPException(status_code=422, detail="Duplicate source content")
        if sha256_bytes(report_data) in source_hashes:
            raise HTTPException(status_code=422, detail="Report cannot also be a comparison source")
        if not all(store.source_is_approved(digest) for digest in source_hashes):
            raise HTTPException(
                status_code=409,
                detail=(
                    "At least one source checksum lacks private-local rights approval. "
                    "An authorized operator must review the source and use the approval CLI first."
                ),
            )
        rubric_data = await _read_bounded(rubric, MAX_RUBRIC_BYTES)
        _validated_rubric(rubric.filename, rubric_data)
        job = store.create_run(
            report=(report_suffix, report_data),
            sources=source_data,
            rubric=rubric_data,
            config_id=config_id,
            report_display_name=_display_name(report.filename),
            source_display_names=[_display_name(source.filename) for source in sources],
            request_id=request.state.request_id,
        )
        return {
            "run_id": job["run_id"],
            "job_id": job["job_id"],
            "request_id": job["request_id"],
            "status": job["status"],
            "config_id": job["config_id"],
            "method_warning": job["method_warning"],
        }

    @app.get(f"{API_PREFIX}/runs/{{run_id}}")
    def get_run(run_id: str) -> dict[str, Any]:
        return _run_response(store, run_id)

    @app.post(f"{API_PREFIX}/runs/{{run_id}}/review")
    def review(run_id: str, payload: ReviewRequest) -> dict[str, Any]:
        if payload.decision not in {"ACCEPT", "REJECT", "DEFER"}:
            raise HTTPException(status_code=422, detail="decision must be ACCEPT, REJECT or DEFER")
        if not payload.reviewer_name.strip():
            raise HTTPException(status_code=422, detail="reviewer_name must be non-empty")
        try:
            job = store.get_job(run_id)
        except (ValueError, FileNotFoundError):
            raise HTTPException(status_code=404, detail="Run not found") from None
        if job["status"] != "SUCCEEDED":
            raise HTTPException(status_code=409, detail="Run is not ready for review")
        if not _job_sources_approved(store, job):
            raise HTTPException(status_code=409, detail="Source approval was revoked")
        with store.review_lock(run_id):
            current = store.get_review(run_id)
            if payload.expected_revision != current["revision"]:
                raise HTTPException(status_code=409, detail="Review revision conflict; reload the run")
            if not _job_sources_approved(store, job):
                raise HTTPException(status_code=409, detail="Source approval was revoked")
            revision = current["revision"] + 1
            record = {
                "revision": revision,
                "review": {
                    "decision": payload.decision,
                    "comment": payload.comment.strip(),
                    "reviewer_name": payload.reviewer_name.strip(),
                    "reviewed_at": datetime.now(timezone.utc).isoformat(),
                    "identity_status": "UNVERIFIED_LOCAL_DEMO",
                    "effect": "NO_PUBLICATION_OR_OFFICIAL_GRADE",
                },
            }
            record["history"] = [*current.get("history", []), record["review"]]
            store.write_review(run_id, record)
        return record

    return app


app = create_app()
