"""Repository interface for the Assessments bounded context."""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..shared.identifiers import AssessmentId, OrganizationId
from .entities import Assessment


class AssessmentRepository(ABC):
    @abstractmethod
    async def get(
        self,
        organization_id: OrganizationId,
        assessment_id: AssessmentId,
    ) -> Assessment | None: ...

    @abstractmethod
    async def list_for_organization(self, organization_id: OrganizationId) -> list[Assessment]: ...

    @abstractmethod
    async def add(self, assessment: Assessment) -> None: ...

    @abstractmethod
    async def save(self, assessment: Assessment) -> None: ...
