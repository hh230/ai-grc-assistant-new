"""The platform roster mapping: roles, capability routing, and seeding (squad + AI Organization)."""

from __future__ import annotations

from devteam_observability import AgentRuntimeRegistry, AgentStatus, agent_id_for, role_for_tool
from devteam_observability.adapter import ORG_ROSTER, PLATFORM_ROSTER, seed_roster
from devteam_protocol import AgentCapability, AgentRole


def test_agent_id_is_platform_scoped_role() -> None:
    assert agent_id_for(AgentRole.DEVELOPER).key == "platform:developer"
    assert agent_id_for(AgentRole.CEO).key == "platform:ceo"


def test_role_for_tool_maps_capabilities_to_roles() -> None:
    # The engineering squad's capabilities.
    assert role_for_tool(AgentCapability.TESTING.value) is AgentRole.QA
    assert role_for_tool(AgentCapability.IMPLEMENTATION.value) is AgentRole.DEVELOPER
    assert role_for_tool(AgentCapability.REVIEW.value) is AgentRole.REVIEWER
    # The AI Organization's capabilities.
    assert role_for_tool(AgentCapability.STRATEGY.value) is AgentRole.CEO
    assert role_for_tool(AgentCapability.ARCHITECTURE.value) is AgentRole.CTO
    assert role_for_tool(AgentCapability.SECURITY_REVIEW.value) is AgentRole.CISO
    assert role_for_tool(AgentCapability.GRC.value) is AgentRole.GRC_EXPERT
    assert role_for_tool(AgentCapability.DELIVERY.value) is AgentRole.DEVTEAM
    assert role_for_tool(AgentCapability.SUPERVISION.value) is AgentRole.SUPERVISOR


def test_role_for_a_non_agent_tool_is_none() -> None:
    # A Git tool step (apply_patch, open_pr) has no agent to observe.
    assert role_for_tool("apply_patch") is None
    assert role_for_tool("open_pr") is None
    assert role_for_tool("") is None


def test_seed_registers_the_whole_platform_idle() -> None:
    registry = AgentRuntimeRegistry()
    seed_roster(registry)
    states = registry.all_states()
    # The squad plus the AI Organization; QA is shared (in PLATFORM_ROSTER, not repeated in ORG).
    assert len(states) == len(PLATFORM_ROSTER) + len(ORG_ROSTER)
    assert all(state.status is AgentStatus.IDLE for state in states)
    keys = {state.agent_id.key for state in states}
    assert {"platform:foreman", "platform:developer"} <= keys  # engineering squad
    assert {"platform:ceo", "platform:ciso", "platform:devteam", "platform:supervisor"} <= keys
