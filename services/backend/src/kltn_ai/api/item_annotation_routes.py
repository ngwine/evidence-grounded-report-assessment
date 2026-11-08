"""Authenticated, private model-visible item review endpoints."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from fastapi import APIRouter, Request, Response
from fastapi.encoders import jsonable_encoder
from starlette.concurrency import run_in_threadpool

from ..domain.item_annotations import ItemAnnotationService


def item_annotation_router(database, private_root: Path, *, transaction_mode: bool,
                           prefix: str, json_reader: Callable, key_reader: Callable,
                           revision_reader: Callable) -> APIRouter:
    router = APIRouter(prefix=prefix + "/workspaces/{workspace_id}/analysis-runs/{run_id}")

    def service():
        return ItemAnnotationService(database, private_root, transactional=transaction_mode)

    @router.get("/annotation-items")
    def items(workspace_id: str, run_id: str, request: Request, response: Response,
              limit: int = 25, cursor: str | None = None):
        output = service().list_items(request.state.actor_id, workspace_id, run_id, limit=limit, cursor=cursor)
        response.headers["ETag"] = f'"rev-{output["run_revision"]}"'
        return output

    @router.post("/item-annotations", status_code=201)
    async def annotate(workspace_id: str, run_id: str, request: Request, response: Response):
        output = await run_in_threadpool(service().create, request.state.actor_id, workspace_id,
            run_id, await json_reader(request), expected_revision=revision_reader(request),
            idempotency_key=key_reader(request), request_id=request.state.request_id)
        response.headers["ETag"] = f'"rev-{output["run_revision"]}"'
        return output

    @router.get("/item-annotations")
    def history(workspace_id: str, run_id: str, request: Request, response: Response,
                limit: int = 25, cursor: str | None = None):
        output = service().history(request.state.actor_id, workspace_id, run_id, limit=limit, cursor=cursor)
        response.headers["ETag"] = f'"rev-{output["run_revision"]}"'
        return output

    @router.get("/item-annotations/export")
    def export(workspace_id: str, run_id: str, request: Request):
        output = service().export(request.state.actor_id, workspace_id, run_id)
        payload = json.dumps(jsonable_encoder(output), ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        return Response(payload, media_type="application/json", headers={"Cache-Control": "no-store, private",
            "Content-Disposition": f'attachment; filename="model-visible-review-{output["analysis_run_id"]}.json"'})

    return router
