"""SqlAlchemyUnitOfWork — the concrete transaction boundary.

It realizes the application's ``UnitOfWork`` port (CLAUDE.md §14): one SQLAlchemy session per
activation, every domain repository exposed lazily, and — on commit — the domain events
recorded by tracked aggregates are translated into integration events and written to the
transactional outbox **in the same transaction** as the state change.

Responsibilities kept here (not in repositories): session lifecycle, aggregate tracking for
event collection, the outbox write, and translating storage-level concurrency/integrity
errors into the application's exceptions.
"""

from __future__ import annotations

from contextlib import suppress

from grc_domain.shared.entity import AggregateRoot
from grc_domain.shared.events import DomainEvent
from grc_services.shared.exceptions import (
    ConcurrencyError,
    ConflictError,
    UnitOfWorkError,
)
from grc_services.shared.unit_of_work import UnitOfWork
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm.exc import StaleDataError

from .contracts.cache import NullRepositoryCache, RepositoryCache
from .contracts.tracking import AggregateTracker
from .mappers.events import to_integration_event
from .outbox import SqlAlchemyOutbox
from .repositories import (
    SqlAlchemyAgentDescriptorRepository,
    SqlAlchemyAssessmentRepository,
    SqlAlchemyAuditRecordRepository,
    SqlAlchemyControlRepository,
    SqlAlchemyEvidenceRepository,
    SqlAlchemyFrameworkMappingRepository,
    SqlAlchemyFrameworkRepository,
    SqlAlchemyKnowledgeSourceRepository,
    SqlAlchemyMissionRepository,
    SqlAlchemyOrganizationRepository,
    SqlAlchemyPluginDescriptorRepository,
    SqlAlchemyPolicyRepository,
    SqlAlchemyReportRepository,
    SqlAlchemyRiskRepository,
    SqlAlchemyToolDescriptorRepository,
    SqlAlchemyUserRepository,
    SqlAlchemyWorkspaceRepository,
)


