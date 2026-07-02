"""Repository interface for the Reporting bounded context."""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..shared.identifiers import OrganizationId, ReportId
from .entities import Report


class ReportRepository(ABC):
    @abstractmethod
    async def get(self, organization_id: OrganizationId, report_id: ReportId) -> Report | None: ...

    @abstractmethod
    async def list_for_organization(self, organization_id: OrganizationId) -> list[Report]: ...

    @abstractmethod
    async def add(self, report: Report) -> None: ...

    @abstractmethod
    async def save(self, report: Report) -> None: ...
