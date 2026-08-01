"""The CISO — security review, threat analysis, compliance validation, sign-off (§11).

Realizes the Agent protocol for ``AgentRole.CISO``. It runs an injected threat/security review over
the mission (testable without a real scanner; the composition binds the real source — the same seam
the engineering squad's Security agent uses) and records a verdict: BLOCK on any high/critical
finding OR when upstream already reported a shortfall, else APPROVE (security sign-off). BLOCK is a
recommendation, not an authorization — the human gate (ADR 0044) is the only authority. Read-only.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from devteam_contracts import AgentFinding, FindingSeverity
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

# Injected so the CISO is testable without a real scanner; the composition binds the real threat
# review. It sees the request so a real review can consider the mission being assessed.
ThreatReview = Callable[[AgentRequest], Sequence[AgentFinding]]
_BLOCKING = frozenset({FindingSeverity.HIGH, FindingSeverity.CRITICAL})


def _no_findings(_request: AgentRequest) -> Sequence[AgentFinding]:
    """The default review: nothing found. A real threat-intel/SAST source is injected at wiring."""
    return ()


class CISOAgent:
    role = AgentRole.CISO

    def __init__(self, review: ThreatReview = _no_findings) -> None:
        self._review = review

    def handle(self, request: AgentRequest) -> AgentResult:
        findings = tuple(self._review(request))
        blocking = [finding for finding in findings if finding.severity in _BLOCKING]
        upstream_shortfall = has_shortfall(inbox_text(request))
        if blocking or upstream_shortfall:
            verdict = AgentVerdict.BLOCK
            reason = (
                f"{len(blocking)} high/critical finding(s)"
                if blocking
                else "upstream reports a shortfall"
            )
            rationale = f"security: BLOCKED — {reason}"
        else:
            verdict = AgentVerdict.APPROVE
            rationale = f"security approved; {len(findings)} finding(s), none blocking"
        return AgentResult(
            ok=True,
            output=f"CISO: {rationale}",
            findings=findings,
            artifacts=(
                AgentArtifact(
                    kind="security_review",
                    title="CISO review",
                    content=rationale,
                    produced_by=AgentRole.CISO,
                ),
            ),
            decision=AgentDecision(verdict=verdict, by_role=AgentRole.CISO, rationale=rationale),
            handoff=AgentHandoff(
                from_role=AgentRole.CISO,
                to_role=AgentRole.GRC_EXPERT,
                reason="security reviewed; map controls",
            ),
        )
