"""The Supervisor agent — the observable heartbeat over platform health (§11).

Realizes the Agent protocol for ``AgentRole.SUPERVISOR``. Run as a periodic "platform health check"
mission, it reads an injected ``HealthReport`` (computed from the live ``RuntimeStateView``) and
records a verdict: PROCEED when the platform is healthy, ESCALATE when an agent or mission is
stalled. This is what makes the Supervisor a live, observable participant doing REAL work (a real
health check over real runtime facts) rather than a silent background thread. Recovery — acting on a
stall — is the Supervisor *controller*'s job; this stage observes and reports. Read-only.
"""

from __future__ import annotations

from collections.abc import Callable

from devteam_protocol import (
    AgentArtifact,
    AgentDecision,
    AgentRequest,
    AgentResult,
    AgentRole,
    AgentVerdict,
)

from devteam_organization.health import HealthReport

# Injected so the agent is testable with a canned report; the runtime binds it to the live view.
HealthSource = Callable[[], HealthReport]


class SupervisorAgent:
    role = AgentRole.SUPERVISOR

    def __init__(self, health: HealthSource) -> None:
        self._health = health

    def handle(self, request: AgentRequest) -> AgentResult:
        report = self._health()
        verdict = AgentVerdict.PROCEED if report.healthy else AgentVerdict.ESCALATE
        detail = "\n".join(
            (
                report.summary,
                *(f"- stalled agent: {key}" for key in report.stalled_agents),
                *(f"- stalled mission: {mid}" for mid in report.stalled_missions),
            )
        )
        return AgentResult(
            ok=True,
            output=f"Supervisor: {report.summary}",
            artifacts=(
                AgentArtifact(
                    kind="health_report",
                    title="platform health check",
                    content=detail,
                    produced_by=AgentRole.SUPERVISOR,
                ),
            ),
            decision=AgentDecision(
                verdict=verdict,
                by_role=AgentRole.SUPERVISOR,
                rationale=report.summary,
            ),
        )
