"""The composition root — where abstractions are bound to concrete adapters.

This is the *only* place that decides which store, which authenticator, and which LLM provider
the platform runs against. Everything downstream (routers, buses, use cases) depends on ports,
so changing a binding here never ripples into business code (CLAUDE.md §6 #5, ADR-0013).
"""

from __future__ import annotations

from grc_services.shared.context import Principal

from .ai import build_embedding_model, build_orchestrator
from .container import AppContainer
from .observability import get_logger
from .runtime import (
    InMemoryDatabase,
    InMemoryUnitOfWork,
    InProcessCommandBus,
    InProcessQueryBus,
    LoggingEventDispatcher,
    RbacAuthorizationService,
    build_registry,
)
from .security.authentication import (
    StaticTokenAuthenticator,
    TokenAuthenticator,
    principal_from_claims,
)
from .settings import Settings

_logger = get_logger("grc_api.composition")

# The well-known local development bearer token. Only seeded outside production.
DEV_BEARER_TOKEN = "dev-token"  # noqa: S105 - not a secret; a fixed local convenience token
_DEV_PRINCIPAL_CLAIMS = {
    "user_id": "dev-user",
    "organization_id": "dev-org",
    "roles": ["owner"],
}


def build_authenticator(settings: Settings) -> TokenAuthenticator:
    """Build the bearer-token authenticator from configuration (default deny on unknown token)."""
    tokens: dict[str, Principal] = {
        token: principal_from_claims(claims) for token, claims in settings.auth_token_map().items()
    }
    if not tokens and settings.auth_seed_dev_principal and not settings.is_production:
        tokens[DEV_BEARER_TOKEN] = principal_from_claims(_DEV_PRINCIPAL_CLAIMS)
        _logger.warning(
            "dev_principal_seeded",
            extra={"detail": "seeded local dev bearer token; never use outside local/dev"},
        )
    _logger.info("authenticator_ready", extra={"token_count": len(tokens)})
    return StaticTokenAuthenticator(tokens)


def build_container(settings: Settings) -> AppContainer:
    registry = build_registry()
    events = LoggingEventDispatcher()
    authz = RbacAuthorizationService()

    if settings.store_backend == "memory":
        db = InMemoryDatabase()
        database: InMemoryDatabase | None = db

        def uow_factory() -> InMemoryUnitOfWork:
            return InMemoryUnitOfWork(db)

    else:  # "sqlalchemy"
        # The production Postgres/pgvector binding (grc_persistence.SqlAlchemyUnitOfWork) is
        # gated on ADL-0008 (the knowledge-persistence re-alignment), which is a Product Owner
        # decision. Fail fast and explicitly rather than start in a misleading state.
        raise RuntimeError(
            "store_backend='sqlalchemy' is not yet selectable: the production persistence "
            "binding is gated on ADL-0008 (knowledge-persistence re-alignment). Use "
            "store_backend='memory' until that decision lands."
        )

    command_bus = InProcessCommandBus(
        uow_factory=uow_factory, events=events, authz=authz, registry=registry
    )
    query_bus = InProcessQueryBus(uow_factory=uow_factory, authz=authz, registry=registry)
    authenticator = build_authenticator(settings)
    orchestrator = build_orchestrator(settings)
    embedding_model = build_embedding_model(settings)

    _logger.info(
        "container_built",
        extra={
            "store_backend": settings.store_backend,
            "llm_provider": settings.llm_provider,
            "commands": len(registry.commands),
            "queries": len(registry.queries),
        },
    )
    return AppContainer(
        settings=settings,
        command_bus=command_bus,
        query_bus=query_bus,
        authenticator=authenticator,
        authz=authz,
        events=events,
        orchestrator=orchestrator,
        embedding_model=embedding_model,
        database=database,
        llm_provider=settings.llm_provider,
        registered_commands=len(registry.commands),
        registered_queries=len(registry.queries),
    )
