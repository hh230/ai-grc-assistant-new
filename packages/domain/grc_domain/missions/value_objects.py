"""Value objects for the Missions bounded context."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..shared.value_objects import Citation


@dataclass(frozen=True)
class MissionGoal:
    """The outcome a mission is chartered to achieve."""

    statement: str

    def __post_init__(self) -> None:
        if not self.statement.strip():
            raise ValueError("MissionGoal statement must not be empty")


@dataclass(frozen=True)
class ProposedAction:
    """A consequential action proposed at a human gate, with its grounding."""

    description: str
    citations: tuple[Citation, ...] = field(default_factory=tuple)
