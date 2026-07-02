"""The AuditRecord entity: an append-only, tenant-scoped, tamper-evident fact.

Audit records are created once and never mutated — there are deliberately no setters.
They make every AI decision and human approval reconstructable for external review
(CLAUDE.md §19).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from ..shared.entity import Entity, utcnow
from ..shared.identifiers import (
    AuditRecordId,
    KnowledgeSourceId,
    OrganizationId,
)
from ..shared.value_objects import Actor, TraceContext
from .enums import AuditCategory
from .value_objects import AiCallTrace


@dataclass(eq=False)
class AuditRecord(Entity):
    organization_id: OrganizationId
    actor: Actor
    category: AuditCategory
    action: str
    object_type: str
    object_id: str
    occurred_at: datetime = field(default_factory=utcnow)
    trace: TraceContext | None = None
    ai_call: AiCallTrace | None = None
    payload_hash: str | None = None
    source_ids: tuple[KnowledgeSourceId, ...] = field(default_factory=tuple)
    outcome: str | None = None

    @classmethod
    def record(
        cls,
        *,
        id: AuditRecordId,
        organization_id: OrganizationId,
        actor: Actor,
        category: AuditCategory,
        action: str,
        object_type: str,
        object_id: str,
        trace: TraceContext | None = None,
        ai_call: AiCallTrace | None = None,
        payload_hash: str | None = None,
        source_ids: tuple[KnowledgeSourceId, ...] = (),
        outcome: str | None = None,
    ) -> AuditRecord:
        if not action.strip():
            raise ValueError("Audit action must not be empty")
        return cls(
            id=id,
            organization_id=organization_id,
            actor=actor,
            category=category,
            action=action,
            object_type=object_type,
            object_id=object_id,
            trace=trace,
            ai_call=ai_call,
            payload_hash=payload_hash,
            source_ids=source_ids,
            outcome=outcome,
        )
