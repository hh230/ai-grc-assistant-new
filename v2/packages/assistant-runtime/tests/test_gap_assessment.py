"""The Gap Assessment capability: framework controls + customer evidence → gap. A real composite
routing controls (framework), evidence (local_search over customer data), and a gap synthesis
(generate_text), reachable through the default assembly."""

from __future__ import annotations

from assistant_runtime.builtin import (
    GAP_ASSESSMENT_CAPABILITY,
    GAP_ASSESSMENT_MISSION_ID,
    build_assistant,
    build_gap_assessment_plan,
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


def test_capability_resolves_to_the_gap_mission_type() -> None:
    assert GAP_ASSESSMENT_CAPABILITY.id == "gap_assessment"
    assert GAP_ASSESSMENT_CAPABILITY.resolver == GAP_ASSESSMENT_MISSION_ID


def test_plan_puts_required_controls_next_to_customer_evidence_then_computes_gap() -> None:
    goal, plan = build_gap_assessment_plan({"request": "Technological"}, _tenant())
    assert goal == "gap assessment: Technological"
    assert plan.execution_profile is ExecutionProfile.COMPOSITE
    assert [s.description for s in plan.steps] == [
        "Identify applicable controls", "Gather supporting evidence", "Compute coverage and gaps"
    ]
    # required controls (framework) + the customer's evidence (search) → gap synthesis (ADR 0051)
    assert [s.tool for s in plan.steps] == [
        CONTROL_LIBRARY_TOOL, LOCAL_SEARCH_TOOL, GENERATE_TEXT_TOOL
    ]
    assert "Technological" in plan.steps[2].instruction
    assert not any(s.consequential for s in plan.steps)


def test_reference_recognizer_routes_gap_requests_to_the_capability(spy_driver) -> None:
    assistant = build_assistant(spy_driver)                 # keyword "gap" → gap_assessment
    response = assistant.handle("run a gap assessment for our access controls", _tenant())
    assert response.capability_id == "gap_assessment"
