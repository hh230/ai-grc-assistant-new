"""The ISO Controls capability (the first backed by a real tool): its plan names the Framework
Library tool via `PlanStep.tool` (ADR 0048), and it is reachable through the default assembly."""

from __future__ import annotations

from assistant_runtime.builtin import (
    ISO_CONTROLS_CAPABILITY,
    ISO_CONTROLS_MISSION_ID,
    build_assistant,
    build_iso_controls_plan,
)
from assistant_runtime.builtin.iso_controls import CONTROL_LIBRARY_TOOL
from pipeline_contracts import TenantContext


def _tenant() -> TenantContext:
    return TenantContext(tenant_id="org_acme", principal_id="u1")


def test_capability_resolves_to_the_iso_mission_type() -> None:
    assert ISO_CONTROLS_CAPABILITY.id == "iso_controls"
    assert ISO_CONTROLS_CAPABILITY.resolver == ISO_CONTROLS_MISSION_ID


def test_plan_is_one_read_only_step_that_names_the_control_library_tool() -> None:
    goal, plan = build_iso_controls_plan({"request": "Technological"}, _tenant())
    assert goal == "ISO 27001 controls: Technological"
    assert len(plan.steps) == 1
    step = plan.steps[0]
    assert step.tool == CONTROL_LIBRARY_TOOL      # routes to the real Framework Library tool
    assert step.instruction == "Technological"    # the scope passes through as the tool's query
    assert not step.consequential                 # read-only ⇒ no human gate
    assert plan.execution_profile.value == "simple"


def test_empty_scope_becomes_the_whole_catalog_query() -> None:
    goal, plan = build_iso_controls_plan({}, _tenant())
    assert goal == "ISO 27001 controls: all controls"
    assert plan.steps[0].instruction == ""        # empty ⇒ the tool lists the whole catalog


def test_reference_recognizer_routes_iso_requests_to_the_capability(spy_driver) -> None:
    assistant = build_assistant(spy_driver)       # keyword "iso" → iso_controls
    response = assistant.handle("show me the iso controls for access", _tenant())
    assert response.capability_id == "iso_controls"
