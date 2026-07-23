"""ADR 0047 — the Risk Assessment capability (MVP): the first *composite* built-in. Proves a
multi-step mission runs through the Assistant, uses **domain** step names, and — the load-bearing
ruling — that the Capability is **detection-agnostic** (selected by intent id, carrying no keyword).
No real evaluation, no tools, no gate.
"""

from __future__ import annotations

from dataclasses import fields

from assistant_runtime import (
    RISK_ASSESSMENT_CAPABILITY,
    RISK_ASSESSMENT_MISSION_TYPE,
    AssistantRuntime,
    CapabilityIntent,
    build_assistant,
)
from assistant_runtime.builtin import (
    build_risk_assessment_plan,
    default_capability_catalog,
    default_mission_catalog,
)
from mission_engine import ExecutionProfile, MissionStatus
from pipeline_contracts import TenantContext

from tests.conftest import SpyMissionDriver


# ── the capability + its composite mission (domain step names) ────────────────
def test_capability_resolves_to_the_risk_assessment_mission_type() -> None:
    assert RISK_ASSESSMENT_CAPABILITY.id == "risk_assessment"
    assert RISK_ASSESSMENT_CAPABILITY.name == "Risk Assessment"
    assert RISK_ASSESSMENT_CAPABILITY.resolver == RISK_ASSESSMENT_MISSION_TYPE.id


def test_plan_is_composite_with_domain_step_names(tenant: TenantContext) -> None:
    goal, plan = build_risk_assessment_plan({"request": "vendor X"}, tenant)
    assert "vendor X" in goal
    # domain step names (ADR 0047) — stable even if the implementation changes later
    names = [s.description for s in plan.steps]
    assert names == ["Collect relevant context", "Assess the risk", "Write the risk report"]
    assert plan.execution_profile is ExecutionProfile.COMPOSITE
    assert not any(s.consequential for s in plan.steps)  # no human gate


def test_it_gathers_then_synthesises_and_chains(tenant: TenantContext) -> None:
    from assistant_runtime.builtin.risk_assessment import GENERATE_TEXT_TOOL, LOCAL_SEARCH_TOOL

    _, plan = build_risk_assessment_plan({"request": "vendor X"}, tenant)
    # a tenant-scoped search gather (local_search, customer data) then two syntheses (ADR 0051)
    assert [s.tool for s in plan.steps] == [
        LOCAL_SEARCH_TOOL, GENERATE_TEXT_TOOL, GENERATE_TEXT_TOOL
    ]
    assert all("vendor X" in s.instruction for s in plan.steps)


# ── the Capability knows nothing about how it is detected (ADR 0047 ruling) ────
def test_capability_carries_no_detection_field() -> None:
    """Structural guarantee: a Capability has only id/name/description/input_schema/resolver — no
    keyword, no recognizer type. Detection lives with the recognizer, never on the Capability."""
    field_names = {f.name for f in fields(RISK_ASSESSMENT_CAPABILITY)}
    assert field_names == {"id", "name", "description", "input_schema", "resolver"}


class _FixedIntentRecognizer:
    """A recognizer that is NOT keyword-based — it emits a fixed capability intent. Used to prove a
    Capability is selected by **intent id**, so swapping the recognizer changes no Capability."""

    def __init__(self, capability_id: str) -> None:
        self._id = capability_id

    def recognize(self, request: str, tenant: TenantContext) -> CapabilityIntent:
        return CapabilityIntent(capability_id=self._id, confidence=1.0, inputs={"request": request})


def test_selected_by_intent_id_regardless_of_recognizer(
    spy_driver: SpyMissionDriver, tenant: TenantContext
) -> None:
    """With a completely different (non-keyword) recognizer, the same capability is chosen purely by
    intent id — the recognizer changed, the Capability did not."""
    runtime = AssistantRuntime(
        missions=spy_driver,
        capabilities=default_capability_catalog(),
        mission_catalog=default_mission_catalog(),
        intent=_FixedIntentRecognizer("risk_assessment"),
        fallback_capability_id="ask",
    )
    assert runtime.handle("literally any text", tenant).capability_id == "risk_assessment"


# ── the full loop, in-memory ──────────────────────────────────────────────────
def test_full_loop_runs_a_composite_risk_mission(
    spy_driver: SpyMissionDriver, tenant: TenantContext
) -> None:
    assistant = build_assistant(spy_driver)  # reference recognizer maps "risk" → risk_assessment

    response = assistant.handle("assess the risk of vendor X", tenant)

    assert response.capability_id == "risk_assessment"
    assert response.status is MissionStatus.COMPLETED
    assert len(response.mission.step_results) == 3  # a real multi-step mission ran
    assert spy_driver.calls == 1  # still exactly one Core call


def test_a_request_without_the_risk_intent_falls_back_to_ask(
    spy_driver: SpyMissionDriver, tenant: TenantContext
) -> None:
    assistant = build_assistant(spy_driver)
    assert assistant.handle("what is MFA?", tenant).capability_id == "ask"
