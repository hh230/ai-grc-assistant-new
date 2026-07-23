"""The FastAPI application factory — the V1 Product API Host (ADR 0052).

`create_app` is a **composition root**: it builds the wired object graph once (the tenant resolver
and the read model), stores it on `app.state`, registers the uniform error handlers, and mounts the
health probe and the versioned `/v1` surface. No business logic lives here — the host validates,
authenticates, scopes to a tenant, and dispatches to `v2/packages/*`.

Adapters are injectable so tests (and later, deployment) swap them without touching the routes: the
default read model is the in-memory one; the Postgres adapter drops in at the same seam. The default
identity provider is the seeded development one; OIDC replaces it here alone.
"""

from __future__ import annotations

from typing import Any

from assistant_runtime.builtin import default_mission_catalog
from document_read_model import DocumentReadModel, InMemoryDocumentReadModel
from fastapi import FastAPI
from framework_library import FrameworkLibrary
from knowledge_runtime import TenantKnowledgeBase
from mission_application import DeliverableBuilderRegistry, ExportService
from mission_engine import EchoExecutor, InMemoryMissionStore, MissionEngine
from mission_read_model import InMemoryMissionListReadModel, MissionListReadModel

from grc_api.errors import register_exception_handlers
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
    read_model: MissionListReadModel | None = None,
    identity_provider: IdentityProvider | None = None,
    mission_store: Any | None = None,
    mission_engine: Any | None = None,
    document_read_model: DocumentReadModel | None = None,
    knowledge_base: TenantKnowledgeBase | None = None,
) -> FastAPI:
    app = FastAPI(title=API_TITLE, version=API_VERSION)

    app.state.mission_read_model = read_model or InMemoryMissionListReadModel()
    app.state.identity_provider = identity_provider or development_identity_provider()
    # The Core store the detail endpoint reads live missions through (Slice S2). Default in-memory;
    # a Postgres-backed store drops in at this same seam.
    store = mission_store if mission_store is not None else InMemoryMissionStore()
    app.state.mission_store = store
    # The Core engine the write commands drive (approve/reject). Shares the store so load + save are
    # consistent. Dev uses the reference EchoExecutor; a real executor drops in at this seam.
    app.state.mission_engine = (
        mission_engine if mission_engine is not None else MissionEngine(store, EchoExecutor())
    )
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
    app.state.document_read_model = document_read_model or InMemoryDocumentReadModel()
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
