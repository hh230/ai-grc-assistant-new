"""SQLAlchemy transactional outbox — the single source of integration events.

:class:`SqlAlchemyOutbox` stages integration events as ``outbox_messages`` rows on the
*current* session. Because the Unit of Work flushes and commits those rows in the same
transaction as the aggregate changes, an event is persisted if and only if its state change
was, giving exactly-once *capture* (publication is at-least-once via a downstream relay).

This module only *orchestrates persistence*; the translation from an integration event to a
row lives in :mod:`grc_persistence.mappers.events`.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from .contracts.outbox import IntegrationEvent, Outbox
from .mappers.events import integration_event_to_model


class SqlAlchemyOutbox(Outbox):
    """Writes integration events into the outbox table within the active transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def enqueue(self, events: Sequence[IntegrationEvent]) -> None:
        if not events:
            return
        created_at = datetime.now(timezone.utc)
        self._session.add_all(
            integration_event_to_model(event, created_at=created_at) for event in events
        )
