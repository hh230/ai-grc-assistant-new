"""The shared vocabulary every QA agent speaks.

Agents are deliberately thin: the *boundary is the finding*, not the class hierarchy (the same
principle ADR 0062 sets for the platform's other agent rosters). An agent proposes work or
reports findings; it owns no storage and no execution loop of its own. That is what lets a new
surface — HTTP against apps/web, or a browser — be added later by giving the existing agents a
different `Surface`, instead of redesigning the roster.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Severity(str, Enum):
    """How much a finding should worry a human.

    `CRASH` is separated from `INVARIANT` on purpose: an unexpected exception means the system
    failed in a way nobody modelled, which is strictly worse than a modelled rule being violated.
    """

    CRASH = "crash"
    INVARIANT = "invariant"
    SUSPICIOUS = "suspicious"


@dataclass(frozen=True)
class Finding:
    """One thing worth a human's attention, with everything needed to reproduce it."""

    agent: str
    severity: Severity
    kind: str
    detail: str
    # The single most valuable field: what to run to see it again.
    reproduce: str
    seed: int | None = None

    def as_row(self) -> dict[str, object]:
        return {
            "agent": self.agent,
            "severity": self.severity.value,
            "kind": self.kind,
            "detail": self.detail,
            "reproduce": self.reproduce,
            "seed": self.seed,
        }


@dataclass
class AgentReport:
    """What one agent produced in one pass."""

    agent: str
    findings: list[Finding] = field(default_factory=list)
    # Free-form counters the Reporter turns into a human summary (scenarios run, inputs tried…).
    stats: dict[str, int] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.findings

    def bump(self, key: str, by: int = 1) -> None:
        self.stats[key] = self.stats.get(key, 0) + by
