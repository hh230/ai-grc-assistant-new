"""Repository interface for the Missions bounded context."""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..shared.identifiers import MissionId, OrganizationId, WorkspaceId
from .entities import Mission


class MissionRepository(ABC):
    @abstractmethod
    async def get(
        self,
        organization_id: OrganizationId,
        mission_id: MissionId,
    ) -> Mission | None: ...

    @abstractmethod
    async def list_for_workspace(
        self, organization_id: OrganizationId, workspace_id: WorkspaceId
    ) -> list[Mission]: ...

    @abstractmethod
    async def add(self, mission: Mission) -> None: ...

    @abstractmethod
    async def save(self, mission: Mission) -> None: ...
