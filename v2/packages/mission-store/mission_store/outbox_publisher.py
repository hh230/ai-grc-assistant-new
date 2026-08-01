"""The `OutboxPublisher` port and its default adapter (ADR 0043-S4 §4). Pure — no driver, no I/O.

The relay rehydrates a typed `DomainEvent` from each unpublished row (via the codec) and hands it to
an `OutboxPublisher`, which delivers it. `DeliveryBusPublisher` is the default adapter: it forwards
the event to a **Delivery Bus** — an `EventBus` carrying the real downstream consumers (audit sinks,
tracers), which lives **outside** the write transaction.

The Delivery Bus is deliberately a *different* bus from the **Capture Bus** the engine emits onto
during a transition (whose only subscriber is the `OutboxSink`). Publishing onto the Delivery Bus
never re-enters the outbox — there is no loop. Per Invariant I11 the relay only ever hands this
publisher events that are already durably committed in the outbox table.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from event_bus.bus import EventBus
from event_bus.events import DomainEvent


@runtime_checkable
class OutboxPublisher(Protocol):
    """Delivers a rehydrated event drained from the outbox. Implementations must not write back to
    the outbox (no loop) and are invoked by the relay only for durably-committed events (I11)."""

    def publish(self, event: DomainEvent) -> None: ...


class DeliveryBusPublisher:
    """The default `OutboxPublisher`: forwards each drained event to a Delivery Bus (any `EventBus`
    implementation carrying the real consumers). A thin adapter — it adds no logic, it only bridges
    the relay to the delivery-side bus."""

    def __init__(self, delivery_bus: EventBus) -> None:
        self._delivery_bus = delivery_bus

    def publish(self, event: DomainEvent) -> None:
        self._delivery_bus.publish(event)
