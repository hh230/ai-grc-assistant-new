"""MissionSignalReceived — a correlated trigger absorbed into a live mission (ADR 0064).

The event UpdateMission emits: the new trigger is recorded as audited provenance on the existing
mission (tenant- and mission-stamped, carrying the finding's kind + summary), with no lifecycle
mutation. It rides the existing event bus + audit; the outbox EVENT_REGISTRY registration (ADR 0044
§6) lands with the durable path.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from event_bus.events import DomainEvent


@dataclass(frozen=True)
class MissionSignalReceived(DomainEvent):
    """A correlated trigger recorded against an existing mission. Summary fields only (ids, kinds),
    never payloads — like every domain event (ADR 0042 §12.2)."""

    name: ClassVar[str] = "mission.signal_received"

    origin: str = ""
    finding_kind: str = ""
    finding_summary: str = ""

    def _payload(self) -> dict[str, object]:
        return {
            "origin": self.origin,
            "finding_kind": self.finding_kind,
            "finding_summary": self.finding_summary,
        }
