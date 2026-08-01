"""The organization planner — the CEO's delegation, as a first-class Plan (§11; ADR 0042/0048).

The CEO's *delegation* face: turn a mission goal into the capability-routed ``Plan`` the frozen
Mission Engine drives (CEO → CTO → CISO → GRC → QA → DevTeam). Planning is separate from execution
(the engine is the brain, ADR 0042 §12.8; this only decides the steps), and the plan is a stored,
inspectable artifact — never LLM text.

**Dynamic skipping (the task's routing requirement).** The CEO always leads and the DevTeam always
closes; the middle stages are included only when the goal is relevant to them — so a pure
policy-drafting mission skips the CTO, a code change skips the GRC stage, and so on. When the goal
raises no specific signal the planner keeps the FULL pipeline (fail toward more governance, never
less). A caller may also pass an explicit stage set to scope a mission precisely.
"""

from __future__ import annotations

from collections.abc import Sequence

from devteam_protocol import AgentCapability
from mission_engine.plan import Plan, PlanStep

from devteam_organization.stages import ORG_PIPELINE, Stage

# The bookend stages the organization always runs: the CEO understands and delegates; the DevTeam
# consolidates delivery. Only the middle stages are ever skipped.
_ALWAYS = frozenset({AgentCapability.STRATEGY, AgentCapability.DELIVERY})

# The words that make a middle stage relevant to a goal. Real keyword analysis over the mandate.
_RELEVANCE: dict[AgentCapability, tuple[str, ...]] = {
    AgentCapability.ARCHITECTURE: (
        "implement", "build", "add", "create", "fix", "refactor", "migrate", "feature",
        "integrate", "deploy", "api", "service", "code", "architecture", "design", "system",
        "pipeline", "endpoint",
    ),
    AgentCapability.SECURITY_REVIEW: (
        "security", "secure", "threat", "vuln", "auth", "access", "encrypt", "secret",
        "credential", "tenant", "injection", "attack", "login", "rate limit", "permission",
    ),
    AgentCapability.GRC: (
        "iso", "nist", "soc", "pci", "gdpr", "pdpl", "sama", "nca", "control", "policy", "risk",
        "evidence", "compliance", "audit", "framework", "regulation", "governance", "privacy",
    ),
    AgentCapability.TESTING: (
        "test", "qa", "verify", "validate", "quality", "regression", "coverage",
    ),
}


class OrganizationPlanner:
    """Builds the organization mission Plan for a goal. Stateless; construct once and reuse."""

    def plan(self, goal: str, *, stages: Sequence[AgentCapability] | None = None) -> Plan:
        """The capability-routed plan for ``goal``. Pass ``stages`` to scope the mission explicitly
        (filtered into pipeline order); otherwise the planner selects the relevant stages."""
        selected = (
            self._filter_to_pipeline(stages) if stages is not None else self.select_stages(goal)
        )
        steps = tuple(
            PlanStep(
                description=f"{stage.title}: {stage.mandate}",
                instruction=goal,
                tool=stage.capability.value,
            )
            for stage in selected
        )
        return Plan(steps=steps)

    def select_stages(self, goal: str) -> tuple[Stage, ...]:
        """Which stages this goal needs. Bookends always; middle stages by relevance; full pipeline
        when the goal raises no signal. Anything the CTO builds also gets a CISO review and QA."""
        lowered = goal.lower()
        chosen: set[AgentCapability] = set(_ALWAYS)
        for capability, keywords in _RELEVANCE.items():
            if any(keyword in lowered for keyword in keywords):
                chosen.add(capability)
        if AgentCapability.ARCHITECTURE in chosen:
            # Anything built is reviewed for security and validated by QA.
            chosen.update({AgentCapability.SECURITY_REVIEW, AgentCapability.TESTING})
        if chosen == _ALWAYS:
            # No signal at all → keep the full pipeline (fail toward more governance).
            return ORG_PIPELINE
        return tuple(stage for stage in ORG_PIPELINE if stage.capability in chosen)

    @staticmethod
    def _filter_to_pipeline(stages: Sequence[AgentCapability]) -> tuple[Stage, ...]:
        wanted = set(stages)
        selected = tuple(stage for stage in ORG_PIPELINE if stage.capability in wanted)
        if not selected:
            raise ValueError("no requested stage is part of the organization pipeline")
        return selected
