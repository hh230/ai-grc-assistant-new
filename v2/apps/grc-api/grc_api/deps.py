"""Dependency providers — the composition seams the routes read through.

Each provider pulls a wired object off `app.state` (built once in `create_app`), so routes depend on
*ports* (`MissionListReadModel`), never on a concrete adapter. Swapping the in-memory read model for
the Postgres one is a composition change here, invisible to the routes.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from typing import Annotated, Any
from uuid import uuid4

from document_read_model import DocumentReadModel
from fastapi import Depends, Request
from governance_discovery.engine import DiscoveryEngine
from governance_plan_execution import PlanExecutionService
from governance_session import DiscoverySessionService
from mission_application import (
    ApprovalQueueProjection,
    ApproveMissionStepCommand,
    CommandContext,
    CoverageRollupProvider,
    CreateMissionCommand,
    DashboardProjection,
    ExportService,
    MissionDetailQuery,
    MissionSummaryProvider,
    RejectMissionStepCommand,
    ResultQuery,
    StartMissionCommand,
)
from mission_read_model import MissionListReadModel
from pipeline_contracts import TenantContext

from grc_api.adapters import (
    CatalogDefinitionProvider,
    CreationProjection,
    EngineMissionCreator,
    EngineWorkflow,
    ReadModelProjection,
    StoreMissionAccess,
)
from grc_api.document_adapters import DocumentIngestionService
from grc_api.security import require_tenant


def get_mission_read_model(request: Request) -> MissionListReadModel:
    read_model: MissionListReadModel = request.app.state.mission_read_model
    return read_model


def get_approval_queue(request: Request) -> ApprovalQueueProjection:
    """The Decisions read (Slice S6): the Approval Queue Projection composed from the store + the
    reused mission-read-model — computed-on-read, no stored table."""
    state = request.app.state
    return ApprovalQueueProjection(state.mission_reader, state.mission_read_model)


def get_document_read_model(request: Request) -> DocumentReadModel:
    read_model: DocumentReadModel = request.app.state.document_read_model
    return read_model


def get_document_ingestion(request: Request) -> DocumentIngestionService:
    """The document write side (Slice S4): the ingestion service composed from the shared knowledge
    base + the document read model — Upload → Ingestion → Document Projection behind one seam."""
    state = request.app.state
    return DocumentIngestionService(state.knowledge_base, state.document_read_model)


def get_mission_detail_query(request: Request) -> MissionDetailQuery:
    """The read-side Application Service the detail route calls. Composed from the wired store +
    read model on `app.state`; the route stays a thin adapter (ADR 0052)."""
    return MissionDetailQuery(
        request.app.state.mission_reader, request.app.state.mission_read_model
    )


def get_result_query(request: Request) -> ResultQuery:
    """The Result read-side service (Slice S3): store + read model + the builder registry."""
    state = request.app.state
    return ResultQuery(state.mission_reader, state.mission_read_model, state.result_registry)


def get_dashboard_projection(request: Request) -> DashboardProjection:
    """The Dashboard Projection (Slice S5): a computed-on-read aggregation composing two providers —
    a MissionSummaryProvider over the reused mission-read-model, and a CoverageRollupProvider over
    the reused ResultQuery. Nothing is stored; the projection is assembled here at read time."""
    state = request.app.state
    result_query = ResultQuery(
        state.mission_reader, state.mission_read_model, state.result_registry
    )
    return DashboardProjection(
        MissionSummaryProvider(state.mission_read_model),
        CoverageRollupProvider(state.mission_read_model, result_query),
    )


def get_export_service(request: Request) -> ExportService:
    export_service: ExportService = request.app.state.export_service
    return export_service


def require_context(
    request: Request,
    tenant: Annotated[TenantContext, Depends(require_tenant)],
) -> CommandContext:
    """Build the Application `CommandContext` from the resolved identity (tenant + principal +
    roles) and the optional correlation/request headers. The write commands take this, never the raw
    identity — identity is explicit, not derived from the tenant (ADR 0054)."""
    return CommandContext(
        tenant_id=tenant.tenant_id,
        principal_id=tenant.principal_id,
        roles=tuple(tenant.roles),
        correlation_id=request.headers.get("X-Correlation-Id", ""),
        request_id=request.headers.get("X-Request-Id", ""),
    )


class _ScopedCommand:
    """Runs a command inside one **command scope** (ADR 0055).

    Opening the scope creates the unit of work and, on its single connection, the mission store, the
    outbox sink and the projection; the command runs; clean exit commits all three together and an
    exception rolls all three back. The route sees an object with `.execute(...)` and knows nothing
    about transactions — and no store outlives the call, because none was ever built outside it.
    """

    def __init__(self, scope_factory: Any, build: Callable[[Any], Any]) -> None:
        self._scope_factory = scope_factory
        self._build = build

    def execute(self, *args: Any, **kwargs: Any) -> Any:
        with self._scope_factory() as scope:
            return self._build(scope).execute(*args, **kwargs)


def _scoped(request: Request, build: Callable[[Any], Any]) -> _ScopedCommand:
    return _ScopedCommand(request.app.state.command_scope, build)


def _mission_command(scope: Any, command_type: Any) -> Any:
    """The three write collaborators, bound to this scope's one connection. The workflow records a
    launch into the scope's buffer (fired after commit, ADR 0055), so it takes `scope.launches`."""
    return command_type(
        access=StoreMissionAccess(scope.store),
        projection=ReadModelProjection(scope.mission_read_model),
        workflow=EngineWorkflow(scope.engine, scope.launches),
    )


