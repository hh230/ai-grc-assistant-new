"""Event dispatcher interface (port).

After a unit of work commits, the recorded domain events are handed to an
`EventDispatcher` for publication to subscribers (projections, integrations, the event
bus). The application depends only on this interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from grc_domain.shared.events import DomainEvent


class EventDispatcher(ABC):
    @abstractmethod
    async def dispatch(self, events: Sequence[DomainEvent]) -> None: ...
