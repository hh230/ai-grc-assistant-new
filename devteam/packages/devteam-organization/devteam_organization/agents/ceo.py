"""The CEO — understands the mission, sets strategy, delegates, approves the direction (§11).

Realizes the Agent protocol for ``AgentRole.CEO``. As the first stage of an organization mission it
frames the goal into a mandate the rest of the org executes and records a strategic decision:
PROCEED when the goal is a real, actionable mandate, ESCALATE when there is nothing actionable to
delegate (a machine verdict — the human gate, ADR 0044, remains the only authority). The CEO's other
face, *delegation*, is the ``OrganizationPlanner`` (which stages to run); here the CEO executes the
strategy step. Read-only: it decides direction, it changes nothing.
"""

from __future__ import annotations

from devteam_protocol import (
    AgentArtifact,
    AgentDecision,
    AgentHandoff,
    AgentRequest,
    AgentResult,
    AgentRole,
    AgentVerdict,
)


class CEOAgent:
    role = AgentRole.CEO

    def handle(self, request: AgentRequest) -> AgentResult:
        goal = request.intent.strip()
        if not goal:
            rationale = "escalated: no actionable mandate to delegate"
            return AgentResult(
                ok=True,
                output=f"CEO: {rationale}",
                decision=AgentDecision(
                    verdict=AgentVerdict.ESCALATE, by_role=AgentRole.CEO, rationale=rationale
                ),
            )
        mandate = (
            f"Mission understood: {goal}\n"
            "Delegating across the organization — architecture, security, GRC, quality, delivery."
        )
        rationale = "mission approved; the organization is engaged"
        return AgentResult(
            ok=True,
            output=f"CEO: {rationale}",
            artifacts=(
                AgentArtifact(
                    kind="strategy",
                    title="CEO mandate",
                    content=mandate,
                    produced_by=AgentRole.CEO,
                ),
            ),
            decision=AgentDecision(
                verdict=AgentVerdict.APPROVE, by_role=AgentRole.CEO, rationale=rationale
            ),
            handoff=AgentHandoff(
                from_role=AgentRole.CEO, to_role=AgentRole.CTO, reason="strategy set; plan it"
            ),
        )
