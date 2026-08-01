"""The FastAPI app for the Approval API (S5a) + the static UI (S5b).

Every route talks ONLY to ``ApprovalService`` over a ``FileApprovalStore`` — never to the coordinator
and never to the lifecycle. A grant/reject is recorded durably in the shared store; the daemon drains
it on its next tick and applies it through the adapter (``notify``). That is the whole file-store +
reconcile contract: this surface's job ends at *recording a decision*.

``create_app(config)`` builds the app; a fresh ``ApprovalService`` is made per request so it always
reads the current file (the daemon may have written it). The single-page UI polls ``GET /api/approvals``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from devteam_approval import (
    Actor,
    ApprovalError,
    ApprovalRequest,
    ApprovalService,
    FileApprovalStore,
)
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from devteam_approval_api.config import ApprovalApiConfig, load_config

_STATIC_DIR = Path(__file__).parent / "static"


class DecisionBody(BaseModel):
    """Who is deciding + an optional note. ``actor_id`` is required; the rest enriches the audit."""

    actor_id: str
    actor_name: str = ""
    role: str = ""
    comment: str = ""


def create_app(config: ApprovalApiConfig | None = None) -> FastAPI:
    settings = config or load_config()

    def service() -> ApprovalService:
        # Fresh per request → always reads the current shared file (the daemon writes it too).
        return ApprovalService(FileApprovalStore(settings.store_path))

    app = FastAPI(title="Rasheed — Approvals", docs_url=None, redoc_url=None)

    @app.get("/api/approvals")
    def list_pending() -> dict[str, Any]:
        return {"approvals": [_view(r) for r in service().pending()]}

    @app.get("/api/approvals/{request_id}")
    def get_one(request_id: str) -> dict[str, Any]:
        request = service().get(request_id)
        if request is None:
            raise HTTPException(status_code=404, detail="no such approval")
        return _view(request)

    @app.post("/api/approvals/{request_id}/grant")
    def grant(request_id: str, body: DecisionBody) -> dict[str, Any]:
        return _decide(service(), request_id, body, approve=True)

    @app.post("/api/approvals/{request_id}/reject")
    def reject(request_id: str, body: DecisionBody) -> dict[str, Any]:
        return _decide(service(), request_id, body, approve=False)

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(str(_STATIC_DIR / "index.html"))

    if _STATIC_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
    return app


def _decide(
    service: ApprovalService, request_id: str, body: DecisionBody, *, approve: bool
) -> dict[str, Any]:
    actor_id = body.actor_id.strip()
    if not actor_id:
        raise HTTPException(status_code=400, detail="actor_id is required")
    actor = Actor(actor_id=actor_id, name=body.actor_name.strip(), role=body.role.strip())
    if service.get(request_id) is None:
        raise HTTPException(status_code=404, detail="no such approval")
    try:
        if approve:
            request = service.approve(request_id, actor=actor, comment=body.comment)
        else:
            request = service.reject(request_id, actor=actor, comment=body.comment)
    except ApprovalError as exc:  # already decided / no longer pending
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _view(request)


def _view(request: ApprovalRequest) -> dict[str, Any]:
    """The shape the UI renders. ``target_ref`` is ``mission_type:asset:signature`` (the correlation
    ref), split out for display; the rich human context lives in ``reason``."""
    mission_type, _, rest = request.target_ref.partition(":")
    asset = rest.partition(":")[0]
    decision = request.current_decision
    return {
        "id": request.id,
        "target_ref": request.target_ref,
        "mission_type": mission_type,
        "asset": asset,
        "status": request.status.value,
        "requirement": request.policy.requirement,
        "role": request.policy.required_role,
        "reason": request.policy.reason,
        "expires_at": request.expires_at,
        "decision": None
        if decision is None
        else {
            "outcome": decision.outcome.value,
            "actor_id": decision.actor.actor_id,
            "actor_name": decision.actor.name,
            "role": decision.actor.role,
            "comment": decision.comment,
            "at": decision.at,
        },
    }