class SqlAlchemyUnitOfWork(UnitOfWork, AggregateTracker):
    """A SQLAlchemy-backed unit of work with a transactional outbox and aggregate tracking."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        cache: RepositoryCache | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._cache: RepositoryCache = cache or NullRepositoryCache()
        self._session: AsyncSession | None = None
        self._outbox: SqlAlchemyOutbox | None = None
        self._repos: dict[str, object] = {}
        self._seen: list[AggregateRoot] = []
        self._seen_markers: set[int] = set()
        self._collected = False
        self._collected_pairs: list[tuple[AggregateRoot, DomainEvent]] = []

    # --- aggregate tracking ---------------------------------------------------------
    def track(self, aggregate: AggregateRoot) -> None:
        marker = id(aggregate)
        if marker not in self._seen_markers:
            self._seen_markers.add(marker)
            self._seen.append(aggregate)

    # --- session access -------------------------------------------------------------
    @property
    def session(self) -> AsyncSession:
        if self._session is None:
            raise UnitOfWorkError("Unit of work is not active")
        return self._session

    def _repo(self, name: str, factory: type) -> object:
        repo = self._repos.get(name)
        if repo is None:
            repo = factory(self.session, self, self._cache)
            self._repos[name] = repo
        return repo

    # --- repositories (domain interfaces) -------------------------------------------
    @property
    def organizations(self) -> SqlAlchemyOrganizationRepository:
        return self._repo("organizations", SqlAlchemyOrganizationRepository)  # type: ignore[return-value]

    @property
    def users(self) -> SqlAlchemyUserRepository:
        return self._repo("users", SqlAlchemyUserRepository)  # type: ignore[return-value]

    @property
    def workspaces(self) -> SqlAlchemyWorkspaceRepository:
        return self._repo("workspaces", SqlAlchemyWorkspaceRepository)  # type: ignore[return-value]

    @property
    def frameworks(self) -> SqlAlchemyFrameworkRepository:
        return self._repo("frameworks", SqlAlchemyFrameworkRepository)  # type: ignore[return-value]

    @property
    def framework_mappings(self) -> SqlAlchemyFrameworkMappingRepository:
        return self._repo("framework_mappings", SqlAlchemyFrameworkMappingRepository)  # type: ignore[return-value]

    @property
    def controls(self) -> SqlAlchemyControlRepository:
        return self._repo("controls", SqlAlchemyControlRepository)  # type: ignore[return-value]

    @property
    def policies(self) -> SqlAlchemyPolicyRepository:
        return self._repo("policies", SqlAlchemyPolicyRepository)  # type: ignore[return-value]

    @property
    def risks(self) -> SqlAlchemyRiskRepository:
        return self._repo("risks", SqlAlchemyRiskRepository)  # type: ignore[return-value]

    @property
    def assessments(self) -> SqlAlchemyAssessmentRepository:
        return self._repo("assessments", SqlAlchemyAssessmentRepository)  # type: ignore[return-value]

    @property
    def evidence(self) -> SqlAlchemyEvidenceRepository:
        return self._repo("evidence", SqlAlchemyEvidenceRepository)  # type: ignore[return-value]

    @property
    def knowledge_sources(self) -> SqlAlchemyKnowledgeSourceRepository:
        return self._repo("knowledge_sources", SqlAlchemyKnowledgeSourceRepository)  # type: ignore[return-value]

    @property
    def reports(self) -> SqlAlchemyReportRepository:
        return self._repo("reports", SqlAlchemyReportRepository)  # type: ignore[return-value]

    @property
    def tools(self) -> SqlAlchemyToolDescriptorRepository:
        return self._repo("tools", SqlAlchemyToolDescriptorRepository)  # type: ignore[return-value]

    @property
    def agents(self) -> SqlAlchemyAgentDescriptorRepository:
        return self._repo("agents", SqlAlchemyAgentDescriptorRepository)  # type: ignore[return-value]

    @property
    def plugins(self) -> SqlAlchemyPluginDescriptorRepository:
        return self._repo("plugins", SqlAlchemyPluginDescriptorRepository)  # type: ignore[return-value]

    @property
    def audit(self) -> SqlAlchemyAuditRecordRepository:
        return self._repo("audit", SqlAlchemyAuditRecordRepository)  # type: ignore[return-value]

    @property
    def missions(self) -> SqlAlchemyMissionRepository:
        # Not declared on the abstract port, but the mission use cases depend on it; the
        # concrete unit of work is free to expose more than the minimum the port requires.
        return self._repo("missions", SqlAlchemyMissionRepository)  # type: ignore[return-value]

    # --- transaction control --------------------------------------------------------
    async def begin(self) -> None:
        if self._session is not None:
            raise UnitOfWorkError("Unit of work is already active")
        self._session = self._session_factory()
        self._outbox = SqlAlchemyOutbox(self._session)
        self._repos.clear()
        self._seen.clear()
        self._seen_markers.clear()
        self._collected = False
        self._collected_pairs = []

    def collect_new_events(self) -> list[DomainEvent]:
        events: list[DomainEvent] = []
        self._collected_pairs = []
        for aggregate in self._seen:
            for event in aggregate.pull_events():
                events.append(event)
                self._collected_pairs.append((aggregate, event))
        self._collected = True
        return events

    async def commit(self) -> None:
        if self._session is None or self._outbox is None:
            raise UnitOfWorkError("Unit of work is not active")
        session = self._session
        try:
            if not self._collected:
                self.collect_new_events()
            integration_events = [
                to_integration_event(aggregate, event) for aggregate, event in self._collected_pairs
            ]
            await self._outbox.enqueue(integration_events)
            await session.commit()
        except StaleDataError as exc:
            await self._rollback_quietly(session)
            raise ConcurrencyError(f"Optimistic concurrency conflict: {exc}") from exc
        except IntegrityError as exc:
            await self._rollback_quietly(session)
            raise ConflictError(f"Integrity conflict on commit: {exc}") from exc
        finally:
            await self._close()

    async def rollback(self) -> None:
        if self._session is None:
            return
        await self._rollback_quietly(self._session)
        await self._close()

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        # The command path closes the session in commit(); the read-only query path exits
        # here without committing — discard its transaction and release the session so it
        # never leaks.
        if self._session is None:
            return
        await self._rollback_quietly(self._session)
        await self._close()

    # --- internals ------------------------------------------------------------------
    @staticmethod
    async def _rollback_quietly(session: AsyncSession) -> None:
        # A rollback failure must not mask the original error that triggered it.
        with suppress(Exception):
            await session.rollback()

    async def _close(self) -> None:
        if self._session is not None:
            await self._session.close()
        self._session = None
        self._outbox = None
        self._repos.clear()
