"""Repository interface for the Evidence bounded context."""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..shared.identifiers import ControlId, EvidenceId, OrganizationId
from .entities import Evidence


class EvidenceRepository(ABC):
    @abstractmethod
    async def get(
        self,
        organization_id: OrganizationId,
        evidence_id: EvidenceId,
    ) -> Evidence | None: ...

    @abstractmethod
    async def list_for_control(
        self, organization_id: OrganizationId, control_id: ControlId
    ) -> list[Evidence]: ...

    @abstractmethod
    async def add(self, evidence: Evidence) -> None: ...

    @abstractmethod
    async def save(self, evidence: Evidence) -> None: ...
