"""Repository for the Missions context — the aggregate with diff-synced child tables.

On ``save`` the repository loads the managed mission row (its step and gate collections are
eager-loaded), updates the root scalars via the mapper, then reconciles each child
collection with :func:`sync_children` keyed on the children's stable ids. Optimistic
concurrency on the root row covers the whole aggregate, because every domain mutation
touches the root (it records an event), marking the row dirty so its ``version`` bumps.
"""

from __future__ import annotations

from grc_domain.missions.entities import Mission
from grc_domain.missions.repositories import MissionRepository
from grc_domain.shared.identifiers import MissionId, OrganizationId, WorkspaceId
from sqlalchemy.ext.asyncio import AsyncSession

from ..contracts.cache import RepositoryCache
from ..contracts.tracking import AggregateTracker
from ..mappers.missions import (
    mission_gate_child_mapper,
    mission_mapper,
    mission_step_child_mapper,
)
from ..models.missions import MissionModel
from ._sync import sync_children
from .base import SqlAlchemyAggregateRepository


class SqlAlchemyMissionRepository(
    SqlAlchemyAggregateRepository[Mission, MissionModel], MissionRepository
):
    def __init__(
        self, session: AsyncSession, tracker: AggregateTracker, cache: RepositoryCache
    ) -> None:
        super().__init__(session, mission_mapper, tracker, cache, MissionModel)

    async def get(self, organization_id: OrganizationId, mission_id: MissionId) -> Mission | None:
        return await self._get_by(
            self._key(str(mission_id), str(organization_id)),
            MissionModel.id == str(mission_id),
            MissionModel.organization_id == str(organization_id),
        )

    async def list_for_workspace(
        self, organization_id: OrganizationId, workspace_id: WorkspaceId
    ) -> list[Mission]:
        return await self._list_by(
            MissionModel.organization_id == str(organization_id),
            MissionModel.workspace_id == str(workspace_id),
            order_by=MissionModel.created_at,
        )

    async def add(self, mission: Mission) -> None:
        await self._insert(mission, self._key(str(mission.id), str(mission.organization_id)))

    async def save(self, mission: Mission) -> None:
        mission_id = str(mission.id)

        def _sync(model: MissionModel) -> None:
            sync_children(model.steps, mission.steps, mission_step_child_mapper, mission_id)
            sync_children(
                model.gates, mission.approval_gates, mission_gate_child_mapper, mission_id
            )

        await self._update(
            mission,
            self._key(mission_id, str(mission.organization_id)),
            pk=mission_id,
            tenant=str(mission.organization_id),
            sync=_sync,
        )
