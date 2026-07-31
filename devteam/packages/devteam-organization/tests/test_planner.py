"""The organization planner — the CEO→…→DevTeam plan and its dynamic stage selection."""

from __future__ import annotations

from devteam_organization import OrganizationPlanner
from devteam_protocol import AgentCapability

_PIPELINE_TOOLS = [
    AgentCapability.STRATEGY.value,
    AgentCapability.ARCHITECTURE.value,
    AgentCapability.SECURITY_REVIEW.value,
    AgentCapability.GRC.value,
    AgentCapability.TESTING.value,
    AgentCapability.DELIVERY.value,
]


def test_an_unscoped_goal_runs_the_whole_pipeline() -> None:
    plan = OrganizationPlanner().plan("do the needful")
    assert [step.tool for step in plan.steps] == _PIPELINE_TOOLS


def test_a_pure_compliance_goal_skips_engineering_stages() -> None:
    plan = OrganizationPlanner().plan("Draft a GDPR data-retention policy")
    tools = [step.tool for step in plan.steps]
    # CEO leads, GRC maps, DevTeam closes; CTO/CISO/QA are skipped (no build, no security signal).
    assert tools == [
        AgentCapability.STRATEGY.value,
        AgentCapability.GRC.value,
        AgentCapability.DELIVERY.value,
    ]


def test_a_build_goal_pulls_in_security_review_and_qa() -> None:
    plan = OrganizationPlanner().plan("Implement a new API endpoint for exports")
    tools = [step.tool for step in plan.steps]
    # Anything built is reviewed by the CISO and validated by QA — even without those keywords.
    assert AgentCapability.ARCHITECTURE.value in tools
    assert AgentCapability.SECURITY_REVIEW.value in tools
    assert AgentCapability.TESTING.value in tools
    assert AgentCapability.GRC.value not in tools  # no compliance signal in this goal


def test_the_bookends_are_always_present() -> None:
    plan = OrganizationPlanner().plan("Rotate the signing secret")  # security signal only
    tools = [step.tool for step in plan.steps]
    assert tools[0] == AgentCapability.STRATEGY.value  # CEO always leads
    assert tools[-1] == AgentCapability.DELIVERY.value  # DevTeam always closes


def test_explicit_stages_scope_the_mission_in_pipeline_order() -> None:
    plan = OrganizationPlanner().plan(
        "assess controls",
        stages=[AgentCapability.DELIVERY, AgentCapability.STRATEGY, AgentCapability.GRC],
    )
    # Requested set, re-ordered into the canonical pipeline order (not the argument order).
    assert [step.tool for step in plan.steps] == [
        AgentCapability.STRATEGY.value,
        AgentCapability.GRC.value,
        AgentCapability.DELIVERY.value,
    ]


def test_every_step_carries_the_goal_as_its_instruction() -> None:
    goal = "Map SOC 2 controls for the export service"
    plan = OrganizationPlanner().plan(goal)
    assert all(step.instruction == goal for step in plan.steps)
