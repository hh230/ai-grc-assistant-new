"""The Policy Generator capability: a real composite that routes `identify_controls` to the control
library and `draft_policy` to the grounded pipeline (ADR 0048), reachable through the assembly."""

from __future__ import annotations

from assistant_runtime.builtin import (
    POLICY_GENERATOR_CAPABILITY,
    POLICY_GENERATOR_MISSION_ID,
    build_assistant,
    build_policy_generator_plan,
)
from assistant_runtime.builtin.tool_names import (
    CONTROL_LIBRARY_TOOL,
    GENERATE_TEXT_TOOL,
    LOCAL_SEARCH_TOOL,
)
from mission_engine import ExecutionProfile
from pipeline_contracts import TenantContext


def _tenant() -> TenantContext:
    return TenantContext(tenant_id="org_acme", principal_id="u1")


def test_capability_resolves_to_the_policy_mission_type() -> None:
    assert POLICY_GENERATOR_CAPABILITY.id == "policy_generator"
    assert POLICY_GENERATOR_CAPABILITY.resolver == POLICY_GENERATOR_MISSION_ID


def test_plan_gathers_then_synthesises_and_chains() -> None:
    goal, plan = build_policy_generator_plan({"request": "acceptable use"}, _tenant())
    assert goal == "policy generation: acceptable use"
    assert plan.execution_profile is ExecutionProfile.COMPOSITE
    assert [s.description for s in plan.steps] == [
        "Identify relevant controls", "Gather policy guidance", "Draft the policy"
    ]
    # controls lookup + a tenant-scoped search gather then a synthesis on them (ADR 0051)
    assert [s.tool for s in plan.steps] == [
        CONTROL_LIBRARY_TOOL, LOCAL_SEARCH_TOOL, GENERATE_TEXT_TOOL
    ]
    assert "acceptable use" in plan.steps[2].instruction
    assert not any(s.consequential for s in plan.steps)     # no human gate


def test_reference_recognizer_routes_policy_requests_to_the_capability(spy_driver) -> None:
    assistant = build_assistant(spy_driver)                 # keyword "policy" → policy_generator
    response = assistant.handle("draft an access control policy for us", _tenant())
    assert response.capability_id == "policy_generator"
