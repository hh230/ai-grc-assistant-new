"""Slice 3 of Human Approval (ADR 0044) — the engine half of resume orchestration: the engine
attaches an approval request at the pause, emits the decision events on `approve`/`reject`, and
`resume` continues an approved mission from the pause point through to completion.

Engine-level (in-memory store + recording bus); the cross-process reload/re-enter orchestration is
exercised end-to-end against real PostgreSQL in the mission-integration suite.
"""

from __future__ import annotations

import pytest
from mission_engine import (
    IllegalTransition,
    Mission,
    MissionEngine,
    MissionStatus,
    Plan,
    PlanStep,
)
from pipeline_contracts import TenantContext


def _names(bus) -> list[str]:
    return [event.name for event in bus.events]


def _pause_at_gate(engine: MissionEngine, tenant: TenantContext) -> Mission:
    """Drive create → plan([A read-only, B consequential]) → execute, pausing at B's gate."""
    mission = engine.create("draft policy", tenant)
    engine.plan(
        mission,
        Plan(
            steps=(
                PlanStep(description="retrieve", instruction="find ECC"),
                PlanStep(description="author", instruction="write", consequential=True),
            )
        ),
    )
    engine.execute(mission)
    return mission


# ── the pause now attaches an approval request (Slice 3 wires what Slice 1 deferred) ──
def test_execute_attaches_an_approval_request_at_the_gate(engine, bus, tenant) -> None:
    mission = _pause_at_gate(engine, tenant)

    assert mission.status is MissionStatus.AWAITING_APPROVAL
    assert len(mission.step_results) == 1  # the read-only step ran; the gate did not
    assert mission.approval is not None
    assert mission.approval.is_pending
    assert mission.has_active_approval
    # `requested_by` is the request ORIGIN, not a human: an engine-raised gate records the system
    # principal (never the mission id, never a subject). The deciding human is on ApprovalDecision.
    assert mission.approval.requested_by == "system"
    assert _names(bus) == [
        "mission.created",
        "mission.planned",
        "mission.step_completed",
        "mission.awaiting_approval",
    ]


# ── approve → RESUMED + event; resume → continues from the pause point → COMPLETED ──
def test_approve_then_resume_completes_from_the_pause_point(engine, bus, tenant) -> None:
    mission = _pause_at_gate(engine, tenant)

    engine.approve(mission, tenant, comment="ok")
    assert mission.status is MissionStatus.RESUMED
    assert "mission.approved" in _names(bus)

    engine.resume(mission)
    assert mission.status is MissionStatus.COMPLETED
    assert len(mission.step_results) == 2  # the approved gated step ran on resume
    # the full audit narrative, in order
    assert _names(bus) == [
        "mission.created",
        "mission.planned",
        "mission.step_completed",
        "mission.awaiting_approval",
        "mission.approved",
        "mission.resumed",
        "mission.step_completed",
        "mission.completed",
    ]


def test_resume_runs_a_single_gated_step(engine, bus, tenant) -> None:
    """A plan whose only step is consequential: execute pauses immediately (nothing ran), and after
    approval, resume runs exactly that step to completion."""
    mission = engine.create("g", tenant)
    engine.plan(mission, Plan(steps=(PlanStep(instruction="write", consequential=True),)))
    engine.execute(mission)
    assert mission.status is MissionStatus.AWAITING_APPROVAL
    assert mission.step_results == []

    engine.approve(mission, tenant)
    engine.resume(mission)
    assert mission.status is MissionStatus.COMPLETED
    assert len(mission.step_results) == 1


# ── reject → CANCELLED + event ────────────────────────────────────────────────
def test_reject_cancels_the_mission_and_emits_the_event(engine, bus, tenant) -> None:
    mission = _pause_at_gate(engine, tenant)

    engine.reject(mission, tenant, comment="insufficient evidence")
    assert mission.status is MissionStatus.CANCELLED
    assert mission.is_terminal
    assert "mission.rejected" in _names(bus)


# ── guards ────────────────────────────────────────────────────────────────────
def test_resume_requires_a_resumed_mission(engine, tenant) -> None:
    mission = _pause_at_gate(engine, tenant)  # AWAITING_APPROVAL, not RESUMED
    with pytest.raises(IllegalTransition):
        engine.resume(mission)


def test_a_second_consequential_step_pauses_again_after_resume(engine, bus, tenant) -> None:
    """A single approval authorizes a single step: a plan [A, B(gate), C(gate)] runs A, pauses at B,
    and after approve+resume runs B then pauses again at C — the approval never covers the rest."""
    mission = engine.create("g", tenant)
    engine.plan(
        mission,
        Plan(
            steps=(
                PlanStep(instruction="a"),
                PlanStep(instruction="b", consequential=True),
                PlanStep(instruction="c", consequential=True),
            )
        ),
    )
    engine.execute(mission)  # runs A, pauses at B
    engine.approve(mission, tenant)
    engine.resume(mission)  # runs B, pauses at C

    assert mission.status is MissionStatus.AWAITING_APPROVAL
    assert len(mission.step_results) == 2  # A and B ran; C is gated
    assert _names(bus).count("mission.awaiting_approval") == 2
