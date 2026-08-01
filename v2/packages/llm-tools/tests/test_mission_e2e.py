"""End to end: a Mission generates text through the real `RegistryExecutor`, the step routing to
`generate_text` via `PlanStep.tool` (ADR 0048). In-memory store, so it runs anywhere."""

from __future__ import annotations

from event_bus.bus import RecordingEventBus
from llm_tools import GENERATE_TEXT_TOOL, LLMTool
from mission_engine import InMemoryMissionStore, MissionEngine, MissionStatus
from pipeline_contracts import TenantContext
from pipeline_tool import RegistryExecutor
from tool_registry import ToolRegistry


def test_a_mission_generates_text_through_the_executor(provider) -> None:
    registry = ToolRegistry()
    registry.register(LLMTool(provider))
    engine = MissionEngine(
        InMemoryMissionStore(),
        RegistryExecutor(registry, tool_name=GENERATE_TEXT_TOOL),
        events=RecordingEventBus(),
    )
    tenant = TenantContext(tenant_id="org_acme", principal_id="u1")

    mission = engine.run_simple("draft policy", tenant, "draft an acceptable use policy")

    assert mission.status is MissionStatus.COMPLETED
    step = mission.step_results[0]
    assert step.ok
    assert step.output == "draft: draft an acceptable use policy"


def test_a_mission_fails_safe_when_generation_fails(failing_provider) -> None:
    registry = ToolRegistry()
    registry.register(LLMTool(failing_provider))
    engine = MissionEngine(
        InMemoryMissionStore(),
        RegistryExecutor(registry, tool_name=GENERATE_TEXT_TOOL),
        events=RecordingEventBus(),
    )
    tenant = TenantContext(tenant_id="org_acme", principal_id="u1")

    mission = engine.run_simple("draft", tenant, "draft")
    assert mission.status is MissionStatus.FAILED   # ok=False step → mission fails safe (§7)
