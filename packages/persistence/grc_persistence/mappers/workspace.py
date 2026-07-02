"""Mapper for the Workspace context."""

from __future__ import annotations

from grc_domain.shared.identifiers import OrganizationId, UserId, WorkspaceId
from grc_domain.workspace.entities import Workspace
from grc_domain.workspace.enums import WorkspaceStatus

from ..contracts.mapper import AggregateMapper
from ..models.workspace import WorkspaceModel
from ._common import aware, encode_id_set


class WorkspaceMapper(AggregateMapper[Workspace, WorkspaceModel]):
    def to_orm(self, aggregate: Workspace) -> WorkspaceModel:
        return WorkspaceModel(
            id=str(aggregate.id),
            organization_id=str(aggregate.organization_id),
            name=aggregate.name,
            owner_id=str(aggregate.owner_id),
            description=aggregate.description,
            status=aggregate.status.value,
            member_ids=encode_id_set(aggregate.member_ids),
            created_at=aggregate.created_at,
            updated_at=aggregate.updated_at,
        )

    def update_orm(self, model: WorkspaceModel, aggregate: Workspace) -> None:
        model.name = aggregate.name
        model.description = aggregate.description
        model.status = aggregate.status.value
        model.member_ids = encode_id_set(aggregate.member_ids)
        model.updated_at = aggregate.updated_at

    def to_domain(self, model: WorkspaceModel) -> Workspace:
        return Workspace(
            id=WorkspaceId(model.id),
            organization_id=OrganizationId(model.organization_id),
            name=model.name,
            owner_id=UserId(model.owner_id),
            description=model.description,
            status=WorkspaceStatus(model.status),
            member_ids={UserId(value) for value in model.member_ids},
            created_at=aware(model.created_at),
            updated_at=aware(model.updated_at),
        )


workspace_mapper = WorkspaceMapper()
