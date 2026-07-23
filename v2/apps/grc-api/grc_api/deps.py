"""Dependency providers — the composition seams the routes read through.

Each provider pulls a wired object off `app.state` (built once in `create_app`), so routes depend on
*ports* (`MissionListReadModel`), never on a concrete adapter. Swapping the in-memory read model for
the Postgres one is a composition change here, invisible to the routes.
"""

from __future__ import annotations

from typing import Annotated, Any

from document_read_model import DocumentReadModel
from fastapi import Depends, Request
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
    return ApprovalQueueProjection(state.mission_store, state.mission_read_model)


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
        request.app.state.mission_store, request.app.state.mission_read_model
    )


def get_result_query(request: Request) -> ResultQuery:
    """The Result read-side service (Slice S3): store + read model + the builder registry."""
    state = request.app.state
    return ResultQuery(state.mission_store, state.mission_read_model, state.result_registry)


def get_dashboard_projection(request: Request) -> DashboardProjection:
    """The Dashboard Projection (Slice S5): a computed-on-read aggregation composing two providers —
    a MissionSummaryProvider over the reused mission-read-model, and a CoverageRollupProvider over
    the reused ResultQuery. Nothing is stored; the projection is assembled here at read time."""
    state = request.app.state
    result_query = ResultQuery(state.mission_store, state.mission_read_model, state.result_registry)
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


def _adapters(request: Request) -> tuple[StoreMissionAccess, ReadModelProjection, EngineWorkflow]:
    state = request.app.state
    return (
        StoreMissionAccess(state.mission_store),
        ReadModelProjection(state.mission_read_model),
        EngineWorkflow(state.mission_engine),
    )


def get_approve_command(request: Request) -> ApproveMissionStepCommand:
    access, projection, workflow = _adapters(request)
    return ApproveMissionStepCommand(access=access, projection=projection, workflow=workflow)


def get_reject_command(request: Request) -> RejectMissionStepCommand:
    access, projection, workflow = _adapters(request)
    return RejectMissionStepCommand(access=access, projection=projection, workflow=workflow)


def get_mission_catalog(request: Request) -> Any:
    """The bundled Mission Catalog — used at the boundary to validate the chosen type (∈ the 6)."""
    return request.app.state.mission_catalog


def get_create_command(request: Request) -> CreateMissionCommand:
    """The create command (Slice S7): define (catalog) → create+plan (engine) → project the creation
    (read model). No mission is loaded — it makes one; no Draft is persisted."""
    state = request.app.state
    return CreateMissionCommand(
        definer=CatalogDefinitionProvider(state.mission_catalog),
        creator=EngineMissionCreator(state.mission_engine),
        projection=CreationProjection(state.mission_read_model),
    )


def get_start_command(request: Request) -> StartMissionCommand:
    """The start command (Slice S7): reuses the S2 MissionCommand template (load → start → proj)."""
    access, projection, workflow = _adapters(request)
    return StartMissionCommand(access=access, projection=projection, workflow=workflow)
