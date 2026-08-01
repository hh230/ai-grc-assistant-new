"""The Event Bus port and its one built-in implementation: a synchronous, in-process,
provider-agnostic dispatcher.

`EventBus` is the hexagonal port every publisher and subscriber depends on. `InProcessEventBus`
is the only implementation this phase ships — deliberately local and synchronous: publishing
calls each matching handler inline, in registration order, and returns when they are done.
There is no queue, no thread, no broker (no Kafka / RabbitMQ / Redis). A different transport
can later implement the same port without any publisher or subscriber changing.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, runtime_checkable

from event_bus.events import DomainEvent

EventHandler = Callable[[DomainEvent], None]
ErrorHandler = Callable[[DomainEvent, Exception], None]

# A sentinel subscription key meaning "every event, regardless of type".
ALL_EVENTS = "*"


@runtime_checkable
class EventBus(Protocol):
    """The port. Publishers depend on `publish`; subscribers register via `subscribe`.
    Subscribe to a concrete `DomainEvent` subclass for one event type, or to `ALL_EVENTS`
    for every event (audit sinks, tracers, dev logging)."""

    def subscribe(self, event_type: type[DomainEvent] | str, handler: EventHandler) -> None: ...

    def publish(self, event: DomainEvent) -> None: ...


class InProcessEventBus:
    """Synchronous, in-process dispatcher. Handler isolation: if an `error_handler` is
    injected, a handler that raises is routed to it and dispatch continues (fail-safe for
    observability — one bad audit sink never breaks the pipeline); with no `error_handler`
    the exception propagates (loud by default, per the coding standards)."""

    def __init__(self, *, error_handler: ErrorHandler | None = None) -> None:
        self._by_type: dict[str, list[EventHandler]] = {}
        self._error_handler = error_handler

    @staticmethod
    def _key(event_type: type[DomainEvent] | str) -> str:
        if isinstance(event_type, str):
            return event_type
        return event_type.name

    def subscribe(self, event_type: type[DomainEvent] | str, handler: EventHandler) -> None:
        self._by_type.setdefault(self._key(event_type), []).append(handler)

    def subscribe_all(self, handler: EventHandler) -> None:
        """Convenience for the common `subscribe(ALL_EVENTS, handler)` case."""
        self.subscribe(ALL_EVENTS, handler)

    def publish(self, event: DomainEvent) -> None:
        # type-specific handlers first (in registration order), then the wildcard handlers.
        handlers = [*self._by_type.get(event.name, ()), *self._by_type.get(ALL_EVENTS, ())]
        for handler in handlers:
            try:
                handler(event)
            except Exception as exc:  # noqa: BLE001 - isolation is the whole point here
                if self._error_handler is None:
                    raise
                self._error_handler(event, exc)


class RecordingEventBus:
    """A no-subscriber bus that just captures everything published, for tests and demos.
    It satisfies the `EventBus` port; `subscribe` is accepted but never dispatched to."""

    def __init__(self) -> None:
        self.events: list[DomainEvent] = []

    def subscribe(self, event_type: type[DomainEvent] | str, handler: EventHandler) -> None:
        return None

    def publish(self, event: DomainEvent) -> None:
        self.events.append(event)
