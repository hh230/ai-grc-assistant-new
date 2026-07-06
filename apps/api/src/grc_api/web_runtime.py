"""The Policy Intelligence wiring against apps/web's live PostgreSQL schema.

This is deliberately **separate** from ``composition.py``'s ``store_backend`` (which selects
the in-memory vs. the ADL-0008-gated SQLAlchemy binding for the *other*, pre-existing
command/query bus routers). Policy Intelligence does not touch that gated path or its schema
at all — it reads/writes apps/web's actual tables through ``grc_persistence_web``.

The tricky part: ``build_container`` runs synchronously at ``create_app`` time (the test
harness explicitly bypasses the async ``lifespan`` — see ``app.py``), but an asyncpg pool must
be created *inside* the event loop that will use it, or every query fails with "attached to a
different loop". So the pool is created lazily, on first use, from within a request's own
async context — not eagerly in the composition root. It is then memoized on ``app.state`` for
the life of the process. This is safe without an explicit lock because asyncio is
single-threaded and cooperative: nothing here awaits between the ``getattr`` check and the
assignment, so two concurrent requests cannot race past the check before one commits its
result — except across the one real ``await`` (``Database.connect``), which is why that path is
additionally guarded by a lazily-created ``asyncio.Lock``.
"""

from __future__ import annotations

import asyncio

from fastapi import FastAPI
from grc_persistence_web import (
    Database,
    KnowledgeItemRepository,
    PolicyMissionStore,
    PolicyRepository,
    PostgresToolInvocationRecorder,
    RegulatoryObligationRepository,
    RegulatoryRawDocumentRepository,
    WorkerControlRepository,
    WorkerEventRepository,
    WorkerRunHistoryRepository,
)
from grc_policy_analyst import ReviewPolicyQualityTool
from grc_policy_hunter import ListApplicableObligationsTool, ScanPolicyCoverageGapsTool
from grc_tools import ToolRegistry


class WebRuntimeNotConfiguredError(RuntimeError):
    """``DATABASE_URL`` is not set — Policy Intelligence needs a connection to apps/web's schema."""


def _register_policy_intelligence_tools(registry: ToolRegistry, database: Database) -> None:
    """Register Policy Hunter's and Policy Analyst's Tools (PI-P3/PI-P4) against apps/web's
    live schema. Called exactly once per process, right after a fresh ``ToolRegistry`` is
    built — ``ToolRegistry.register`` itself would raise on a second call for the same
    name/version, so this must never run twice against the same registry instance.
    """
    obligations = RegulatoryObligationRepository(database)
    raw_documents = RegulatoryRawDocumentRepository(database)
    policies = PolicyRepository(database)

    registry.register(
        ListApplicableObligationsTool(obligations=obligations, raw_documents=raw_documents)
    )
    registry.register(
        ScanPolicyCoverageGapsTool(
            obligations=obligations, raw_documents=raw_documents, policies=policies
        )
    )
    registry.register(
        ReviewPolicyQualityTool(
            policies=policies, obligations=obligations, raw_documents=raw_documents
        )
    )


async def get_web_database(app: FastAPI, database_url: str) -> Database:
    existing: Database | None = getattr(app.state, "web_database", None)
    if existing is not None:
        return existing
    if not hasattr(app.state, "web_database_lock"):
        app.state.web_database_lock = asyncio.Lock()
    async with app.state.web_database_lock:
        existing = getattr(app.state, "web_database", None)
        if existing is None:
            if not database_url:
                raise WebRuntimeNotConfiguredError(
                    "DATABASE_URL is not configured; Policy Intelligence needs a "
                    "web_postgres connection to apps/web's schema"
                )
            existing = await Database.connect(database_url)
            app.state.web_database = existing
    return existing


async def get_tool_registry(app: FastAPI, database_url: str) -> ToolRegistry:
    existing: ToolRegistry | None = getattr(app.state, "tool_registry", None)
    if existing is not None:
        return existing
    database = await get_web_database(app, database_url)
    registry = ToolRegistry(recorder=PostgresToolInvocationRecorder(database))
    _register_policy_intelligence_tools(registry, database)
    app.state.tool_registry = registry
    return registry


async def get_policy_repository(app: FastAPI, database_url: str) -> PolicyRepository:
    database = await get_web_database(app, database_url)
    return PolicyRepository(database)


async def get_policy_mission_store(app: FastAPI, database_url: str) -> PolicyMissionStore:
    database = await get_web_database(app, database_url)
    return PolicyMissionStore(database)


async def get_worker_control_repository(app: FastAPI, database_url: str) -> WorkerControlRepository:
    database = await get_web_database(app, database_url)
    return WorkerControlRepository(database)


async def get_worker_run_history_repository(
    app: FastAPI, database_url: str
) -> WorkerRunHistoryRepository:
    database = await get_web_database(app, database_url)
    return WorkerRunHistoryRepository(database)


async def get_worker_event_repository(app: FastAPI, database_url: str) -> WorkerEventRepository:
    database = await get_web_database(app, database_url)
    return WorkerEventRepository(database)


async def get_web_knowledge_item_repository(
    app: FastAPI, database_url: str
) -> KnowledgeItemRepository:
    database = await get_web_database(app, database_url)
    return KnowledgeItemRepository(database)


async def close_web_database(app: FastAPI) -> None:
    """Called from the lifespan shutdown. A no-op if the pool was never lazily created."""
    database: Database | None = getattr(app.state, "web_database", None)
    if database is not None:
        await database.close()
        app.state.web_database = None
