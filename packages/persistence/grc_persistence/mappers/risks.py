"""Mapper for the Risks context."""

from __future__ import annotations

from grc_domain.risks.entities import Risk
from grc_domain.risks.enums import RiskStatus, RiskTreatment
from grc_domain.shared.identifiers import ControlId, EvidenceId, OrganizationId, RiskId, UserId

from ..contracts.mapper import AggregateMapper
from ..models.risks import RiskModel
from ._common import aware, decode_risk_score, encode_id_set, encode_risk_score


class RiskMapper(AggregateMapper[Risk, RiskModel]):
    def to_orm(self, aggregate: Risk) -> RiskModel:
        return RiskModel(
            id=str(aggregate.id),
            organization_id=str(aggregate.organization_id),
            title=aggregate.title,
            description=aggregate.description,
            category=aggregate.category,
            owner_id=str(aggregate.owner_id) if aggregate.owner_id is not None else None,
            status=aggregate.status.value,
            score=encode_risk_score(aggregate.score),
            treatment=aggregate.treatment.value if aggregate.treatment is not None else None,
            accepted_by=str(aggregate.accepted_by) if aggregate.accepted_by is not None else None,
            acceptance_rationale=aggregate.acceptance_rationale,
            mitigating_control_ids=encode_id_set(aggregate.mitigating_control_ids),
            evidence_ids=encode_id_set(aggregate.evidence_ids),
            created_at=aggregate.created_at,
            updated_at=aggregate.updated_at,
        )

    def update_orm(self, model: RiskModel, aggregate: Risk) -> None:
        model.title = aggregate.title
        model.description = aggregate.description
        model.category = aggregate.category
        model.owner_id = str(aggregate.owner_id) if aggregate.owner_id is not None else None
        model.status = aggregate.status.value
        model.score = encode_risk_score(aggregate.score)
        model.treatment = aggregate.treatment.value if aggregate.treatment is not None else None
        model.accepted_by = (
            str(aggregate.accepted_by) if aggregate.accepted_by is not None else None
        )
        model.acceptance_rationale = aggregate.acceptance_rationale
        model.mitigating_control_ids = encode_id_set(aggregate.mitigating_control_ids)
        model.evidence_ids = encode_id_set(aggregate.evidence_ids)
        model.updated_at = aggregate.updated_at

    def to_domain(self, model: RiskModel) -> Risk:
        return Risk(
            id=RiskId(model.id),
            organization_id=OrganizationId(model.organization_id),
            title=model.title,
            description=model.description,
            category=model.category,
            owner_id=UserId(model.owner_id) if model.owner_id is not None else None,
            status=RiskStatus(model.status),
            score=decode_risk_score(model.score),
            treatment=RiskTreatment(model.treatment) if model.treatment is not None else None,
            accepted_by=UserId(model.accepted_by) if model.accepted_by is not None else None,
            acceptance_rationale=model.acceptance_rationale,
            mitigating_control_ids={ControlId(v) for v in model.mitigating_control_ids},
            evidence_ids={EvidenceId(v) for v in model.evidence_ids},
            created_at=aware(model.created_at),
            updated_at=aware(model.updated_at),
        )


risk_mapper = RiskMapper()
