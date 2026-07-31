"""The GRC Expert — frameworks, controls, risk, evidence, policy (§11; CLAUDE.md §13).

Realizes the Agent protocol for ``AgentRole.GRC_EXPERT``. It maps a mission to the real controls it
touches across the frameworks the platform serves (ISO 27001, NIST CSF, SOC 2, PCI DSS, GDPR) using
an injected ``FrameworkKnowledge`` catalog — real reference data matched by real keyword analysis,
never invented — and records a verdict: REQUEST_CHANGES ("evidence requested") when upstream reports
a shortfall, else PROCEED ("controls mapped; risk accepted"). Read-only; the mapping is grounded in
the catalog, and the seam lets the full ``framework-library`` (ADR 0050) replace the default later.
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
from devteam_organization.knowledge import (
    FrameworkKnowledge,
    default_framework_knowledge,
)


class GRCExpertAgent:
    role = AgentRole.GRC_EXPERT

    def __init__(self, knowledge: FrameworkKnowledge = default_framework_knowledge) -> None:
        self._knowledge = knowledge

    def handle(self, request: AgentRequest) -> AgentResult:
        controls = tuple(self._knowledge(request.intent))
        frameworks = sorted({control.framework for control in controls})
        mapping = "\n".join(
            (
                f"Controls mapped for: {request.intent.strip()}",
                *(f"- {control.label}" for control in controls),
                f"Frameworks touched: {', '.join(frameworks)}.",
                "Evidence expectation: attach the operating evidence for each mapped control.",
            )
        )
        shortfall = has_shortfall(inbox_text(request))
        verdict = AgentVerdict.REQUEST_CHANGES if shortfall else AgentVerdict.PROCEED
        rationale = (
            "evidence requested — upstream reports a shortfall to resolve before sign-off"
            if shortfall
            else f"controls mapped across {len(frameworks)} framework(s); residual risk accepted"
        )
        return AgentResult(
            ok=True,
            output=f"GRC Expert: {rationale}",
            artifacts=(
                AgentArtifact(
                    kind="grc_mapping",
                    title="controls & evidence mapping",
                    content=mapping,
                    produced_by=AgentRole.GRC_EXPERT,
                    source_ids=tuple(control.control_id for control in controls),
                ),
            ),
            decision=AgentDecision(
                verdict=verdict, by_role=AgentRole.GRC_EXPERT, rationale=rationale
            ),
            handoff=AgentHandoff(
                from_role=AgentRole.GRC_EXPERT,
                to_role=AgentRole.QA,
                reason="controls mapped; validate",
            ),
        )
