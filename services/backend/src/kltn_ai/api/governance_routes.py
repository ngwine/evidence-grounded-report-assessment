"""Authenticated selector for pre-existing, currently usable upload approvals."""

from pathlib import Path

from fastapi import APIRouter, Request

from ..domain.documents import DocumentService
from ..domain.governance_options import GovernanceOptionsService


def governance_router(database, private_root: Path, *, transaction_mode: bool,
                      prefix: str) -> APIRouter:
    router = APIRouter(prefix=prefix)

    @router.get("/workspaces/{workspace_id}/upload-authorizations")
    def upload_authorizations(workspace_id: str, request: Request, kind: str,
                              limit: int = 25, cursor: str | None = None):
        documents = DocumentService(database, private_root, transactional=transaction_mode)
        return GovernanceOptionsService(database, documents).list(request.state.actor_id,
            workspace_id, kind=kind, limit=limit, cursor=cursor)

    return router
