"""Mapping: domain event → :class:`IntegrationEvent` → outbox row.

Keeping this here (rather than in the outbox writer) honors the rule that *all* Domain →
storage translation lives in the mappers package. The outbox writer only orchestrates
persistence; the shape of a serialized event is decided here.
"""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from grc_domain.shared.entity import AggregateRoot
from grc_domain.shared.events import DomainEvent
from grc_domain.shared.identifiers import EntityId, OrganizationId

from ..contracts.outbox import IntegrationEvent
from ..models.outbox import OutboxMessageModel

# Base DomainEvent fields are promoted to the envelope, not duplicated in the payload.
_ENVELOPE_FIELDS = frozenset({"event_id", "occurred_at"})


def _to_primitive(value: Any) -> Any:
    """Recursively convert a domain value into a JSON-safe primitive."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, EntityId):
        return value.value
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_to_primitive(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _to_primitive(item) for key, item in value.items()}
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _to_primitive(getattr(value, field.name)) for field in fields(value)}
    return str(value)


def serialize_event_payload(event: DomainEvent) -> dict[str, Any]:
    """Serialize an event's own fields (excluding the envelope fields) to primitives."""
    return {
        field.name: _to_primitive(getattr(event, field.name))
        for field in fields(event)
        if field.name not in _ENVELOPE_FIELDS
    }


def to_integration_event(aggregate: AggregateRoot, event: DomainEvent) -> IntegrationEvent:
    """Build an integration-event envelope from the aggregate that recorded the event."""
    organization_id = getattr(aggregate, "organization_id", None)
    if organization_id is None and isinstance(aggregate.id, OrganizationId):
        # The Organization aggregate is its own tenant.
        organization_id = aggregate.id
    return IntegrationEvent(
        event_id=event.event_id,
        event_type=type(event).__name__,
        aggregate_type=type(aggregate).__name__,
        aggregate_id=str(aggregate.id),
        organization_id=str(organization_id) if organization_id is not None else None,
        occurred_at=event.occurred_at,
        payload=serialize_event_payload(event),
        trace_id=None,
    )


def integration_event_to_model(
    event: IntegrationEvent, *, created_at: datetime
) -> OutboxMessageModel:
    """Translate an integration event into an unpublished outbox row."""
    return OutboxMessageModel(
        id=event.event_id,
        event_type=event.event_type,
        aggregate_type=event.aggregate_type,
        aggregate_id=event.aggregate_id,
        organization_id=event.organization_id,
        payload=dict(event.payload),
        occurred_at=event.occurred_at,
        created_at=created_at,
        published_at=None,
        trace_id=event.trace_id,
    )


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)
