"""The plan (ADR 0042 §11, §12.6): execution_profile is derived, plans are versioned and
immutable, and an empty plan is rejected."""

import pytest
from mission_engine.errors import PlanError
from mission_engine.plan import ExecutionProfile, Plan, PlanStep, single_step_plan


def test_single_read_only_step_is_simple():
    plan = single_step_plan("what does NCA ECC say about MFA?")
    assert plan.execution_profile is ExecutionProfile.SIMPLE
    assert len(plan.steps) == 1
    assert plan.version == 1
    assert not plan.has_gate


def test_many_steps_is_composite():
    plan = Plan(steps=(PlanStep(instruction="a"), PlanStep(instruction="b")))
    assert plan.execution_profile is ExecutionProfile.COMPOSITE


def test_single_consequential_step_is_composite_and_gated():
    plan = Plan(steps=(PlanStep(instruction="write policy", consequential=True),))
    assert plan.execution_profile is ExecutionProfile.COMPOSITE
    assert plan.has_gate


def test_empty_plan_is_rejected():
    with pytest.raises(PlanError):
        Plan(steps=())


def test_next_version_increments_and_leaves_the_original_untouched():
    v1 = single_step_plan("x")
    v2 = v1.next_version((PlanStep(instruction="x"), PlanStep(instruction="y")))
    assert v2.version == 2
    assert v1.version == 1  # the accepted plan is never mutated (§12.6)
    assert v2.execution_profile is ExecutionProfile.COMPOSITE


def test_steps_get_stable_prefixed_ids():
    step = PlanStep(instruction="x")
    assert step.id.startswith("stp_")


def test_to_dict_exposes_the_derived_profile():
    data = single_step_plan("x").to_dict()
    assert data["execution_profile"] == "simple"
    assert data["version"] == 1
