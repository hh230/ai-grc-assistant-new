"""The ``RuntimeObserver`` port — the one seam every runtime fact travels through.

Adapters (the DevTeam adapter today, another agent system tomorrow) depend only on this port; they
call ``observe`` and know nothing about what consumes the event. The in-memory
``AgentRuntimeRegistry`` realizes it (folding events into live state); a journaling observer will
realize it too (appending events to disk for the dashboard's process). Because there is a genuine
second realization, this is a real port, not a premature abstraction (Port-Worthiness rule).

``CompositeObserver`` fans one event out to several observers — the runtime needs the registry AND
the journal on the same stream. It is fail-safe: observability must never break the runtime it
watches, so one observer that raises is isolated and the rest still see the event.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Protocol, runtime_checkable

from devteam_observability.core.events import RuntimeEvent

ObserverErrorHandler = Callable[[RuntimeEvent, Exception], None]


@runtime_checkable
class RuntimeObserver(Protocol):
    """Receives one runtime fact. Realized by the registry (fold into state), the journal (append
    to disk), and any other consumer. Implementations must not raise for control flow — a bad
    observer is isolated by ``CompositeObserver``, never allowed to break the runtime."""

    def observe(self, event: RuntimeEvent) -> None: ...


class CompositeObserver:
    """Fan one event out to many observers, in order. Fail-safe: with an ``error_handler`` a raising
    observer is routed to it and dispatch continues; without one the exception propagates (loud by
    default, matching the Core's ``InProcessEventBus``)."""

    def __init__(
        self,
        observers: Iterable[RuntimeObserver],
        *,
        error_handler: ObserverErrorHandler | None = None,
    ) -> None:
        self._observers: list[RuntimeObserver] = list(observers)
        self._error_handler = error_handler

    def observe(self, event: RuntimeEvent) -> None:
        for observer in self._observers:
            try:
                observer.observe(event)
            except Exception as exc:  # noqa: BLE001 - isolation is the whole point here
                if self._error_handler is None:
                    raise
                self._error_handler(event, exc)
