"""Operational health endpoints (unauthenticated, outside the versioned API).

``/healthz`` is liveness (the process is up); ``/readyz`` is readiness (the object graph is wired
and able to serve). Kept deliberately free of business logic and auth so orchestrators and load
balancers can probe them.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from ..container import AppContainer
from ..schemas.common import ApiModel
from ..security.dependencies import get_container

router = APIRouter(tags=["health"])


class LivenessResponse(ApiModel):
    status: str


class ReadinessResponse(ApiModel):
    status: str
    environment: str
    store_backend: str
    llm_provider: str
    registered_commands: int
    registered_queries: int


@router.get("/healthz", response_model=LivenessResponse, summary="Liveness probe")
async def healthz() -> LivenessResponse:
    return LivenessResponse(status="ok")


@router.get("/readyz", response_model=ReadinessResponse, summary="Readiness probe")
async def readyz(
    container: Annotated[AppContainer, Depends(get_container)],
) -> ReadinessResponse:
    return ReadinessResponse(
        status="ready",
        environment=container.settings.app_env,
        store_backend=container.settings.store_backend,
        llm_provider=container.llm_provider,
        registered_commands=container.registered_commands,
        registered_queries=container.registered_queries,
    )
