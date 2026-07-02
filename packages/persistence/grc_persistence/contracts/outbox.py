"""Transactional outbox contract — the single source of integration events.

Domain events recorded by aggregates are translated into immutable :class:`IntegrationEvent`
envelopes and persisted, **in the same database transaction** as the state change, through
the :class:`Outbox`. A separate relay (future work, ``packages/events``) reads unpublished
rows and forwards them to the bus. Because integration events only ever originate from
outbox rows, publication is reliable (no lost events) and has exactly one source of truth
(CLAUDE.md §16).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class IntegrationEvent:
    """An immutable, serializable fact ready to be published to the event bus.

    It is derived from a domain event plus the aggregate that recorded it, so it carries
    the routing/audit context a consumer needs: the event type, the originating aggregate,
    the owning tenant (``None`` for globally-scoped aggregates), and a JSON-safe payload.
    """

    event_id: str
    event_type: str
    aggregate_type: str
    aggregate_id: str
    organization_id: str | None
    occurred_at: datetime
    payload: Mapping[str, object] = field(default_factory=dict)
    trace_id: str | None = None


class Outbox(ABC):
    """Persists integration events transactionally with the unit of work."""

    @abstractmethod
    async def enqueue(self, events: Sequence[IntegrationEvent]) -> None:
        """Stage integration events for insertion within the current transaction."""
        ...
