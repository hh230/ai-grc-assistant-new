"""The shared mission-step tool contract (the review's finding): it is explicit and single-
sourced, and it is what makes a *new* tool executable with no change to RegistryExecutor."""

from dataclasses import dataclass

from mission_engine import MissionStatus, StepRequest
from pipeline_contracts import TenantContext
from pipeline_tool import RegistryExecutor, ToolStepResult
from tool_registry import SideEffectProfile, ToolRegistry, ToolSpec


def test_tool_step_result_round_trips_through_the_dict_boundary():
    original = ToolStepResult(
        ok=True, output="42 rows", source_ids=("q1",), confidence=0.9, warnings=("truncated",)
    )
    assert ToolStepResult.from_payload(original.as_payload()) == original


def test_from_payload_degrades_safely_on_a_partial_or_ill_typed_result():
    # A tool that returns junk must not crash the executor — every field coerces.
    result = ToolStepResult.from_payload({"output": 123, "source_ids": ["a", 7, "b"]})
    assert result.ok is False          # missing → not ok
    assert result.output == ""         # non-str → empty
    assert result.source_ids == ("a", "b")  # non-str items dropped
    assert result.confidence is None


# --- the extensibility proof (review criteria 2 & 5) ------------------------------------

@dataclass(frozen=True)
class _RiskTool:
    """A wholly different Tool — no pipeline, no LLM — that simply speaks the contract. It
    stands in for a future SQL / Document / Risk / Workflow tool."""

    spec: ToolSpec

    def invoke(self, payload: dict[str, object], tenant: TenantContext) -> dict[str, object]:
        return ToolStepResult(
            ok=True,
            output=f"risk assessed for: {payload['instruction']}",
            confidence=0.75,
            source_ids=("risk-model-v3",),
        ).as_payload()


def test_a_new_conforming_tool_runs_through_the_unchanged_executor():
    registry = ToolRegistry()
    registry.register(
        _RiskTool(ToolSpec(name="assess_risk", side_effect=SideEffectProfile.READ_ONLY))
    )
    # Same RegistryExecutor class, just pointed at the new tool — no code change to it.
    executor = RegistryExecutor(registry, tool_name="assess_risk")

    result = executor.execute(
        StepRequest(
            mission_id="mis_1",
            step_id="stp_1",
            tenant=TenantContext(tenant_id="org_acme", principal_id="u1"),
            instruction="vendor onboarding",
        )
    )
    assert result.ok
    assert result.output == "risk assessed for: vendor onboarding"
    assert result.confidence == 0.75
    assert result.source_ids == ("risk-model-v3",)


def test_a_new_tool_completes_a_real_mission_end_to_end():
    # And the same new tool drives a full Mission through the frozen Mission Engine — proof the
    # whole execution path is tool-generic, not pipeline-specific.
    from event_bus.bus import RecordingEventBus
    from mission_engine import InMemoryMissionStore, MissionEngine

    registry = ToolRegistry()
    registry.register(
        _RiskTool(ToolSpec(name="assess_risk", side_effect=SideEffectProfile.READ_ONLY))
    )
    engine = MissionEngine(
        InMemoryMissionStore(),
        RegistryExecutor(registry, tool_name="assess_risk"),
        events=RecordingEventBus(),
    )
    mission = engine.run_simple(
        "risk", TenantContext(tenant_id="org_acme", principal_id="u1"), "vendor onboarding"
    )
    assert mission.status is MissionStatus.COMPLETED
    assert mission.step_results[0].output.startswith("risk assessed for:")
