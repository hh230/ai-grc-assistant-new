"""The Vendor Review capability: a real composite routing `identify_supplier_controls` to the
control library and `assess_vendor` to the grounded pipeline (ADR 0048), reachable through the
assembly. Also guards that "risk of vendor X" still routes to Risk Assessment (first-hit-wins)."""

from __future__ import annotations

from assistant_runtime.builtin import (
    VENDOR_REVIEW_CAPABILITY,
    VENDOR_REVIEW_MISSION_ID,
    build_assistant,
    build_vendor_review_plan,
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


def test_capability_resolves_to_the_vendor_review_mission_type() -> None:
    assert VENDOR_REVIEW_CAPABILITY.id == "vendor_review"
    assert VENDOR_REVIEW_CAPABILITY.resolver == VENDOR_REVIEW_MISSION_ID


def test_plan_gathers_then_synthesises_and_chains() -> None:
    goal, plan = build_vendor_review_plan({"request": "Acme Cloud"}, _tenant())
    assert goal == "vendor review: Acme Cloud"
    assert plan.execution_profile is ExecutionProfile.COMPOSITE
    assert [s.description for s in plan.steps] == [
        "Identify supplier controls", "Gather vendor context", "Assess the vendor"
    ]
    # supplier controls + a tenant-scoped search gather then a synthesis (ADR 0051)
    assert [s.tool for s in plan.steps] == [
        CONTROL_LIBRARY_TOOL, LOCAL_SEARCH_TOOL, GENERATE_TEXT_TOOL
    ]
    assert plan.steps[0].instruction == "supplier"          # supplier controls apply to any vendor
    assert "Acme Cloud" in plan.steps[2].instruction
    assert not any(s.consequential for s in plan.steps)


def test_reference_recognizer_routes_vendor_requests_to_the_capability(spy_driver) -> None:
    assistant = build_assistant(spy_driver)                 # keyword "vendor" → vendor_review
    response = assistant.handle("review the vendor Acme Cloud", _tenant())
    assert response.capability_id == "vendor_review"


def test_risk_of_a_vendor_still_routes_to_risk_assessment(spy_driver) -> None:
    # "risk" precedes "vendor" in the keyword map (first hit wins), so a risk request wins.
    assistant = build_assistant(spy_driver)
    response = assistant.handle("assess the risk of vendor Acme", _tenant())
    assert response.capability_id == "risk_assessment"
