"""Mapper for the Controls context."""

from __future__ import annotations

from grc_domain.controls.entities import Control
from grc_domain.controls.enums import ControlImplementationStatus
from grc_domain.shared.identifiers import (
    ControlId,
    EvidenceId,
    OrganizationId,
    UserId,
    WorkspaceId,
)

from ..contracts.mapper import AggregateMapper
from ..models.controls import ControlModel
from ._common import (
    aware,
    decode_framework_control_refs,
    encode_framework_control_refs,
    encode_id_set,
)


class ControlMapper(AggregateMapper[Control, ControlModel]):
    def to_orm(self, aggregate: Control) -> ControlModel:
        return ControlModel(
            id=str(aggregate.id),
            organization_id=str(aggregate.organization_id),
            workspace_id=str(aggregate.workspace_id),
            title=aggregate.title,
            description=aggregate.description,
            owner_id=str(aggregate.owner_id) if aggregate.owner_id is not None else None,
            implementation_status=aggregate.implementation_status.value,
            framework_controls=encode_framework_control_refs(aggregate.framework_controls),
            evidence_ids=encode_id_set(aggregate.evidence_ids),
            created_at=aggregate.created_at,
            updated_at=aggregate.updated_at,
        )

    def update_orm(self, model: ControlModel, aggregate: Control) -> None:
        model.title = aggregate.title
        model.description = aggregate.description
        model.owner_id = str(aggregate.owner_id) if aggregate.owner_id is not None else None
        model.implementation_status = aggregate.implementation_status.value
        model.framework_controls = encode_framework_control_refs(aggregate.framework_controls)
        model.evidence_ids = encode_id_set(aggregate.evidence_ids)
        model.updated_at = aggregate.updated_at

    def to_domain(self, model: ControlModel) -> Control:
        return Control(
            id=ControlId(model.id),
            organization_id=OrganizationId(model.organization_id),
            workspace_id=WorkspaceId(model.workspace_id),
            title=model.title,
            description=model.description,
            owner_id=UserId(model.owner_id) if model.owner_id is not None else None,
            implementation_status=ControlImplementationStatus(model.implementation_status),
            framework_controls=decode_framework_control_refs(model.framework_controls),
            evidence_ids={EvidenceId(value) for value in model.evidence_ids},
            created_at=aware(model.created_at),
            updated_at=aware(model.updated_at),
        )


control_mapper = ControlMapper()
