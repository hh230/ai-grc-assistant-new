"""Base domain event (shared kernel)."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, kw_only=True)
class DomainEvent:
    """Immutable, past-tense fact about something that happened in the domain.

    Subclasses add their own keyword-only fields. Events carry no behavior and no
    infrastructure concerns — publishing/handling lives outside the domain.
    """

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    occurred_at: datetime = field(default_factory=_utcnow)
