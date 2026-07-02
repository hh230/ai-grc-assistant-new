"""Mapper for the Evidence context."""

from __future__ import annotations

from grc_domain.evidence.entities import Evidence
from grc_domain.evidence.enums import EvidenceStatus, EvidenceType
from grc_domain.shared.identifiers import (
    ControlId,
    EvidenceId,
    KnowledgeSourceId,
    OrganizationId,
)
from grc_domain.shared.value_objects import DateRange

from ..contracts.mapper import AggregateMapper
from ..models.evidence import EvidenceModel
from ._common import aware, encode_id_set


class EvidenceMapper(AggregateMapper[Evidence, EvidenceModel]):
    def to_orm(self, aggregate: Evidence) -> EvidenceModel:
        return EvidenceModel(
            id=str(aggregate.id),
            organization_id=str(aggregate.organization_id),
            title=aggregate.title,
            evidence_type=aggregate.evidence_type.value,
            knowledge_source_id=(
                str(aggregate.knowledge_source_id)
                if aggregate.knowledge_source_id is not None
                else None
            ),
            collected_at=aggregate.collected_at,
            validity_start=aggregate.validity.start if aggregate.validity is not None else None,
            validity_end=aggregate.validity.end if aggregate.validity is not None else None,
            status=aggregate.status.value,
            linked_control_ids=encode_id_set(aggregate.linked_control_ids),
            rejection_reason=aggregate.rejection_reason,
            created_at=aggregate.created_at,
            updated_at=aggregate.updated_at,
        )

    def update_orm(self, model: EvidenceModel, aggregate: Evidence) -> None:
        model.title = aggregate.title
        model.evidence_type = aggregate.evidence_type.value
        model.knowledge_source_id = (
            str(aggregate.knowledge_source_id)
            if aggregate.knowledge_source_id is not None
            else None
        )
        model.collected_at = aggregate.collected_at
        model.validity_start = aggregate.validity.start if aggregate.validity is not None else None
        model.validity_end = aggregate.validity.end if aggregate.validity is not None else None
        model.status = aggregate.status.value
        model.linked_control_ids = encode_id_set(aggregate.linked_control_ids)
        model.rejection_reason = aggregate.rejection_reason
        model.updated_at = aggregate.updated_at

    def to_domain(self, model: EvidenceModel) -> Evidence:
        validity: DateRange | None = None
        if model.validity_start is not None:
            validity = DateRange(
                start=aware(model.validity_start),
                end=aware(model.validity_end) if model.validity_end is not None else None,
            )
        return Evidence(
            id=EvidenceId(model.id),
            organization_id=OrganizationId(model.organization_id),
            title=model.title,
            evidence_type=EvidenceType(model.evidence_type),
            knowledge_source_id=(
                KnowledgeSourceId(model.knowledge_source_id)
                if model.knowledge_source_id is not None
                else None
            ),
            collected_at=aware(model.collected_at) if model.collected_at is not None else None,
            validity=validity,
            status=EvidenceStatus(model.status),
            linked_control_ids={ControlId(value) for value in model.linked_control_ids},
            rejection_reason=model.rejection_reason,
            created_at=aware(model.created_at),
            updated_at=aware(model.updated_at),
        )


evidence_mapper = EvidenceMapper()
