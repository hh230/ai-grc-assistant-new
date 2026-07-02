"""Event dispatcher adapter for the application's ``EventDispatcher`` port.

After a unit of work commits, the handler hands the recorded domain events here. For the API
runtime this dispatcher (1) records the event to the structured log as an audit-stream line
(CLAUDE.md §16, §19) and (2) retains them in a bounded in-process buffer so tests and the
``/internal`` observability surface can assert what happened. A production deployment swaps
this for a transactional-outbox relay onto the event bus — the port is unchanged.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Sequence

from grc_domain.shared.events import DomainEvent
from grc_services.shared.events import EventDispatcher

from ..observability import get_logger

_logger = get_logger("grc_api.events")


class LoggingEventDispatcher(EventDispatcher):
    """Logs each domain event and keeps the most recent ones in memory (bounded)."""

    def __init__(self, *, buffer_size: int = 1000) -> None:
        self._recent: deque[DomainEvent] = deque(maxlen=buffer_size)

    async def dispatch(self, events: Sequence[DomainEvent]) -> None:
        for event in events:
            self._recent.append(event)
            _logger.info(
                "domain_event",
                extra={"event_type": type(event).__name__},
            )

    @property
    def recent(self) -> tuple[DomainEvent, ...]:
        return tuple(self._recent)
