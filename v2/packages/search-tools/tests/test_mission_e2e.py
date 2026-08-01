"""End to end: a Mission runs a real search through the real `RegistryExecutor`, the step routing to
`local_search` via `PlanStep.tool` (ADR 0048). Also proves the hybrid tool fuses both modalities.
In-memory store + providers, so it runs anywhere."""

from __future__ import annotations

from event_bus.bus import RecordingEventBus
from mission_engine import InMemoryMissionStore, MissionEngine, MissionStatus
from pipeline_contracts import TenantContext
from pipeline_tool import RegistryExecutor
from search_tools import (
    HYBRID_SEARCH_TOOL,
    LOCAL_SEARCH_TOOL,
    build_hybrid_search_tool,
    build_local_search_tool,
)
from tool_registry import PAYLOAD_INSTRUCTION, ToolRegistry, ToolStepResult


def test_a_mission_runs_a_real_search_through_the_executor(keyword_provider) -> None:
    registry = ToolRegistry()
    registry.register(build_local_search_tool(keyword_provider))
    engine = MissionEngine(
        InMemoryMissionStore(),
        RegistryExecutor(registry, tool_name=LOCAL_SEARCH_TOOL),
        events=RecordingEventBus(),
    )
    tenant = TenantContext(tenant_id="org_acme", principal_id="u1")

    mission = engine.run_simple("find incident procedures", tenant, "incident management")

    assert mission.status is MissionStatus.COMPLETED
    step = mission.step_results[0]
    assert step.ok
    assert "c3" in step.source_ids          # the incident-management chunk, cited, end to end
    assert "incident" in step.output


def test_hybrid_tool_fuses_both_modalities(vector_provider, keyword_provider, tenant) -> None:
    tool = build_hybrid_search_tool(vector_provider, keyword_provider)
    assert tool.spec.name == HYBRID_SEARCH_TOOL
    result = ToolStepResult.from_payload(
        tool.invoke({PAYLOAD_INSTRUCTION: "access control"}, tenant)
    )
    assert result.ok
    assert "c1" in result.source_ids        # the keyword match survives fusion + ranking + citation