def get_approve_command(request: Request) -> Any:
    return _scoped(request, lambda scope: _mission_command(scope, ApproveMissionStepCommand))


def get_reject_command(request: Request) -> Any:
    return _scoped(request, lambda scope: _mission_command(scope, RejectMissionStepCommand))


def get_mission_catalog(request: Request) -> Any:
    """The bundled Mission Catalog — used at the boundary to validate the chosen type (∈ the 6)."""
    return request.app.state.mission_catalog


def get_create_command(request: Request) -> Any:
    """The create command (Slice S7): define (catalog) → create+plan (engine) → project the creation
    (read model). No mission is loaded — it makes one; no Draft is persisted."""
    catalog = request.app.state.mission_catalog
    return _scoped(
        request,
        lambda scope: CreateMissionCommand(
            definer=CatalogDefinitionProvider(catalog),
            creator=EngineMissionCreator(scope.engine),
            projection=CreationProjection(scope.mission_read_model),
        ),
    )


def get_start_command(request: Request) -> Any:
    """The start command (Slice S7): reuses the S2 MissionCommand template (load → start → proj)."""
    return _scoped(request, lambda scope: _mission_command(scope, StartMissionCommand))


# --- Governance Discovery (ADR 0066) --------------------------------------------------------


def get_discovery_store(request: Request) -> Iterator[Any]:
    """A fresh store per request, closed on return — the same per-call-connection discipline
    `DurableMissionReader` follows (ADR 0055: no durable store lives on `app.state`). Built through
    `app.state.discovery_store_factory` (defaults to `PostgresGovernanceStore`; a test injects an
    in-memory fake via `create_app(discovery_store_factory=...)`, exactly like `mission_store`/
    `read_model` do for the mission subsystem)."""
    store = request.app.state.discovery_store_factory()
    try:
        yield store
    finally:
        close = getattr(store, "close", None)
        if close is not None:
            close()


def get_discovery_service(
    request: Request,
    store: Annotated[Any, Depends(get_discovery_store)],
) -> DiscoverySessionService:
    """The engine (pure, stateless, safe to share across requests) is built once in `create_app`
    and lives on `app.state.discovery_engine`; only the store is per-request."""
    engine: DiscoveryEngine = request.app.state.discovery_engine
    return DiscoverySessionService(engine, store, new_id=lambda: str(uuid4()), now=time.time)


# --- Governance Plan Execution (ADR 0066 §5) -------------------------------------------------


def get_governance_store(request: Request) -> Iterator[Any]:
    """Plan Execution reads/writes through the same store class and the same per-request-connection
    discipline as Discovery (`get_discovery_store`) — `PostgresGovernanceStore` carries both
    subsystems' tables (ADR 0066 §5.7 kept them in one store, one database)."""
    store = request.app.state.discovery_store_factory()
    try:
        yield store
    finally:
        close = getattr(store, "close", None)
        if close is not None:
            close()


def get_plan_execution_service(
    request: Request,
    store: Annotated[Any, Depends(get_governance_store)],
) -> PlanExecutionService:
    """`mark_done`/`reopen`/`attach_evidence`/`current_maturity()` (ADR 0066 §5) — the engine is the
    same shared, stateless one Discovery uses; only the store is per-request."""
    engine: DiscoveryEngine = request.app.state.discovery_engine
    return PlanExecutionService(engine, store, new_id=lambda: str(uuid4()), now=time.time)
