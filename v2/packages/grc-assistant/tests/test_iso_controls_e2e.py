"""The ISO Controls capability, end to end through the **real** Framework Library tool and the
**real** RegistryExecutor — no database, no LLM. This proves a real GRC capability's plan routes its
step (by `PlanStep.tool`, ADR 0048) to the registered control-library tool and returns real ISO
27001 controls, and that the composition root assembles both standard tools.

    build_iso_controls_plan → Mission → RegistryExecutor → framework_control_library → real controls
"""

from __future__ import annotations

from assistant_runtime.builtin.iso_controls import (
    CONTROL_LIBRARY_TOOL,
    build_iso_controls_plan,
)
from event_bus.bus import RecordingEventBus
from framework_library import CONTROL_LIBRARY_TOOL as FRAMEWORK_TOOL_NAME
from grc_assistant import build_grc_tool_registry
from knowledge_runtime import TenantKnowledgeBase
from mission_engine import InMemoryMissionStore, MissionEngine, MissionStatus
from pipeline_contracts import TenantContext, UserRequest
from pipeline_tool import RUN_PIPELINE_TOOL, RegistryExecutor


class _FakeOrchestrator:
    """Satisfies `PipelineRunner` so the registry can hold a Pipeline Tool; never invoked here."""

    def run(self, request: UserRequest, *, mission_id: str, trace_id: str | None = None):
        raise AssertionError("the ISO capability must not touch the pipeline")


def _empty_provider():
    """A keyword provider over an empty knowledge base — the ISO capability never searches."""
    return TenantKnowledgeBase().keyword_provider()


def _tenant() -> TenantContext:
    return TenantContext(tenant_id="org_acme", principal_id="u1")


def test_capability_tool_name_matches_the_registered_tool() -> None:
    # Drift guard: the capability names the tool by string; it must equal the tool's real name.
    assert CONTROL_LIBRARY_TOOL == FRAMEWORK_TOOL_NAME


def test_the_composition_root_registers_the_standard_tools(generation_provider) -> None:
    from llm_tools import GENERATE_TEXT_TOOL
    from search_tools import LOCAL_SEARCH_TOOL

    registry = build_grc_tool_registry(_FakeOrchestrator(), generation_provider, _empty_provider())
    assert registry.get(RUN_PIPELINE_TOOL) is not None
    assert registry.get(CONTROL_LIBRARY_TOOL) is not None
    assert registry.get(GENERATE_TEXT_TOOL) is not None
    assert registry.get(LOCAL_SEARCH_TOOL) is not None


def test_iso_capability_returns_real_controls_through_the_executor(generation_provider) -> None:
    registry = build_grc_tool_registry(_FakeOrchestrator(), generation_provider, _empty_provider())
    engine = MissionEngine(
        InMemoryMissionStore(),
        RegistryExecutor(registry, tool_name=RUN_PIPELINE_TOOL),  # default; ISO step overrides it
        events=RecordingEventBus(),
    )
    tenant = _tenant()
    goal, plan = build_iso_controls_plan({"request": "A.8.5"}, tenant)

    mission = engine.create(goal, tenant)
    engine.plan(mission, plan)
    engine.execute(mission)

    assert mission.status is MissionStatus.COMPLETED
    step = mission.step_results[0]
    assert "A.8.5 Secure authentication" in step.output       # a real ISO control, not an echo
    assert step.source_ids == ("iso_27001:A.8.5",)            # provenance survived the whole path


def test_iso_capability_lists_a_theme(generation_provider) -> None:
    registry = build_grc_tool_registry(_FakeOrchestrator(), generation_provider, _empty_provider())
    engine = MissionEngine(
        InMemoryMissionStore(), RegistryExecutor(registry), events=RecordingEventBus()
    )
    tenant = _tenant()
    goal, plan = build_iso_controls_plan({"request": "People"}, tenant)
    mission = engine.create(goal, tenant)
    engine.plan(mission, plan)
    engine.execute(mission)

    assert mission.status is MissionStatus.COMPLETED
    assert mission.step_results[0].source_ids == tuple(f"iso_27001:A.6.{n}" for n in range(1, 9))
