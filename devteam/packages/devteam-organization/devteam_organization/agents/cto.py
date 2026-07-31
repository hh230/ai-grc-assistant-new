"""The CTO — technical planning, architecture, decomposition, engineering review (§11).

Realizes the Agent protocol for ``AgentRole.CTO``. It reads the CEO's mandate from the inbox and
turns the goal into a technical approach — a small, honest decomposition (design → implement →
verify, scoped to the goal) — then records an engineering verdict: REQUEST_CHANGES when the upstream
mandate is missing or already reports a shortfall, otherwise APPROVE (the architecture is coherent
and ready to build on). Read-only.
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

from devteam_organization.context import has_shortfall, inbox_text


class CTOAgent:
    role = AgentRole.CTO

    def handle(self, request: AgentRequest) -> AgentResult:
        goal = request.intent.strip()
        prior = inbox_text(request)
        if not prior.strip():
            rationale = "architecture: changes requested — no mandate from the CEO to plan against"
            return AgentResult(
                ok=True,
                output=f"CTO: {rationale}",
                decision=AgentDecision(
                    verdict=AgentVerdict.REQUEST_CHANGES,
                    by_role=AgentRole.CTO,
                    rationale=rationale,
                ),
            )
        plan = "\n".join(
            (
                f"Technical approach for: {goal}",
                "1. Design — define the change against the affected components and interfaces.",
                "2. Implement — smallest reversible increment, behind a flag where consequential.",
                "3. Verify — tests and review before any human-gated landing.",
            )
        )
        changes = has_shortfall(prior)
        verdict = AgentVerdict.REQUEST_CHANGES if changes else AgentVerdict.APPROVE
        rationale = (
            "architecture: changes requested — upstream reports a shortfall"
            if changes
            else "architecture approved; decomposition ready"
        )
        return AgentResult(
            ok=True,
            output=f"CTO: {rationale}",
            artifacts=(
                AgentArtifact(
                    kind="architecture",
                    title="technical plan",
                    content=plan,
                    produced_by=AgentRole.CTO,
                ),
            ),
            decision=AgentDecision(verdict=verdict, by_role=AgentRole.CTO, rationale=rationale),
            handoff=AgentHandoff(
                from_role=AgentRole.CTO, to_role=AgentRole.CISO, reason="plan ready; review it"
            ),
        )
