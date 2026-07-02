"""Base Entity and AggregateRoot (shared kernel)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from .events import DomainEvent
from .identifiers import EntityId


def utcnow() -> datetime:
    """Domain clock helper. Always timezone-aware UTC."""
    return datetime.now(timezone.utc)


@dataclass(kw_only=True, eq=False)
class Entity:
    """Base class for entities. Equality and hashing are by identity (`id`), not state."""

    id: EntityId
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Entity):
            return NotImplemented
        return type(self) is type(other) and self.id == other.id

    def __hash__(self) -> int:
        return hash((type(self).__name__, self.id))

    def _touch(self) -> None:
        """Mark the entity as modified now."""
        self.updated_at = utcnow()


@dataclass(kw_only=True, eq=False)
class AggregateRoot(Entity):
    """Base class for aggregate roots.

    Aggregates are the consistency boundary: state changes go through the root, which
    records domain events. Infrastructure later pulls and publishes those events; the
    domain itself never publishes anything.
    """

    _events: list[DomainEvent] = field(
        default_factory=list, init=False, repr=False, compare=False
    )

    def _record_event(self, event: DomainEvent) -> None:
        self._events.append(event)
        self._touch()

    def pull_events(self) -> list[DomainEvent]:
        """Return and clear the recorded events (called by the application layer)."""
        events = list(self._events)
        self._events.clear()
        return events

    @property
    def pending_events(self) -> tuple[DomainEvent, ...]:
        return tuple(self._events)
