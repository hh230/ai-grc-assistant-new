"""ADR 0044 Slice 3 — Human Approval **resume orchestration**, end to end against real PostgreSQL.

This is the first time the Integration Runtime enters ADR 0044. It drives the full gate lifecycle
across process-like boundaries — each step its own transaction — and proves the Outbox and Audit
keep working through it:

    execute → AWAITING_APPROVAL  →  approve → RESUMED  →  resume_if_approved → continue → COMPLETED

`resume_if_approved` is the orchestration seam: it **detects** the approval (persisted status
`RESUMED`), **reloads** the mission from the store, **re-enters** it into the Mission Engine, and
**continues** execution from the pause point. DB-gated; auto-skips without a database.
"""

from __future__ import annotations

import psycopg
from mission_engine import Mission, MissionStatus, Plan, PlanStep
from mission_integration import MissionRuntime
from pipeline_contracts import TenantContext

_GATED_PLAN = Plan(
    steps=(
        PlanStep(description="retrieve", instruction="find ECC MFA"),
        PlanStep(description="author", instruction="write policy", consequential=True),
    )
)


def _outbox_names(conn: psycopg.Connection, table: str, mission_id: str) -> list[str]:
    rows = conn.execute(
        f"SELECT event_name FROM {table} WHERE mission_id = %s ORDER BY id", (mission_id,)
    ).fetchall()
    return [r[0] for r in rows]


def _pause_at_gate(runtime: MissionRuntime, tenant: TenantContext) -> Mission:
    """create → plan([read-only, consequential]) → execute, each its own transaction; pauses at the
    gate with a persisted pending ApprovalRequest."""
    mission = runtime.run_transition(lambda e: e.create("gap analysis w/ approval", tenant))
    runtime.run_transition(lambda e: e.plan(mission, _GATED_PLAN))
    return runtime.run_transition(lambda e: e.execute(mission))


# ── the full flow: pause → approve → resume → complete ────────────────────────
def test_pause_approve_resume_completes_with_outbox_and_audit(
    runtime: MissionRuntime,
    observer: psycopg.Connection,
    tables: tuple[str, str],
    tenant: TenantContext,
) -> None:
    _missions_table, outbox_table = tables
    paused = _pause_at_gate(runtime, tenant)
    assert paused.status is MissionStatus.AWAITING_APPROVAL

    # the pending approval survived to the store (reload across a boundary)
    reloaded = runtime.load(paused.id, tenant)
    assert reloaded is not None and reloaded.has_active_approval

    # approve in its own transaction → RESUMED
    approved = runtime.approve(paused.id, tenant, comment="looks good")
    assert approved is not None and approved.status is MissionStatus.RESUMED

    # resume orchestration: detect + reload + re-enter + continue → COMPLETED
    resumed = runtime.resume_if_approved(paused.id, tenant)
    assert resumed is not None and resumed.status is MissionStatus.COMPLETED

    # durable final state: the approved gated step ran, no data lost
    final = runtime.load(paused.id, tenant)
    assert final is not None
    assert final.status is MissionStatus.COMPLETED
    assert len(final.step_results) == 2

    # the outbox captured the full narrative, in order (across all transitions)
    expected = [
        "mission.created",
        "mission.planned",
        "mission.step_completed",
        "mission.awaiting_approval",
        "mission.approved",
        "mission.resumed",
        "mission.step_completed",
        "mission.completed",
    ]
    assert _outbox_names(observer, outbox_table, paused.id) == expected

    # relay delivers every committed event to the Audit Sink, in order — Outbox + Audit still work
    runtime.relay()
    assert runtime.audit.event_names_for(paused.id) == expected


# ── reject variant: pause → reject → cancelled ────────────────────────────────
def test_pause_reject_cancels_with_outbox_and_audit(
    runtime: MissionRuntime,
    observer: psycopg.Connection,
    tables: tuple[str, str],
    tenant: TenantContext,
) -> None:
    _missions_table, outbox_table = tables
    paused = _pause_at_gate(runtime, tenant)

    rejected = runtime.reject(paused.id, tenant, comment="insufficient evidence")
    assert rejected is not None and rejected.status is MissionStatus.CANCELLED

    final = runtime.load(paused.id, tenant)
    assert final is not None and final.status is MissionStatus.CANCELLED

    assert _outbox_names(observer, outbox_table, paused.id) == [
        "mission.created",
        "mission.planned",
        "mission.step_completed",
        "mission.awaiting_approval",
        "mission.rejected",
    ]
    runtime.relay()
    assert runtime.audit.event_names_for(paused.id)[-1] == "mission.rejected"


# ── resume orchestration is a no-op when the mission was not approved ──────────
def test_resume_if_approved_is_a_noop_when_not_approved(
    runtime: MissionRuntime, tenant: TenantContext
) -> None:
    """A mission that is not RESUMED is returned unchanged — no transition, no events. Detection
    names the mission; it never re-drives one that no human approved."""
    completed = runtime.run_transition(lambda e: e.run_simple("q", tenant, "i"))
    assert completed.status is MissionStatus.COMPLETED

    same = runtime.resume_if_approved(completed.id, tenant)
    assert same is not None and same.status is MissionStatus.COMPLETED
    assert len(runtime.audit) == 0  # nothing relayed/emitted by the no-op resume
