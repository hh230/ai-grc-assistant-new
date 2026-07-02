"""Repository for the Controls context."""

from __future__ import annotations

from grc_domain.controls.entities import Control
from grc_domain.controls.repositories import ControlRepository
from grc_domain.shared.identifiers import ControlId, OrganizationId, WorkspaceId
from sqlalchemy.ext.asyncio import AsyncSession

from ..contracts.cache import RepositoryCache
from ..contracts.tracking import AggregateTracker
from ..mappers.controls import control_mapper
from ..models.controls import ControlModel
from .base import SqlAlchemyAggregateRepository


class SqlAlchemyControlRepository(
    SqlAlchemyAggregateRepository[Control, ControlModel], ControlRepository
):
    def __init__(
        self, session: AsyncSession, tracker: AggregateTracker, cache: RepositoryCache
    ) -> None:
        super().__init__(session, control_mapper, tracker, cache, ControlModel)

    async def get(self, organization_id: OrganizationId, control_id: ControlId) -> Control | None:
        return await self._get_by(
            self._key(str(control_id), str(organization_id)),
            ControlModel.id == str(control_id),
            ControlModel.organization_id == str(organization_id),
        )

    async def list_for_workspace(
        self, organization_id: OrganizationId, workspace_id: WorkspaceId
    ) -> list[Control]:
        return await self._list_by(
            ControlModel.organization_id == str(organization_id),
            ControlModel.workspace_id == str(workspace_id),
            order_by=ControlModel.created_at,
        )

    async def add(self, control: Control) -> None:
        await self._insert(control, self._key(str(control.id), str(control.organization_id)))

    async def save(self, control: Control) -> None:
        await self._update(
            control,
            self._key(str(control.id), str(control.organization_id)),
            pk=str(control.id),
            tenant=str(control.organization_id),
        )
