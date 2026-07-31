"""The AI Organization's mission pipeline — the ordered chain of governed stages (CLAUDE.md §11).

A mission flows CEO → CTO → CISO → GRC Expert → QA → DevTeam, each stage a capability the frozen
Mission Engine routes to via ``PlanStep.tool`` (ADR 0048) and the observability adapter names as the
matching agent (``CAPABILITY_ROLES``). This module is pure data: the ordered ``Stage`` list. The
planner turns it (or a subset of it) into a ``Plan``; the runtime executes it; the observer records
the CEO→…→DevTeam handoff chain. No control flow lives here — routing is the Mission Engine's, the
skip decision is the planner's.
"""

from __future__ import annotations

from dataclasses import dataclass

from devteam_protocol import AgentCapability, AgentRole


@dataclass(frozen=True)
class Stage:
    """One governed stage of an organization mission: the capability the step routes to, the role
    that provides it (kept aligned with ``CAPABILITY_ROLES`` so the observed agent matches the
    executed one), the org member's display title, and the mandate the step carries as its
    instruction."""

    capability: AgentCapability
    role: AgentRole
    title: str
    mandate: str


# The canonical organization pipeline, in order. TESTING is the engineering squad's QA capability,
# reused as the organization's quality stage (its agent is the squad's QA agent, not a duplicate).
ORG_PIPELINE: tuple[Stage, ...] = (
    Stage(
        AgentCapability.STRATEGY, AgentRole.CEO, "CEO", "understand the mission and set strategy"
    ),
    Stage(
        AgentCapability.ARCHITECTURE,
        AgentRole.CTO,
        "CTO",
        "produce the technical plan and architecture",
    ),
    Stage(
        AgentCapability.SECURITY_REVIEW,
        AgentRole.CISO,
        "CISO",
        "security review, threat analysis, and compliance validation",
    ),
    Stage(
        AgentCapability.GRC,
        AgentRole.GRC_EXPERT,
        "GRC Expert",
        "map frameworks, controls, risk, and evidence expectations",
    ),
    Stage(
        AgentCapability.TESTING,
        AgentRole.QA,
        "QA",
        "validate the outputs and run the quality gate",
    ),
    Stage(
        AgentCapability.DELIVERY,
        AgentRole.DEVTEAM,
        "DevTeam",
        "consolidate the organization's plan into a delivery plan",
    ),
)
