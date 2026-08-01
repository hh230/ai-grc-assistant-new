"""The FastAPI application factory — the V1 Product API Host (ADR 0052).

`create_app` is a **composition root**: it builds the wired object graph once (the tenant resolver
and the read model), stores it on `app.state`, registers the uniform error handlers, and mounts the
health probe and the versioned `/v1` surface. No business logic lives here — the host validates,
authenticates, scopes to a tenant, and dispatches to `v2/packages/*`.

Adapters are injectable so tests (and later, deployment) swap them without touching the routes. The
**read models are durable by default** — an unconfigured deployment gets PostgreSQL, not an
in-memory projection (see `composition`); a test that wants in-memory asks for it explicitly with
`storage=Storage.MEMORY`. The store, the executor, and the identity provider are still the
development ones, each replaced at its own seam.
"""

from __future__ import annotations

from typing import Any

from assistant_runtime.builtin import default_mission_catalog
from document_read_model import DocumentReadModel
from fastapi import FastAPI
from framework_library import FrameworkLibrary
from knowledge_runtime import TenantKnowledgeBase
from mission_application import DeliverableBuilderRegistry, ExportService
from mission_engine import EchoExecutor, InMemoryMissionStore, MissionEngine
from mission_engine.ports import ExecutionPort
from mission_read_model import MissionListReadModel, PostgresMissionListReadModel

from grc_api.adapters import ReadModelProjection
from grc_api.composition import (
    DurableMissionReader,
    Storage,
    Tables,
    build_document_read_model,
    build_mission_read_model,
    durable_command_scope_factory,
    memory_command_scope_factory,
    open_autocommit_connection,
)
from grc_api.errors import register_exception_handlers
from grc_api.launch import DurableMissionLaunch, MemoryMissionLaunch, MissionLaunchPort
from grc_api.result_adapters import (
    BundledDeliverableProvider,
    DocxExporter,
    GapAssessmentResultBuilder,
    GenericResultBuilder,
    MarkdownExporter,
    PdfExporter,
)
from grc_api.routers.approvals import router as approvals_router
from grc_api.routers.dashboard import router as dashboard_router
from grc_api.routers.documents import router as documents_router
from grc_api.routers.health import router as health_router
from grc_api.routers.missions import router as missions_router
from grc_api.security import IdentityProvider, development_identity_provider

API_TITLE = "Rasheed GRC API"
API_VERSION = "0.1.0"


def create_app(
    *,
    storage: Storage = Storage.DURABLE,
    tables: Tables | None = None,
    executor: ExecutionPort | None = None,
    read_model: MissionListReadModel | None = None,
    identity_provider: IdentityProvider | None = None,
    mission_store: Any | None = None,
    mission_engine: Any | None = None,
    document_read_model: DocumentReadModel | None = None,
    knowledge_base: TenantKnowledgeBase | None = None,
) -> FastAPI:
    app = FastAPI(title=API_TITLE, version=API_VERSION)

    # `storage` selects the read-model adapters: DURABLE (the production default — an unconfigured
    # deployment gets PostgreSQL, never an in-memory projection that loses a tenant's work) or
    # MEMORY, which a test asks for explicitly. An injected adapter still wins over both.
    where = tables or Tables()
    app.state.mission_read_model = read_model or build_mission_read_model(storage, where)
    app.state.identity_provider = identity_provider or development_identity_provider()
    # Storage, per ADR 0055. **No durable store lives here.** Reads go through a reader service that
    # creates a store per read and discards it; writes go through a factory that creates one
    # transaction's worth of collaborators per command. What is long-lived is configuration, never a
    # store — so there is nothing for a later change to accidentally share process-wide.
    run_step: ExecutionPort = executor or EchoExecutor()
    launch: MissionLaunchPort
    if storage is Storage.MEMORY:
        # In-memory state has to live somewhere: the dictionary IS the storage, and no connection or
        # transaction is involved. `mission_store` / `mission_engine` stay injectable for this path.
        memory_store = mission_store if mission_store is not None else InMemoryMissionStore()
        memory_engine = (
            mission_engine if mission_engine is not None else MissionEngine(memory_store, run_step)
        )
        app.state.mission_reader = memory_store
        # Execution starts through the launch boundary (ADR 0055), never from a command directly.
        # It projects its result to the shared read model when it finishes (execution is a write).
        memory_projection = ReadModelProjection(app.state.mission_read_model)
        launch = MemoryMissionLaunch(memory_engine, memory_store, memory_projection.project)
        app.state.command_scope = memory_command_scope_factory(
            memory_engine, memory_store, app.state.mission_read_model, launch
        )
    else:
        app.state.mission_reader = DurableMissionReader(where.missions)
        launch = DurableMissionLaunch(
            executor=run_step,
            missions_table=where.missions,
            outbox_table=where.outbox,
            connect=open_autocommit_connection,
            project=lambda conn, mission: ReadModelProjection(
                PostgresMissionListReadModel(connection=conn, table=where.missions_view)
            ).project(mission),
        )
        app.state.command_scope = durable_command_scope_factory(run_step, where, launch)
    # The Result builder registry (Slice S3): each mission type gets its builder; the default is the
    # generic one. Concrete builders + the framework provider are composed here, behind the ports.
    provider = BundledDeliverableProvider()
    frameworks = FrameworkLibrary.from_bundled()
    app.state.result_registry = DeliverableBuilderRegistry(
        default=GenericResultBuilder(provider),
        by_type={"gap_assessment": GapAssessmentResultBuilder(provider, frameworks)},
    )
    app.state.export_service = ExportService(
        {"md": MarkdownExporter(), "docx": DocxExporter(), "pdf": PdfExporter()}
    )
    # Knowledge (Slice S4): the Document read model the view lists, plus the shared knowledge base
    # the upload ingests into. One base holds every tenant's chunks (each chunk tenant-scoped), so
    # retrieval never crosses the boundary. Both drop in at this seam (Postgres / pgvector later).
    app.state.document_read_model = document_read_model or build_document_read_model(storage, where)
    app.state.knowledge_base = knowledge_base or TenantKnowledgeBase()
    # The Mission Catalog (Slice S7): a Mission type IS a plan factory. The create command reads it
    # to turn a chosen type + scope into the Core's (goal, plan). The bundled catalog holds the 6.
    app.state.mission_catalog = default_mission_catalog()

    register_exception_handlers(app)
    app.include_router(health_router)
    app.include_router(missions_router, prefix="/v1")
    app.include_router(documents_router, prefix="/v1")
    app.include_router(dashboard_router, prefix="/v1")
    app.include_router(approvals_router, prefix="/v1")

    return app


# A module-level ASGI app so `uvicorn grc_api.app:app` works — the intuitive entrypoint. Without it,
# uvicorn fails with "Attribute 'app' not found in module 'grc_api.app'" and the API never starts,
# so every `/v1` fetch fails at the network layer and the UI shows "Load failed". The package
# re-exports this same instance as `grc_api:app` (unseeded); the seeded demo app is
# `grc_api.dev:app`.
app = create_app()
