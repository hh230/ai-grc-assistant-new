"""Repository interface for the Controls bounded context."""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..shared.identifiers import ControlId, OrganizationId, WorkspaceId
from .entities import Control


class ControlRepository(ABC):
    @abstractmethod
    async def get(
        self,
        organization_id: OrganizationId,
        control_id: ControlId,
    ) -> Control | None: ...

    @abstractmethod
    async def list_for_workspace(
        self, organization_id: OrganizationId, workspace_id: WorkspaceId
    ) -> list[Control]: ...

    @abstractmethod
    async def add(self, control: Control) -> None: ...

    @abstractmethod
    async def save(self, control: Control) -> None: ...
