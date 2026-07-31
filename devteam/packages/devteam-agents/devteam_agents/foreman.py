"""The Foreman — the dev team's planner (ADR 0061/0062/0063).

Turns a goal into a composite mission Plan whose steps route by CAPABILITY (ADR 0063) via
PlanStep.tool (ADR 0048): the Foreman plans in capabilities and imports no agent class. It is the
"brain" altitude (the Mission Engine drives the plan, ADR 0042 §12.8) — it plans and routes, it does
not execute specialists. It also realizes the Agent protocol (asked to handle, it returns the plan
as an artifact), so the Foreman is itself in the roster.
"""

from __future__ import annotations

from devteam_protocol import (
    AgentArtifact,
    AgentCapability,
    AgentDecision,
    AgentRequest,
    AgentResult,
    AgentRole,
    AgentVerdict,
)
from devteam_tools import APPLY_PATCH, COMMIT_CHANGES, OPEN_PR, PUSH_BRANCH
from mission_engine.plan import Plan, PlanStep


class Foreman:
    role = AgentRole.FOREMAN

    def plan_quality_review(self) -> Plan:
        """The canonical read-only spine mission: testing runs the suites, then review reviews the
        outcome. Two capability steps; read-only, so no human gate (ADR 0042 §11)."""
        return Plan(
            steps=(
                PlanStep(
                    description="run standalone test suites",
                    instruction="run the quality gate across the standalone packages",
                    tool=AgentCapability.TESTING.value,
                ),
                PlanStep(
                    description="review the testing outcome",
                    instruction="review the test results and decide",
                    tool=AgentCapability.REVIEW.value,
                ),
            )
        )

    def plan_fix_it(self, issue: str) -> Plan:
        """The gated fix-it mission: the Developer (IMPLEMENTATION) diagnoses and proposes a diff
        (read-only), then the change is landed by the consequential Git Tools. The plan places a
        SINGLE human gate — apply_patch is the consequential step, so the Mission Engine pauses once
        (ADR 0044) before the first side effect; commit/push/open_pr follow non-gated, covered by
        that one "land this patch" approval. That is the target behavior: pause before any
        consequential action, then after approval apply, commit, push, and open a PR automatically.
        The tools still DECLARE consequential in their specs; consequential here is the plan's gate
        placement (the engine gates on the step flag, never the tool's profile)."""
        return Plan(
            steps=(
                PlanStep(
                    description="diagnose the issue and propose a patch",
                    instruction=f"diagnose and propose a patch for: {issue}",
                    tool=AgentCapability.IMPLEMENTATION.value,
                ),
                PlanStep(
                    description="land the patch: apply, commit, push, open a PR",
                    instruction="",  # apply_patch reads the diff from the prior context (ADR 0051)
                    consequential=True,  # the one human gate, before any repository side effect
                    tool=APPLY_PATCH,
                ),
                PlanStep(
                    description="commit the change",
                    instruction=f"fix: {issue}",
                    tool=COMMIT_CHANGES,
                ),
                PlanStep(
                    description="push the branch",
                    instruction=issue,  # push_branch slugifies this into devteam/<slug>
                    tool=PUSH_BRANCH,
                ),
                PlanStep(
                    description="open a pull request",
                    instruction=f"Fix: {issue}",
                    tool=OPEN_PR,
                ),
            )
        )

    def handle(self, request: AgentRequest) -> AgentResult:
        plan = self.plan_quality_review()
        rendered = "\n".join(
            f"{i}. [{step.tool}] {step.description}" for i, step in enumerate(plan.steps, start=1)
        )
        return AgentResult(
            ok=True,
            output=f"planned {len(plan.steps)} step(s)",
            artifacts=(
                AgentArtifact(
                    kind="mission_plan",
                    title="quality review plan",
                    content=rendered,
                    produced_by=AgentRole.FOREMAN,
                ),
            ),
            decision=AgentDecision(verdict=AgentVerdict.PROCEED, by_role=AgentRole.FOREMAN),
        )
