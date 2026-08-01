"""The Security agent (read-only) — dependency/secret scanning, SAST-lite (ADR 0061/0062).

Realizes the Agent protocol for AgentRole.SECURITY. It runs an injected scan (testable without a
real scanner), turning issues into AgentFindings and an AgentDecision: BLOCK on anything
high/critical, else PROCEED. Read-only — it scans, never writes; BLOCK is a recommendation, not an
authorization (the human gate, ADR 0044, is the only authority).
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

# Injected so Security is testable without a real scanner; the composition root binds the real one.
Scan = Callable[[], Sequence[AgentFinding]]
_BLOCKING = frozenset({FindingSeverity.HIGH, FindingSeverity.CRITICAL})


class SecurityAgent:
    role = AgentRole.SECURITY

    def __init__(self, scan: Scan) -> None:
        self._scan = scan

    def handle(self, request: AgentRequest) -> AgentResult:
        findings = tuple(self._scan())
        blocking = [finding for finding in findings if finding.severity in _BLOCKING]
        verdict = AgentVerdict.BLOCK if blocking else AgentVerdict.PROCEED
        rationale = f"{len(blocking)} blocking of {len(findings)} issue(s)"
        return AgentResult(
            ok=True,  # the step ran; issues are carried by the findings + the decision
            output=f"Security: {verdict.value} — {rationale}",
            findings=findings,
            artifacts=(
                AgentArtifact(
                    kind="security_report",
                    title="scan",
                    content=rationale,
                    produced_by=AgentRole.SECURITY,
                ),
            ),
            decision=AgentDecision(
                verdict=verdict, by_role=AgentRole.SECURITY, rationale=rationale
            ),
        )
