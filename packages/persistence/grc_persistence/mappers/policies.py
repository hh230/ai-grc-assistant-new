"""Mapper for the Policies context."""

from __future__ import annotations

from grc_domain.policies.entities import Policy
from grc_domain.policies.enums import PolicyStatus
from grc_domain.policies.value_objects import PolicyBody, PolicyVersion
from grc_domain.shared.identifiers import ControlId, OrganizationId, PolicyId, UserId

from ..contracts.mapper import AggregateMapper
from ..models.policies import PolicyModel
from ._common import (
    aware,
    decode_citations,
    decode_framework_control_refs,
    encode_citations,
    encode_framework_control_refs,
    encode_id_set,
)


class PolicyMapper(AggregateMapper[Policy, PolicyModel]):
    def to_orm(self, aggregate: Policy) -> PolicyModel:
        return PolicyModel(
            id=str(aggregate.id),
            organization_id=str(aggregate.organization_id),
            title=aggregate.title,
            body=aggregate.body.text,
            owner_id=str(aggregate.owner_id),
            status=aggregate.status.value,
            policy_version=aggregate.version.number,
            approved_by=str(aggregate.approved_by) if aggregate.approved_by is not None else None,
            linked_control_ids=encode_id_set(aggregate.linked_control_ids),
            framework_controls=encode_framework_control_refs(aggregate.framework_controls),
            citations=encode_citations(aggregate.citations),
            created_at=aggregate.created_at,
            updated_at=aggregate.updated_at,
        )

    def update_orm(self, model: PolicyModel, aggregate: Policy) -> None:
        model.title = aggregate.title
        model.body = aggregate.body.text
        model.status = aggregate.status.value
        model.policy_version = aggregate.version.number
        model.approved_by = (
            str(aggregate.approved_by) if aggregate.approved_by is not None else None
        )
        model.linked_control_ids = encode_id_set(aggregate.linked_control_ids)
        model.framework_controls = encode_framework_control_refs(aggregate.framework_controls)
        model.citations = encode_citations(aggregate.citations)
        model.updated_at = aggregate.updated_at

    def to_domain(self, model: PolicyModel) -> Policy:
        return Policy(
            id=PolicyId(model.id),
            organization_id=OrganizationId(model.organization_id),
            title=model.title,
            body=PolicyBody(model.body),
            owner_id=UserId(model.owner_id),
            status=PolicyStatus(model.status),
            version=PolicyVersion(model.policy_version),
            approved_by=UserId(model.approved_by) if model.approved_by is not None else None,
            linked_control_ids={ControlId(value) for value in model.linked_control_ids},
            framework_controls=decode_framework_control_refs(model.framework_controls),
            citations=decode_citations(model.citations),
            created_at=aware(model.created_at),
            updated_at=aware(model.updated_at),
        )


policy_mapper = PolicyMapper()
