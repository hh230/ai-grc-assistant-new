"""Unit of Work interface — the application's Transaction Boundary.

A UnitOfWork groups repository operations into a single atomic transaction and exposes the
domain repository interfaces. It also surfaces the domain events recorded by the aggregates
touched during the transaction, so the handler can dispatch them after commit.

This is an interface only. The concrete implementation (SQLAlchemy session, etc.) lives in
the infrastructure layer and is injected into handlers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from grc_domain.assessments.repositories import AssessmentRepository
from grc_domain.audit.repositories import AuditRecordRepository
from grc_domain.controls.repositories import ControlRepository
from grc_domain.evidence.repositories import EvidenceRepository
from grc_domain.frameworks.repositories import (
    FrameworkMappingRepository,
    FrameworkRepository,
)
from grc_domain.knowledge.repositories import KnowledgeSourceRepository
from grc_domain.missions.repositories import MissionRepository
from grc_domain.platform.repositories import (
    AgentDescriptorRepository,
    PluginDescriptorRepository,
    ToolDescriptorRepository,
)
from grc_domain.policies.repositories import PolicyRepository
from grc_domain.reporting.repositories import ReportRepository
from grc_domain.risks.repositories import RiskRepository
from grc_domain.shared.events import DomainEvent
from grc_domain.tenancy.repositories import OrganizationRepository, UserRepository
from grc_domain.workspace.repositories import WorkspaceRepository


class UnitOfWork(ABC):
    """Atomic transaction boundary exposing the domain repositories."""

    # --- repositories (domain interfaces; implemented by infrastructure) ---
    @property
    @abstractmethod
    def organizations(self) -> OrganizationRepository: ...

    @property
    @abstractmethod
    def users(self) -> UserRepository: ...

    @property
    @abstractmethod
    def workspaces(self) -> WorkspaceRepository: ...

    @property
    @abstractmethod
    def missions(self) -> MissionRepository: ...

    @property
    @abstractmethod
    def frameworks(self) -> FrameworkRepository: ...

    @property
    @abstractmethod
    def framework_mappings(self) -> FrameworkMappingRepository: ...

    @property
    @abstractmethod
    def controls(self) -> ControlRepository: ...

    @property
    @abstractmethod
    def policies(self) -> PolicyRepository: ...

    @property
    @abstractmethod
    def risks(self) -> RiskRepository: ...

    @property
    @abstractmethod
    def assessments(self) -> AssessmentRepository: ...

    @property
    @abstractmethod
    def evidence(self) -> EvidenceRepository: ...

    @property
    @abstractmethod
    def knowledge_sources(self) -> KnowledgeSourceRepository: ...

    @property
    @abstractmethod
    def reports(self) -> ReportRepository: ...

    @property
    @abstractmethod
    def tools(self) -> ToolDescriptorRepository: ...

    @property
    @abstractmethod
    def agents(self) -> AgentDescriptorRepository: ...

    @property
    @abstractmethod
    def plugins(self) -> PluginDescriptorRepository: ...

    @property
    @abstractmethod
    def audit(self) -> AuditRecordRepository: ...

    # --- transaction control ---
    async def __aenter__(self) -> UnitOfWork:
        await self.begin()
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        if exc_type is not None:
            await self.rollback()
        # On success the handler calls commit() explicitly before exit.

    @abstractmethod
    async def begin(self) -> None: ...

    @abstractmethod
    async def commit(self) -> None: ...

    @abstractmethod
    async def rollback(self) -> None: ...

    @abstractmethod
    def collect_new_events(self) -> list[DomainEvent]:
        """Return domain events recorded by aggregates touched in this unit of work."""
        ...
