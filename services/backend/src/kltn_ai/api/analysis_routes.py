"""Authenticated index/run/result boundaries; only worker commits AI output."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, Request, Response
from fastapi.encoders import jsonable_encoder
from starlette.concurrency import run_in_threadpool

from ..domain.analysis import AnalysisService
from ..domain.errors import DomainError
from ..domain.indexes import IndexService


def _generation(row: dict[str, Any]) -> dict[str, Any]:
    return {"id": str(row["_id"]), "document_version_id": str(row["document_version_id"]),
            "job_id": str(row["job_id"]), **{name: row[name] for name in (
                "state", "config_id", "revision", "generation_no", "chunk_count", "failure_code")}}


def _run(row: dict[str, Any]) -> dict[str, Any]:
    sources = [str(value) for value in row["source_version_ids"]]
    return {"id": str(row["_id"]), "report_version_id": str(row["document_version_id"]),
        "source_version_ids": sources,
        "source_scope_sha256": hashlib.sha256(json.dumps(sources, separators=(",", ":")).encode()).hexdigest(),
        "index_generation_ids": [str(value) for value in row["index_generation_ids"]],
        "rubric_version_id": str(row["rubric_version_id"]) if row["rubric_version_id"] else None,
        "job_id": str(row["job_id"]), **{name: row[name] for name in (
            "run_type", "config_id", "state", "revision", "failure_code", "created_at", "completed_at", "review_state")}}


def _review(row: dict[str, Any]) -> dict[str, Any]:
    return {"id": str(row["_id"]), "analysis_run_id": str(row["analysis_run_id"]),
            "reviewer_id": str(row["created_by"]), **{name: row[name] for name in (
                "decision", "reason_code", "reason_text", "based_on_revision", "created_at")}}


def analysis_router(database, private_root: Path, *, transaction_mode: bool,
                    prefix: str, json_reader: Callable, key_reader: Callable,
                    revision_reader: Callable) -> APIRouter:
    router = APIRouter(prefix=prefix)

    def indexes():
        return IndexService(database, private_root, transactional=transaction_mode)

    def analyses():
        return AnalysisService(database, private_root, transactional=transaction_mode)

    @router.post("/workspaces/{workspace_id}/document-versions/{version_id}/index-generations", status_code=202)
    async def request_index(workspace_id: str, version_id: str, request: Request):
        body = await json_reader(request)
        if (set(body) - {"config_id", "rebuild"} or body.get("config_id") not in {"bm25-smoke", "research-v0"}
                or type(body.get("rebuild", False)) is not bool):
            raise DomainError(422, "VALIDATION_FAILED", "A supported index config_id is required")
        result = await run_in_threadpool(indexes().request, request.state.actor_id, workspace_id,
            version_id, body["config_id"], idempotency_key=key_reader(request), request_id=request.state.request_id,
            rebuild=body.get("rebuild", False))
        return _generation(result["generation"])

    @router.get("/workspaces/{workspace_id}/index-generations/{generation_id}")
    def get_index(workspace_id: str, generation_id: str, request: Request, response: Response):
        value = indexes().get(request.state.actor_id, workspace_id, generation_id)
        response.headers["ETag"] = f'"rev-{value["generation"]["revision"]}"'
        return _generation(value["generation"])

    @router.post("/workspaces/{workspace_id}/reports/{report_id}/analysis-runs", status_code=202)
    async def create_run(workspace_id: str, report_id: str, request: Request):
        value = await run_in_threadpool(analyses().create, request.state.actor_id, workspace_id,
            report_id, await json_reader(request), idempotency_key=key_reader(request), request_id=request.state.request_id)
        row = value["run"]
        return {"run_id": str(row["_id"]), "job_id": str(value["job"]["_id"]), "state": row["state"]}

    @router.get("/workspaces/{workspace_id}/analysis-runs/{run_id}")
    def get_run(workspace_id: str, run_id: str, request: Request, response: Response):
        value = analyses().get(request.state.actor_id, workspace_id, run_id)
        response.headers["ETag"] = f'"rev-{value["revision"]}"'
        return _run(value)

    @router.get("/workspaces/{workspace_id}/reports/{report_id}/analysis-runs")
    def list_runs(workspace_id: str, report_id: str, request: Request,
                  limit: int = 25, cursor: str | None = None):
        values = analyses().list(request.state.actor_id, workspace_id, report_id, limit=limit, cursor=cursor)
        return {"items": [_run(item) for item in values["items"]], "page": values["page"]}

    @router.get("/workspaces/{workspace_id}/analysis-runs/{run_id}/results")
    def results(workspace_id: str, run_id: str, request: Request):
        return analyses().get_result(request.state.actor_id, workspace_id, run_id)

    @router.get("/workspaces/{workspace_id}/analysis-runs/{run_id}/evidence")
    def evidence(workspace_id: str, run_id: str, request: Request,
                 limit: int = 25, cursor: str | None = None):
        values = analyses().list_evidence(request.state.actor_id, workspace_id, run_id, limit=limit, cursor=cursor)
        output = []
        for item in values["items"]:
            output.append({"id": str(item["_id"]), "analysis_run_id": str(item["analysis_run_id"]),
                "report_version_id": str(item["document_version_id"]),
                "source_version_id": str(item["source_version_id"]) if item["source_version_id"] else None,
                **{name: item[name] for name in ("pipeline", "report_chunk_id", "source_chunk_id", "checklist_id", "evidence")}})
        return {"items": output, "page": values["page"]}

    @router.get("/workspaces/{workspace_id}/analysis-runs/{run_id}/export")
    def export(workspace_id: str, run_id: str, request: Request):
        service = analyses()
        run = service.get(request.state.actor_id, workspace_id, run_id)
        output = {"schema_version": 1, "run": _run(run),
                  "results": service.get_result(request.state.actor_id, workspace_id, run_id),
                  "interpretation": "Reviewable analysis proposal; not an official grade or plagiarism verdict"}
        payload = json.dumps(jsonable_encoder(output), ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        return Response(payload, media_type="application/json", headers={
            "Content-Disposition": f'attachment; filename="analysis-{run["_id"]}.json"'})

    @router.post("/workspaces/{workspace_id}/analysis-runs/{run_id}/reviews", status_code=201)
    async def review(workspace_id: str, run_id: str, request: Request):
        value = await run_in_threadpool(analyses().review, request.state.actor_id, workspace_id,
            run_id, await json_reader(request), expected_revision=revision_reader(request),
            request_id=request.state.request_id)
        return _review(value)

    @router.get("/workspaces/{workspace_id}/analysis-runs/{run_id}/reviews")
    def reviews(workspace_id: str, run_id: str, request: Request,
                limit: int = 25, cursor: str | None = None):
        values = analyses().list_reviews(request.state.actor_id, workspace_id, run_id, limit=limit, cursor=cursor)
        return {"items": [_review(item) for item in values["items"]], "page": values["page"]}

    return router
