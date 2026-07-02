"""Repository interface for the Workspace bounded context."""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..shared.identifiers import OrganizationId, WorkspaceId
from .entities import Workspace


class WorkspaceRepository(ABC):
    @abstractmethod
    async def get(
        self,
        organization_id: OrganizationId,
        workspace_id: WorkspaceId,
    ) -> Workspace | None: ...

    @abstractmethod
    async def list_for_organization(self, organization_id: OrganizationId) -> list[Workspace]: ...

    @abstractmethod
    async def add(self, workspace: Workspace) -> None: ...

    @abstractmethod
    async def save(self, workspace: Workspace) -> None: ...
