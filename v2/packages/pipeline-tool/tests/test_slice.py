"""The vertical slice (ADR 0042, Phase 15 step 3): a Mission runs end to end through the
Pipeline Tool and the real AI Orchestrator, and comes back COMPLETED with a grounded answer.

    Mission → ExecutionPort → RegistryExecutor → Registry → PipelineTool → AI Orchestrator → Answer
"""

import pytest
from mission_engine import MissionStatus, StepRequest, StepResult
from pipeline_tool import RegistryExecutor
from tool_registry import ToolNotFound, ToolRegistry

_GROUNDED_QUERY = "What are the security controls required for personal data?"


def test_mission_completes_end_to_end_with_a_grounded_answer(mission_engine, tenant):
    mission = mission_engine.run_simple("security controls", tenant, _GROUNDED_QUERY)

    assert mission.status is MissionStatus.COMPLETED
    assert mission.execution_profile.value == "simple"
    assert len(mission.step_results) == 1

    step = mission.step_results[0]
    assert step.ok
    assert "[1]" in step.output                 # the real generated answer flowed back
    assert step.source_ids                      # grounding survived the whole slice
    assert step.confidence is not None


def test_engine_events_frame_the_whole_slice(mission_engine, tenant):
    mission = mission_engine.run_simple("q", tenant, _GROUNDED_QUERY)
    names = [e.name for e in mission_engine._events.events]  # RecordingEventBus
    assert names == [
        "mission.created",
        "mission.planned",
        "mission.step_completed",
        "mission.completed",
    ]
    # every event still carries this mission's stamp, across the slice
    assert all(e.mission_id == mission.id for e in mission_engine._events.events)
    assert all(e.tenant_id == "org_acme" for e in mission_engine._events.events)


def test_executor_resolves_the_tool_through_the_registry(registry, tenant):
    executor = RegistryExecutor(registry)
    result = executor.execute(
        StepRequest(
            mission_id="mis_1",
            step_id="stp_1",
            tenant=tenant,
            instruction=_GROUNDED_QUERY,
        )
    )
    assert isinstance(result, StepResult)
    assert result.ok
    assert result.step_id == "stp_1"


def test_executor_fails_clearly_when_the_tool_is_missing(tenant):
    executor = RegistryExecutor(ToolRegistry())  # empty registry
    with pytest.raises(ToolNotFound):
        executor.execute(
            StepRequest(mission_id="m", step_id="s", tenant=tenant, instruction="x")
        )
