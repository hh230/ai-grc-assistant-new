"""Value objects for the Reporting bounded context."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..shared.value_objects import Citation


@dataclass(frozen=True)
class ReportSection:
    """A section of a report. Content generation is external; this is structure + grounding."""

    heading: str
    body: str
    citations: tuple[Citation, ...] = field(default_factory=tuple)
