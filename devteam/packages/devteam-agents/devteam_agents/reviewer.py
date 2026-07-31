"""The Reviewer agent (read-only) — reviews the work handed in and issues a verdict (ADR 0061/0062).

Realizes the Agent protocol for AgentRole.REVIEWER. It reads the inbox handoff and returns an
AgentResult with an AgentDecision: APPROVE when the work is clean, REQUEST_CHANGES on a shortfall,
ABSTAIN when nothing was handed in. A machine verdict, never an authorization — the human gate
(ADR 0044) remains the only authority. Read-only.

Today the seam carries only prior outputs (ADR 0062 rule 4), so the Reviewer reads the QA summary
line; deep review over structured upstream findings arrives with the Foreman's rich-layer
orchestration (a tracked refinement).
"""

from __future__ import annotations

import re

from devteam_protocol import (
    AgentArtifact,
    AgentDecision,
    AgentRequest,
    AgentResult,
    AgentRole,
    AgentVerdict,
)

# QA's output reads "QA: N/M suites green"; N < M is a shortfall signal.
_QA_SUMMARY = re.compile(r"(\d+)/(\d+) suites green")


class ReviewerAgent:
    role = AgentRole.REVIEWER

    def handle(self, request: AgentRequest) -> AgentResult:
        reviewed = request.inbox.artifacts if request.inbox is not None else ()
        reviewed_text = "\n".join(artifact.content for artifact in reviewed)
        if not reviewed:
            verdict, rationale = AgentVerdict.ABSTAIN, "nothing handed in to review"
        elif _looks_short(reviewed_text):
            verdict, rationale = AgentVerdict.REQUEST_CHANGES, "upstream work reports a shortfall"
        else:
            verdict = AgentVerdict.APPROVE
            rationale = f"reviewed {len(reviewed)} artifact(s); no failure signal"
        return AgentResult(
            # The STEP succeeded (the review ran); the verdict carries approve/request_changes.
            ok=True,
            output=f"Reviewer: {verdict.value} — {rationale}",
            artifacts=(
                AgentArtifact(
                    kind="review",
                    title="review summary",
                    content=rationale,
                    produced_by=AgentRole.REVIEWER,
                ),
            ),
            decision=AgentDecision(
                verdict=verdict, by_role=AgentRole.REVIEWER, rationale=rationale
            ),
        )


def _looks_short(text: str) -> bool:
    """A shortfall signal in the reviewed text: QA reported fewer green suites than total."""
    match = _QA_SUMMARY.search(text)
    if match is None:
        return False
    return int(match.group(1)) < int(match.group(2))
