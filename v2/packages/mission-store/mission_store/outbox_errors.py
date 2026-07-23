"""Errors raised by the Transactional Outbox (ADR 0043-S4, Slice 4). Kept in their own module so
the frozen Slice 1/2 `errors.py` is untouched; they extend that taxonomy by *importing* its base:

    MissionStoreError                       (frozen, errors.py)
     └── OutboxError                        — an outbox operation could not complete safely
          └── UnsupportedEventType          — a stored event name has no registered type to rebuild

`UnsupportedEventType` is raised on the relay's rehydrate path only, for an `event_name` that is
not in the rehydration registry. Per ADR 0043-S4 Rev.3 §6 the relay **raises and leaves the row
unpublished** — it never deletes the row and never marks it published — so once the missing type is
registered a later drain republishes it (I8). It is a fail-loud stance: there is no generic
fallback event.
"""

from __future__ import annotations

from mission_store.errors import MissionStoreError


class OutboxError(MissionStoreError):
    """A durable-outbox operation could not be completed safely (ADR 0043-S4 §6)."""


class UnsupportedEventType(OutboxError):
    """A stored outbox row carries an `event_name` that no registered event type can rebuild. Raised
    on the relay's rehydrate path (`event_from_record`) before any event is reconstructed. The relay
    must leave the row unpublished (neither delete it nor mark it published), so it is republished
    once the type is registered — never silently degraded to a generic event (Invariant I8)."""

    def __init__(self, *, event_name: str, outbox_id: int | None = None) -> None:
        self.event_name = event_name
        self.outbox_id = outbox_id
        where = f" (outbox row {outbox_id})" if outbox_id is not None else ""
        super().__init__(
            f"no registered event type for event_name {event_name!r}{where}; "
            "the row is left unpublished until the type is registered"
        )
