"""End to end: a real Mission drives the Framework Library tool through the **real**
`RegistryExecutor`, with the step routing to it by name via `PlanStep.tool` (ADR 0048) — proof that
a real GRC tool plugs into the frozen execution path with no change to the Mission Engine.

    Mission → ExecutionPort → RegistryExecutor → ToolRegistry → ControlLibraryTool → real controls

Uses the in-memory store (no Postgres), so it runs anywhere.
"""

from __future__ import annotations

from event_bus.bus import RecordingEventBus
from framework_library import CONTROL_LIBRARY_TOOL, ControlLibraryTool, FrameworkLibrary
from mission_engine import (
    InMemoryMissionStore,
    MissionEngine,
    MissionStatus,
    Plan,
    PlanStep,
)
from pipeline_contracts import TenantContext
from pipeline_tool import RegistryExecutor
from tool_registry import ToolRegistry


def _engine() -> MissionEngine:
    registry = ToolRegistry()
    registry.register(ControlLibraryTool(FrameworkLibrary.from_bundled()))
    return MissionEngine(
        InMemoryMissionStore(),
        RegistryExecutor(registry, tool_name=CONTROL_LIBRARY_TOOL),
        events=RecordingEventBus(),
    )


def test_a_mission_returns_real_iso_controls_through_the_executor() -> None:
    engine = _engine()
    tenant = TenantContext(tenant_id="org_acme", principal_id="u1")
    mission = engine.run_simple("look up A.8.5", tenant, "A.8.5")

    assert mission.status is MissionStatus.COMPLETED
    step = mission.step_results[0]
    assert step.ok
    assert "Secure authentication" in step.output           # a real control flowed back
    assert step.source_ids == ("iso_27001:A.8.5",)           # provenance survived the whole path


def test_a_composite_plan_routes_each_step_to_the_named_tool() -> None:
    # A multi-step plan (ADR 0048): every step names the control-library tool explicitly and gets
    # its own query answered — the shape a real Risk/Gap capability will use.
    engine = _engine()
    tenant = TenantContext(tenant_id="org_acme", principal_id="u1")
    mission = engine.create("iso gap scan", tenant)
    engine.plan(
        mission,
        Plan(
            steps=(
                PlanStep(description="access", instruction="Access control",
                         tool=CONTROL_LIBRARY_TOOL),
                PlanStep(description="crypto", instruction="A.8.24", tool=CONTROL_LIBRARY_TOOL),
                PlanStep(description="people", instruction="People", tool=CONTROL_LIBRARY_TOOL),
            )
        ),
    )
    engine.execute(mission)

    assert mission.status is MissionStatus.COMPLETED
    outputs = [r.output for r in mission.step_results]
    assert "A.5.15 Access control" in outputs[0]
    assert "A.8.24 Use of cryptography" in outputs[1]
    assert mission.step_results[2].source_ids == tuple(f"iso_27001:A.6.{n}" for n in range(1, 9))
