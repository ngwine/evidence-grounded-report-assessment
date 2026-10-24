"""Authenticated selector for pre-existing, currently usable upload approvals."""

from collections.abc import Callable
from pathlib import Path

from fastapi import APIRouter, Request
from starlette.concurrency import run_in_threadpool

from ..domain.documents import DocumentService
from ..domain.governance_options import GovernanceOptionsService
from ..domain.upload_declarations import UploadDeclarationService


def governance_router(database, private_root: Path, *, transaction_mode: bool,
                      prefix: str, json_reader: Callable, key_reader: Callable) -> APIRouter:
    router = APIRouter(prefix=prefix)

    @router.get("/workspaces/{workspace_id}/upload-authorizations")
    def upload_authorizations(workspace_id: str, request: Request, kind: str,
                              limit: int = 25, cursor: str | None = None):
        documents = DocumentService(database, private_root, transactional=transaction_mode)
        return GovernanceOptionsService(database, documents).list(request.state.actor_id,
            workspace_id, kind=kind, limit=limit, cursor=cursor)

    @router.post("/workspaces/{workspace_id}/upload-declarations", status_code=201)
    async def declare_author_consent(workspace_id: str, request: Request):
        body, key = await json_reader(request), key_reader(request)
        documents = DocumentService(database, private_root, transactional=transaction_mode)
        return await run_in_threadpool(UploadDeclarationService(documents).create,
            request.state.actor_id, workspace_id, body, idempotency_key=key,
            request_id=request.state.request_id)

    return router
