"""Shared value objects used across multiple bounded contexts."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from .enums import ConfidenceLevel
from .identifiers import KnowledgeSourceId


@dataclass(frozen=True)
class Confidence:
    """A numeric confidence in [0, 1] with a derived coarse level."""

    score: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.score <= 1.0:
            raise ValueError("Confidence score must be between 0.0 and 1.0")

    @property
    def level(self) -> ConfidenceLevel:
        if self.score < 0.4:
            return ConfidenceLevel.LOW
        if self.score < 0.75:
            return ConfidenceLevel.MEDIUM
        return ConfidenceLevel.HIGH

    @property
    def is_low(self) -> bool:
        return self.level is ConfidenceLevel.LOW


@dataclass(frozen=True)
class Citation:
    """A pointer back to a retrieved source supporting a claim (grounding)."""

    source_id: KnowledgeSourceId
    locator: str  # section/page/anchor within the source
    snippet: str | None = None

    def __post_init__(self) -> None:
        if not self.locator.strip():
            raise ValueError("Citation locator must not be empty")


@dataclass(frozen=True)
class DateRange:
    """A validity window. `end` of None means open-ended."""

    start: datetime
    end: datetime | None = None

    def __post_init__(self) -> None:
        if self.end is not None and self.end < self.start:
            raise ValueError("DateRange end must not precede start")

    def contains(self, moment: datetime) -> bool:
        if moment < self.start:
            return False
        return self.end is None or moment <= self.end

    def is_expired(self, at: datetime) -> bool:
        return self.end is not None and at > self.end


class ActorKind(str, Enum):
    """Who performed an action."""

    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"


@dataclass(frozen=True)
class Actor:
    """The actor responsible for an action (for audit and approvals)."""

    kind: ActorKind
    reference: str | None = None  # user id / agent name / system component
    display_name: str | None = None


@dataclass(frozen=True)
class TraceContext:
    """Distributed-trace correlation carried through the domain for auditability."""

    trace_id: str
    span_id: str | None = None


@dataclass(frozen=True, order=True)
class SemanticVersion:
    """Semantic version for tools, agents, and plugins."""

    major: int
    minor: int
    patch: int

    def __post_init__(self) -> None:
        for part in (self.major, self.minor, self.patch):
            if part < 0:
                raise ValueError("SemanticVersion parts must be non-negative")

    @classmethod
    def parse(cls, text: str) -> SemanticVersion:
        try:
            major, minor, patch = (int(p) for p in text.strip().split("."))
        except ValueError as exc:  # noqa: TRY003 - domain-friendly message
            raise ValueError(f"Invalid semantic version: {text!r}") from exc
        return cls(major, minor, patch)

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"
