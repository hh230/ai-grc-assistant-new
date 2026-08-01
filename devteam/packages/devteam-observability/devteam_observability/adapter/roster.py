"""The platform roster mapping — the agents expressed as ``core`` identities.

Maps ``devteam_protocol`` roles and capabilities onto roster-neutral ``AgentId``s, and gives the
canonical capability -> role table (which mirrors the runtime compositions: TESTING runs QA,
IMPLEMENTATION runs the Developer, STRATEGY runs the CEO, and so on). ``role_for_tool`` turns a
``PlanStep.tool`` value back into the role that runs it, so the ``ObservingExecutor`` can name the
agent behind a step from the ``StepRequest`` alone — and return ``None`` for a non-agent tool (a Git
tool), whose step has no agent to observe.

Two cohorts share this one adapter — both are the PLATFORM subsystem, both observed identically:

- ``PLATFORM_ROSTER`` — the engineering squad (ADR 0061): Foreman, QA, Monitor, Security, Developer,
  Reviewer.
- ``ORG_ROSTER`` — the AI Organization (CLAUDE.md §11): CEO, CTO, CISO, GRC Expert, DevTeam,
  Supervisor. Added as a second roster here, additively — the extension seam this module exists to
  be (no ``core`` change). ``seed_roster`` seeds both, so the dashboard shows the whole platform.
"""

from __future__ import annotations

from devteam_protocol import AgentCapability, AgentRole

from devteam_observability.core import AgentId, AgentRuntimeRegistry, AgentSubsystem


def agent_id_for(role: AgentRole) -> AgentId:
    """The roster-neutral identity for a dev-team role: subsystem PLATFORM, role = enum value."""
    return AgentId(AgentSubsystem.PLATFORM, role.value)


# Human-facing labels for the dashboard; identity stays the (subsystem, role) pair.
DISPLAY_NAMES: dict[AgentRole, str] = {
    # The engineering squad (ADR 0061).
    AgentRole.FOREMAN: "Foreman",
    AgentRole.QA: "QA",
    AgentRole.MONITOR: "Monitor",
    AgentRole.SECURITY: "Security",
    AgentRole.DEVELOPER: "Developer",
    AgentRole.REVIEWER: "Reviewer",
    # The AI Organization (CLAUDE.md §11).
    AgentRole.CEO: "CEO",
    AgentRole.CTO: "CTO",
    AgentRole.CISO: "CISO",
    AgentRole.GRC_EXPERT: "GRC Expert",
    AgentRole.DEVTEAM: "DevTeam",
    AgentRole.SUPERVISOR: "Supervisor",
}

# Which role provides each planned capability (ADR 0063). Mirrors the runtime compositions
# (``build_default_agents`` for the squad, ``build_organization_agents`` for the org) so the
# observed role always matches the executed agent.
CAPABILITY_ROLES: dict[AgentCapability, AgentRole] = {
    # The engineering squad's capabilities.
    AgentCapability.TESTING: AgentRole.QA,
    AgentCapability.IMPLEMENTATION: AgentRole.DEVELOPER,
    AgentCapability.REVIEW: AgentRole.REVIEWER,
    AgentCapability.SECURITY: AgentRole.SECURITY,
    AgentCapability.MONITORING: AgentRole.MONITOR,
    # The AI Organization's capabilities. TESTING (above) is reused for the org's QA member.
    AgentCapability.STRATEGY: AgentRole.CEO,
    AgentCapability.ARCHITECTURE: AgentRole.CTO,
    AgentCapability.SECURITY_REVIEW: AgentRole.CISO,
    AgentCapability.GRC: AgentRole.GRC_EXPERT,
    AgentCapability.DELIVERY: AgentRole.DEVTEAM,
    AgentCapability.SUPERVISION: AgentRole.SUPERVISOR,
}

# The engineering squad (ADR 0061), for seeding the registry so every agent is visible before it
# does any work.
PLATFORM_ROSTER: tuple[AgentRole, ...] = (
    AgentRole.FOREMAN,
    AgentRole.QA,
    AgentRole.MONITOR,
    AgentRole.SECURITY,
    AgentRole.DEVELOPER,
    AgentRole.REVIEWER,
)

# The AI Organization (CLAUDE.md §11). QA is intentionally NOT repeated here — the org's quality
# member is the squad's QA agent (already in PLATFORM_ROSTER), reused rather than duplicated.
ORG_ROSTER: tuple[AgentRole, ...] = (
    AgentRole.CEO,
    AgentRole.CTO,
    AgentRole.CISO,
    AgentRole.GRC_EXPERT,
    AgentRole.DEVTEAM,
    AgentRole.SUPERVISOR,
)


def role_for_tool(tool: str) -> AgentRole | None:
    """The agent role a ``PlanStep.tool`` routes to, or ``None`` when the tool is not an agent
    capability (a Git tool such as ``apply_patch``) — that step has no agent to observe."""
    try:
        capability = AgentCapability(tool)
    except ValueError:
        return None
    return CAPABILITY_ROLES.get(capability)


def seed_roster(registry: AgentRuntimeRegistry) -> None:
    """Register the whole platform — the engineering squad and the AI Organization — so the
    dashboard shows every agent (idle) before any activity. ``register`` is idempotent, so a shared
    role (QA) seeded once is harmless to encounter twice."""
    for role in (*PLATFORM_ROSTER, *ORG_ROSTER):
        registry.register(agent_id_for(role), display_name=DISPLAY_NAMES[role])
