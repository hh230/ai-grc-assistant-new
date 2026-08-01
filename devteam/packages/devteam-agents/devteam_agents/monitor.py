"""The Monitor agent (read-only) — watches logs/CI/errors and raises findings (ADR 0061/0062).

Realizes the Agent protocol for AgentRole.MONITOR. It runs an injected observation (testable
without a live source), turning what it sees into AgentFindings and an AgentDecision: ESCALATE on
anything high/critical, else PROCEED. Read-only — it observes, it never writes.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from devteam_contracts import AgentFinding, FindingSeverity
from devteam_protocol import (
    AgentArtifact,
    AgentDecision,
    AgentRequest,
    AgentResult,
    AgentRole,
    AgentVerdict,
)

# Injected so Monitor is testable without a live source; the composition root binds the real one.
Observation = Callable[[], Sequence[AgentFinding]]
_ALERTING = frozenset({FindingSeverity.HIGH, FindingSeverity.CRITICAL})


class MonitorAgent:
    role = AgentRole.MONITOR

    def __init__(self, observe: Observation) -> None:
        self._observe = observe

    def handle(self, request: AgentRequest) -> AgentResult:
        findings = tuple(self._observe())
        alerting = [finding for finding in findings if finding.severity in _ALERTING]
        verdict = AgentVerdict.ESCALATE if alerting else AgentVerdict.PROCEED
        rationale = f"{len(alerting)} alert(s) across {len(findings)} observation(s)"
        return AgentResult(
            ok=True,  # the step ran; anomalies are carried by the findings + the decision
            output=f"Monitor: {verdict.value} — {rationale}",
            findings=findings,
            artifacts=(
                AgentArtifact(
                    kind="monitor_report",
                    title="observations",
                    content=rationale,
                    produced_by=AgentRole.MONITOR,
                ),
            ),
            decision=AgentDecision(verdict=verdict, by_role=AgentRole.MONITOR, rationale=rationale),
        )
