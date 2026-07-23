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


# --- ADR 0048: per-step tool selection --------------------------------------------------

@dataclass(frozen=True)
class _EchoingTool:
    """A trivial tool that echoes which tool ran, so a multi-tool plan can prove each step
    routed to the tool its `PlanStep.tool` named."""

    spec: ToolSpec

    def invoke(self, payload: dict[str, object], tenant: TenantContext) -> dict[str, object]:
        text = f"{self.spec.name}: {payload['instruction']}"
        return ToolStepResult(ok=True, output=text).as_payload()


def _echo(name: str) -> _EchoingTool:
    return _EchoingTool(ToolSpec(name=name, side_effect=SideEffectProfile.READ_ONLY))


def test_request_tool_overrides_the_constructor_default():
    # An explicit request.tool wins over the executor's default tool.
    registry = ToolRegistry()
    registry.register(_echo("tool_a"))
    registry.register(_echo("tool_b"))
    executor = RegistryExecutor(registry, tool_name="tool_a")  # default is tool_a

    result = executor.execute(
        StepRequest(
            mission_id="m",
            step_id="s",
            tenant=TenantContext(tenant_id="org_acme", principal_id="u1"),
            instruction="x",
            tool="tool_b",  # ADR 0048: name a different tool per step
        )
    )
    assert result.output == "tool_b: x"  # honoured the per-step tool, not the default


def test_empty_request_tool_falls_back_to_the_default():
    # Backward compatibility: a step with no tool (every pre-ADR-0048 plan) uses the default.
    registry = ToolRegistry()
    registry.register(_echo("tool_a"))
    executor = RegistryExecutor(registry, tool_name="tool_a")

    result = executor.execute(
        StepRequest(
            mission_id="m",
            step_id="s",
            tenant=TenantContext(tenant_id="org_acme", principal_id="u1"),
            instruction="x",  # tool="" by default
        )
    )
    assert result.output == "tool_a: x"


# --- ADR 0051: inter-step context ------------------------------------------------------

@dataclass
class _CapturingTool:
    """Records the payload it was invoked with, so we can assert the executor rendered the prior
    step results into it."""

    spec: ToolSpec
    seen: dict[str, object] | None = None

    def invoke(self, payload: dict[str, object], tenant: TenantContext) -> dict[str, object]:
        self.seen = dict(payload)
        return ToolStepResult(ok=True, output="ok").as_payload()


def test_executor_renders_prior_results_into_the_payload():
    from mission_engine import StepResult
    from pipeline_tool.contract import PAYLOAD_PRIOR_CONTEXT

    tool = _CapturingTool(ToolSpec(name="cap", side_effect=SideEffectProfile.READ_ONLY))
    registry = ToolRegistry()
    registry.register(tool)
    executor = RegistryExecutor(registry, tool_name="cap")

    executor.execute(
        StepRequest(
            mission_id="m",
            step_id="s2",
            tenant=TenantContext(tenant_id="org_acme", principal_id="u1"),
            instruction="synthesize",
            prior_results=(
                StepResult(step_id="s1", ok=True, output="the risk is HIGH"),
                StepResult(step_id="s1b", ok=True, output="controls: A.5.15"),
            ),
        )
    )
    assert tool.seen is not None
    prior = str(tool.seen[PAYLOAD_PRIOR_CONTEXT])
    assert "the risk is HIGH" in prior and "controls: A.5.15" in prior
    assert "[Step 1]" in prior and "[Step 2]" in prior


def test_prior_context_is_empty_for_a_first_step():
    from pipeline_tool.contract import PAYLOAD_PRIOR_CONTEXT

    tool = _CapturingTool(ToolSpec(name="cap", side_effect=SideEffectProfile.READ_ONLY))
    registry = ToolRegistry()
    registry.register(tool)
    RegistryExecutor(registry, tool_name="cap").execute(
        StepRequest(mission_id="m", step_id="s1",
                    tenant=TenantContext(tenant_id="org_acme", principal_id="u1"),
                    instruction="first")
    )
    assert tool.seen is not None
    assert tool.seen[PAYLOAD_PRIOR_CONTEXT] == ""   # no prior steps → inert key


def test_multi_tool_mission_routes_each_step_to_its_own_tool():
    # The payoff (ADR 0048): a composite plan whose steps name different tools runs each step
    # on the tool it named — end to end through the frozen Mission Engine.
    from event_bus.bus import RecordingEventBus
    from mission_engine import InMemoryMissionStore, MissionEngine, Plan, PlanStep

    registry = ToolRegistry()
    for name in ("collect", "assess", "report"):
        registry.register(_echo(name))
    engine = MissionEngine(
        InMemoryMissionStore(),
        RegistryExecutor(registry, tool_name="collect"),  # default used only if a step omits tool
        events=RecordingEventBus(),
    )
    tenant = TenantContext(tenant_id="org_acme", principal_id="u1")
    mission = engine.create("risk assessment: acme", tenant)
    engine.plan(
        mission,
        Plan(
            steps=(
                PlanStep(description="collect_context", instruction="gather", tool="collect"),
                PlanStep(description="assess_risk", instruction="score", tool="assess"),
                PlanStep(description="generate_report", instruction="write", tool="report"),
            )
        ),
    )
    engine.execute(mission)

    assert mission.status is MissionStatus.COMPLETED
    assert [r.output for r in mission.step_results] == [
        "collect: gather",
        "assess: score",
        "report: write",
    ]
