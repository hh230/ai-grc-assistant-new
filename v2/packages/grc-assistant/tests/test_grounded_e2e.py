"""Step A, end to end on real PostgreSQL: the Assistant, wired over the **real** Execution Platform,
answers a Simple Question with a **grounded answer from the pipeline** instead of an echo.

    User → AssistantRuntime → Capability (ask) → Mission → MissionRuntime
         → RegistryExecutor → Tool Registry → PipelineTool → AI Orchestrator → grounded answer

The pipeline runs for real behind fake search/generation providers (see conftest); nothing here
touches a network or an SDK. DB-gated; auto-skips without a database.
"""

from __future__ import annotations

from assistant_runtime import build_assistant
from mission_engine import MissionStatus
from mission_integration import MissionRuntime
from pipeline_contracts import TenantContext


def test_simple_question_returns_a_grounded_answer_not_echo(
    tool_backed_runtime: MissionRuntime, tenant: TenantContext
) -> None:
    assistant = build_assistant(tool_backed_runtime)

    response = assistant.handle("what does the PDPL say about consent?", tenant)

    assert response.capability_id == "ask"
    assert response.status is MissionStatus.COMPLETED

    step = response.mission.step_results[0]
    assert step.output == "Grounded answer [1]."  # produced by the pipeline, via the tool
    assert not step.output.startswith("echo:")  # proof: the REAL executor ran, not EchoExecutor
    # (grounding/source_ids depend on the pipeline's own retrieval decision for this query — a
    # pipeline-internal concern, not the Step-A wiring proof, so we don't assert on it here.)

    # durably persisted through the real MissionRuntime
    reloaded = tool_backed_runtime.load(response.mission_id, tenant)
    assert reloaded is not None
    assert reloaded.status is MissionStatus.COMPLETED
    assert reloaded.step_results[0].output == "Grounded answer [1]."
