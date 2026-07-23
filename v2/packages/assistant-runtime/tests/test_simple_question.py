"""Slice 3 — the first built-in capability (AI GRC Assistant → Simple Question). Proves the whole
loop `request → AssistantRuntime → Capability → Mission → MissionRuntime → Response` in-memory (the
DB-backed proof is in test_e2e.py). No tools, no gate, no multi-Mission — a single read-only step.
"""

from __future__ import annotations

from assistant_runtime import (
    AI_GRC_ASSISTANT_CAPABILITY,
    SIMPLE_QUESTION_MISSION_TYPE,
    build_assistant,
)
from assistant_runtime.builtin import (
    build_simple_question_plan,
    default_capability_catalog,
    default_mission_catalog,
)
from mission_engine import ExecutionProfile, MissionStatus
from pipeline_contracts import TenantContext

from tests.conftest import SpyMissionDriver


# ── the capability + its mission type ─────────────────────────────────────────
def test_capability_resolves_to_the_simple_question_mission_type() -> None:
    assert AI_GRC_ASSISTANT_CAPABILITY.id == "ask"
    assert AI_GRC_ASSISTANT_CAPABILITY.name == "AI GRC Assistant"
    assert AI_GRC_ASSISTANT_CAPABILITY.resolver == SIMPLE_QUESTION_MISSION_TYPE.id
    # both live in the default catalogs the assembler wires
    assert "ask" in default_capability_catalog()
    assert "simple_question" in default_mission_catalog()


def test_plan_factory_builds_one_read_only_step(tenant: TenantContext) -> None:
    goal, plan = build_simple_question_plan({"request": "what is MFA?"}, tenant)
    assert goal == "what is MFA?"
    assert len(plan.steps) == 1
    assert plan.execution_profile is ExecutionProfile.SIMPLE  # simple mission
    assert not plan.steps[0].consequential  # no human gate


def test_empty_request_degrades_gracefully(tenant: TenantContext) -> None:
    goal, plan = build_simple_question_plan({}, tenant)
    assert goal == "answer the question"  # never an empty plan
    assert len(plan.steps) == 1


# ── the full loop, in-memory ──────────────────────────────────────────────────
def test_full_loop_answers_a_request_as_a_simple_question(
    spy_driver: SpyMissionDriver, tenant: TenantContext
) -> None:
    assistant = build_assistant(spy_driver)

    response = assistant.handle("what does NCA ECC say about MFA?", tenant)

    assert response.capability_id == "ask"  # User → Capability
    assert response.status is MissionStatus.COMPLETED  # → Mission → MissionRuntime → completed
    assert len(response.mission.step_results) == 1  # a single read-only step ran
    assert response.mission.step_results[0].output.startswith("echo:")  # went through the Core
    assert spy_driver.calls == 1  # exactly one MissionRuntime call


def test_a_request_matching_no_capability_falls_back_to_ask(
    spy_driver: SpyMissionDriver, tenant: TenantContext
) -> None:
    """Any request whose intent matches no registered capability keyword routes to `ask` — e.g. a
    greeting, or "summarize the meeting notes". Matched capabilities have their own tests."""
    assistant = build_assistant(spy_driver)
    assert assistant.handle("hello there", tenant).capability_id == "ask"
    assert assistant.handle("summarize the meeting notes", tenant).capability_id == "ask"
