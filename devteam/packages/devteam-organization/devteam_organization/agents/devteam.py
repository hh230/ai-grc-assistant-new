"""The DevTeam — consolidates the organization's plan into delivery (§11).

Realizes the Agent protocol for ``AgentRole.DEVTEAM``, the final stage. It reads the whole inbox
(the CEO's mandate, the CTO's plan, the CISO's review, the GRC mapping, the QA result) and
consolidates a delivery plan, recording a verdict: REQUEST_CHANGES when an upstream stage flags a
shortfall (do not deliver over a red flag), else PROCEED. Crucially it does NOT land code: actual
implementation runs through the engineering squad's existing human-gated fix-it flow (Developer →
apply/commit/push/PR behind the ADR-0044 gate). This stage plans delivery; the gate authorizes it.
Read-only.
"""

from __future__ import annotations

from devteam_protocol import (
    AgentArtifact,
    AgentDecision,
    AgentRequest,
    AgentResult,
    AgentRole,
    AgentVerdict,
)

from devteam_organization.context import has_shortfall, inbox_text


class DevTeamAgent:
    role = AgentRole.DEVTEAM

    def handle(self, request: AgentRequest) -> AgentResult:
        prior = inbox_text(request)
        shortfall = has_shortfall(prior)
        plan = "\n".join(
            (
                f"Delivery plan for: {request.intent.strip()}",
                "- Consolidated the organization's strategy, architecture, security, GRC, and QA.",
                "- Implementation lands through the engineering squad's human-gated fix-it flow;",
                "  nothing consequential ships without the ADR-0044 approval gate.",
            )
        )
        verdict = AgentVerdict.REQUEST_CHANGES if shortfall else AgentVerdict.PROCEED
        rationale = (
            "delivery held: an upstream stage requested changes — resolve before landing"
            if shortfall
            else "delivery approved; ready to land through the human-gated fix-it flow"
        )
        return AgentResult(
            ok=True,
            output=f"DevTeam: {rationale}",
            artifacts=(
                AgentArtifact(
                    kind="delivery_plan",
                    title="delivery plan",
                    content=plan,
                    produced_by=AgentRole.DEVTEAM,
                ),
            ),
            decision=AgentDecision(
                verdict=verdict, by_role=AgentRole.DEVTEAM, rationale=rationale
            ),
        )
