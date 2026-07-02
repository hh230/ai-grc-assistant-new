"""Repository for the Workspace context."""

from __future__ import annotations

from grc_domain.shared.identifiers import OrganizationId, WorkspaceId
from grc_domain.workspace.entities import Workspace
from grc_domain.workspace.repositories import WorkspaceRepository
from sqlalchemy.ext.asyncio import AsyncSession

from ..contracts.cache import RepositoryCache
from ..contracts.tracking import AggregateTracker
from ..mappers.workspace import workspace_mapper
from ..models.workspace import WorkspaceModel
from .base import SqlAlchemyAggregateRepository


class SqlAlchemyWorkspaceRepository(
    SqlAlchemyAggregateRepository[Workspace, WorkspaceModel], WorkspaceRepository
):
    def __init__(
        self, session: AsyncSession, tracker: AggregateTracker, cache: RepositoryCache
    ) -> None:
        super().__init__(session, workspace_mapper, tracker, cache, WorkspaceModel)

    async def get(
        self, organization_id: OrganizationId, workspace_id: WorkspaceId
    ) -> Workspace | None:
        return await self._get_by(
            self._key(str(workspace_id), str(organization_id)),
            WorkspaceModel.id == str(workspace_id),
            WorkspaceModel.organization_id == str(organization_id),
        )

    async def list_for_organization(self, organization_id: OrganizationId) -> list[Workspace]:
        return await self._list_by(
            WorkspaceModel.organization_id == str(organization_id),
            order_by=WorkspaceModel.created_at,
        )

    async def add(self, workspace: Workspace) -> None:
        await self._insert(workspace, self._key(str(workspace.id), str(workspace.organization_id)))

    async def save(self, workspace: Workspace) -> None:
        await self._update(
            workspace,
            self._key(str(workspace.id), str(workspace.organization_id)),
            pk=str(workspace.id),
            tenant=str(workspace.organization_id),
        )
