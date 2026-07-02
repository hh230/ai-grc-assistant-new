"""Mapper for the Audit context.

An :class:`AuditRecord` is an append-only entity (not a mutable aggregate root), so this
mapper deliberately offers only ``to_orm`` / ``to_domain`` — there is no update path, which
mirrors the domain's no-setter design (CLAUDE.md §19).
"""

from __future__ import annotations

from grc_domain.audit.entities import AuditRecord
from grc_domain.audit.enums import AuditCategory
from grc_domain.shared.identifiers import (
    AuditRecordId,
    KnowledgeSourceId,
    OrganizationId,
)

from ..models.audit import AuditRecordModel
from ._common import (
    aware,
    decode_actor,
    decode_ai_call,
    decode_trace,
    encode_actor,
    encode_ai_call,
    encode_trace,
)


class AuditRecordMapper:
    def to_orm(self, record: AuditRecord) -> AuditRecordModel:
        return AuditRecordModel(
            id=str(record.id),
            organization_id=str(record.organization_id),
            actor=encode_actor(record.actor),
            category=record.category.value,
            action=record.action,
            object_type=record.object_type,
            object_id=record.object_id,
            occurred_at=record.occurred_at,
            trace=encode_trace(record.trace),
            ai_call=encode_ai_call(record.ai_call),
            payload_hash=record.payload_hash,
            source_ids=[str(source_id) for source_id in record.source_ids],
            outcome=record.outcome,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    def to_domain(self, model: AuditRecordModel) -> AuditRecord:
        return AuditRecord(
            id=AuditRecordId(model.id),
            organization_id=OrganizationId(model.organization_id),
            actor=decode_actor(model.actor),
            category=AuditCategory(model.category),
            action=model.action,
            object_type=model.object_type,
            object_id=model.object_id,
            occurred_at=aware(model.occurred_at),
            trace=decode_trace(model.trace),
            ai_call=decode_ai_call(model.ai_call),
            payload_hash=model.payload_hash,
            source_ids=tuple(KnowledgeSourceId(value) for value in model.source_ids),
            outcome=model.outcome,
            created_at=aware(model.created_at),
            updated_at=aware(model.updated_at),
        )


audit_record_mapper = AuditRecordMapper()
