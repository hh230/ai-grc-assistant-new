"""``AgentFinding`` — one thing an agent or trigger noticed worth acting on (ADR 0061).

The immutable, pre-mission fact a specialist (Monitor, QA, Security, Reviewer) or a trigger
produces: a failing CI job, an error spike, a vulnerable dependency, a review objection. The
Foreman turns findings into Dev Missions; agents exchange them across the collaboration protocol
(``AgentResult.findings``, ``AgentHandoff.findings``). Pure data, like the Core's value objects
(``Plan``, ``StepResult``). It lives in this shared bottom package so the trigger layer and the
protocol reuse the one finding concept — never duplicated.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from pipeline_contracts import dataclass_dict


class FindingSeverity(str, Enum):
    """How urgently a finding should be acted on. Declared low → critical for triage."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class AgentFinding:
    """One observation an agent may open or advance a mission for. ``kind`` is a stable machine
    label (e.g. ``"ci_failure"``, ``"vulnerable_dependency"``); ``source`` names the agent/tool
    that found it; ``summary`` is a one-line headline; ``detail`` the body; ``refs`` are stable
    pointers (file paths, CI run ids, CVE ids) an auditor can follow."""

    kind: str
    severity: FindingSeverity
    summary: str
    source: str = ""
    detail: str = ""
    refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.kind or not self.kind.strip():
            raise ValueError("an AgentFinding must have a non-empty kind")
        if not self.summary or not self.summary.strip():
            raise ValueError("an AgentFinding must have a non-empty summary")
        object.__setattr__(self, "refs", tuple(self.refs))

    def to_dict(self) -> dict[str, object]:
        # `to_plain` serializes the FindingSeverity enum as its value automatically.
        return dataclass_dict(self)
