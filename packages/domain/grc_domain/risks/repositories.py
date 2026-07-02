"""Repository interface for the Risks bounded context."""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..shared.identifiers import OrganizationId, RiskId
from .entities import Risk


class RiskRepository(ABC):
    @abstractmethod
    async def get(self, organization_id: OrganizationId, risk_id: RiskId) -> Risk | None: ...

    @abstractmethod
    async def list_for_organization(self, organization_id: OrganizationId) -> list[Risk]: ...

    @abstractmethod
    async def add(self, risk: Risk) -> None: ...

    @abstractmethod
    async def save(self, risk: Risk) -> None: ...
