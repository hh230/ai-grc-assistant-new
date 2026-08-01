"""End-to-end integration scenarios for Mission Store Slices 1–4, run as one system.

These drive the full path against a real PostgreSQL:

    Mission Engine → Mission Store → Unit of Work → Transactional Outbox
                   → Outbox Relay → Delivery Bus → Audit Sink

Nothing here re-tests a single slice in isolation (the frozen packages already do that); each test
exercises the *seams between* the slices — that state and events commit together, that the relay
delivers what committed and only what committed, and that audit receives exactly the published
stream. Every test is DB-gated and auto-skips without a database (see `conftest.py`).

Scenario map (from the integration brief):
  1. Simple Mission        — test_simple_mission_flows_end_to_end
  2. Composite Mission     — test_composite_mission_multi_transition_order
  3. Resume Scenario       — test_resume_reloads_from_store_and_completes
  4. Outbox Atomicity      — test_outbox_failure_aborts_the_mission_save
                             test_committed_mission_always_has_its_event
  5. Relay                 — test_relay_at_least_once / _leaves_unpublished / _marks_published
  6. Audit                 — test_all_published_events_reach_the_audit_sink
"""

from __future__ import annotations

import psycopg
import pytest
from event_bus import ALL_EVENTS, InProcessEventBus
from mission_engine import MissionStatus, Plan, PlanStep, single_step_plan
from mission_integration import MissionAuditSink, MissionRuntime
from mission_store import PostgresMissionStore, UnitOfWork
from mission_store.config import dsn as store_dsn
from pipeline_contracts import TenantContext

# ── low-level, out-of-band row helpers (assert on the raw tables, never the SUT connection) ──


def _outbox_names(conn: psycopg.Connection, table: str, mission_id: str) -> list[str]:
    rows = conn.execute(
        f"SELECT event_name FROM {table} WHERE mission_id = %s ORDER BY id", (mission_id,)
    ).fetchall()
    return [r[0] for r in rows]


def _scalar_count(conn: psycopg.Connection, sql: str, params: tuple[object, ...]) -> int:
    row = conn.execute(sql, params).fetchone()
    assert row is not None  # count(*) always returns exactly one row
    return int(row[0])


def _mission_rows(conn: psycopg.Connection, table: str, mission_id: str) -> int:
    return _scalar_count(conn, f"SELECT count(*) FROM {table} WHERE id = %s", (mission_id,))


def _unpublished(conn: psycopg.Connection, table: str) -> int:
    return _scalar_count(conn, f"SELECT count(*) FROM {table} WHERE published_at IS NULL", ())


# ── 1. Simple Mission ────────────────────────────────────────────────────────────────────
def test_simple_mission_flows_end_to_end(
    runtime: MissionRuntime,
    observer: psycopg.Connection,
    tables: tuple[str, str],
    tenant: TenantContext,
) -> None:
    """The 'even the simplest question is a Mission' path, all the way to Audit. One transition
    (create → plan → execute) commits mission state and all four events atomically; the relay then
    delivers them onto the Delivery Bus and into the Audit Sink."""
    missions_table, outbox_table = tables

    mission = runtime.run_transition(
        lambda e: e.run_simple("MFA lookup", tenant, "what does NCA ECC say about MFA?")
    )

    # Mission persisted and COMPLETED in the store.
    assert mission.status is MissionStatus.COMPLETED
    assert _mission_rows(observer, missions_table, mission.id) == 1
    reloaded = runtime.load(mission.id, tenant)
    assert reloaded is not None
    assert reloaded.status is MissionStatus.COMPLETED
    assert len(reloaded.step_results) == 1

    # Domain events captured to the outbox, atomically with the save.
    assert _outbox_names(observer, outbox_table, mission.id) == [
        "mission.created",
        "mission.planned",
        "mission.step_completed",
        "mission.completed",
    ]

    # Nothing delivered until we relay (delivery is outside the write transaction).
    assert runtime.audit.event_names_for(mission.id) == []

    delivered = runtime.relay()
    assert delivered == 4
    assert runtime.audit.event_names_for(mission.id) == [
        "mission.created",
        "mission.planned",
        "mission.step_completed",
        "mission.completed",
    ]
    assert _unpublished(observer, outbox_table) == 0


# ── 2. Composite Mission ─────────────────────────────────────────────────────────────────
def test_composite_mission_multi_transition_order(
    runtime: MissionRuntime,
    observer: psycopg.Connection,
    tables: tuple[str, str],
    tenant: TenantContext,
) -> None:
    """A composite mission driven as several *separate* transitions (each its own transaction).
    Every transition saves correctly, every transition's events reach the outbox, and the relay
    delivers the whole stream in insertion order into Audit."""
    missions_table, outbox_table = tables
    three_step = Plan(
        steps=(
            PlanStep(description="retrieve", instruction="find ECC MFA"),
            PlanStep(description="assess", instruction="score coverage"),
            PlanStep(description="summarise", instruction="draft summary"),
        )
    )

    mission = runtime.run_transition(lambda e: e.create("gap analysis", tenant))
    assert mission.status is MissionStatus.CREATED
    runtime.run_transition(lambda e: e.plan(mission, three_step))
    executed = runtime.run_transition(lambda e: e.execute(mission))

    assert executed.status is MissionStatus.COMPLETED
    assert executed.execution_profile is not None
    assert executed.execution_profile.value == "composite"

    # Each of the three steps was recorded and persisted.
    reloaded = runtime.load(mission.id, tenant)
    assert reloaded is not None
    assert len(reloaded.step_results) == 3

    # Every transition's events landed in the outbox, in order (3 step_completed between).
    assert _outbox_names(observer, outbox_table, mission.id) == [
        "mission.created",
        "mission.planned",
        "mission.step_completed",
        "mission.step_completed",
        "mission.step_completed",
        "mission.completed",
    ]

    delivered = runtime.relay()
    assert delivered == 6
    assert runtime.audit.event_names_for(mission.id) == [
        "mission.created",
        "mission.planned",
        "mission.step_completed",
        "mission.step_completed",
        "mission.step_completed",
        "mission.completed",
    ]


# ── 3. Resume Scenario ───────────────────────────────────────────────────────────────────
def test_resume_reloads_from_store_and_completes(
    runtime: MissionRuntime,
    observer: psycopg.Connection,
    tables: tuple[str, str],
    tenant: TenantContext,
) -> None:
    """Run a mission, stop at a process boundary, reload from the Mission Store, and resume to
    completion — proving durable state survives the stop with no data loss and no missing events.

    The stop point is between PLANNED and EXECUTING: the in-memory aggregate from the first two
    transitions is discarded, the mission is reconstructed purely from the store, and execution
    continues on that reloaded aggregate. (No human-approval gate is involved — that surface is a
    later phase and out of scope here.)"""
    missions_table, outbox_table = tables

    created = runtime.run_transition(lambda e: e.create("resumable mission", tenant))
    mission_id = created.id
    runtime.run_transition(
        lambda e: e.plan(created, single_step_plan("do the work", description="resumable"))
    )

    # --- simulate a process restart ---
    # Everything below reconstructs the mission *only* from durable storage and never touches the
    # `created` aggregate again — the reloaded `resumed` object is the one that gets executed, so
    # the resume genuinely rides on persisted state, not on the in-memory handle.
    resumed = runtime.load(mission_id, tenant)
    assert resumed is not None
    assert resumed.status is MissionStatus.PLANNED  # exactly where we stopped
    assert resumed.plan is not None
    assert not resumed.step_results  # nothing executed yet

    # Resume: continue the lifecycle on the reloaded aggregate.
    completed = runtime.run_transition(lambda e: e.execute(resumed))
    assert completed.status is MissionStatus.COMPLETED

    # No data loss: the final persisted state is coherent and complete.
    final = runtime.load(mission_id, tenant)
    assert final is not None
    assert final.status is MissionStatus.COMPLETED
    assert len(final.step_results) == 1

    # No missing events: the full lifecycle is in the outbox and reaches Audit, in order.
    assert _outbox_names(observer, outbox_table, mission_id) == [
        "mission.created",
        "mission.planned",
        "mission.step_completed",
        "mission.completed",
    ]
    runtime.relay()
    assert runtime.audit.event_names_for(mission_id) == [
        "mission.created",
        "mission.planned",
        "mission.step_completed",
        "mission.completed",
    ]


# ── 4. Outbox Atomicity ──────────────────────────────────────────────────────────────────
def _failing_write(event: object) -> None:
    """A capture-bus subscriber that raises on the event write — to prove that if the outbox write
    fails inside the transaction, the mission `save` in the same transaction is rolled back too (no
    dual write, ADR 0043-S4 I1/I2)."""
    raise RuntimeError("outbox write blew up")


def test_outbox_failure_aborts_the_mission_save(
    observer: psycopg.Connection,
    tables: tuple[str, str],
    tenant: TenantContext,
) -> None:
    """If the outbox fails during the transaction, the mission is NOT saved. We wire one transition
    by hand (the runtime always wires a healthy sink) so the sink can fail, and assert both tables
    are empty after the abort.

    The engine's `create` calls `save` and *then* emits — the emit runs the failing sink and raises
    inside `create`, so the raise is proof the mission was already written (uncommitted) when the
    event write blew up. The `UnitOfWork` rolls the whole transaction back on that exception, so the
    already-written mission row is discarded too — the atomicity guarantee (I1/I2)."""
    from mission_engine import EchoExecutor, MissionEngine

    missions_table, outbox_table = tables
    writer = psycopg.connect(store_dsn(), autocommit=False)
    try:
        with pytest.raises(RuntimeError, match="blew up"), UnitOfWork(connection=writer) as uow:
            store = PostgresMissionStore(connection=uow.connection, table=missions_table)
            bus = InProcessEventBus()  # no error_handler → the failure propagates and aborts
            bus.subscribe(ALL_EVENTS, _failing_write)
            engine = MissionEngine(store, EchoExecutor(), events=bus)
            engine.create("doomed", tenant)  # save happens, then the event write raises → rollback
            uow.commit()
    finally:
        writer.close()

    # Neither the mission nor any event survived — the whole transaction rolled back (atomicity).
    assert _scalar_count(observer, f"SELECT count(*) FROM {missions_table}", ()) == 0
    assert _unpublished(observer, outbox_table) == 0


def test_committed_mission_always_has_its_event(
    runtime: MissionRuntime,
    observer: psycopg.Connection,
    tables: tuple[str, str],
    tenant: TenantContext,
) -> None:
    """The other direction of atomicity: if the mission IS saved, its event IS in the outbox. A
    healthy transition commits both; an outside observer sees the pair appear together."""
    missions_table, outbox_table = tables
    mission = runtime.run_transition(lambda e: e.create("committed", tenant))

    assert _mission_rows(observer, missions_table, mission.id) == 1
    assert _outbox_names(observer, outbox_table, mission.id) == ["mission.created"]


# ── 5. Relay ─────────────────────────────────────────────────────────────────────────────
def test_relay_marks_published_and_is_idempotent(
    runtime: MissionRuntime,
    observer: psycopg.Connection,
    tables: tuple[str, str],
    tenant: TenantContext,
) -> None:
    """The relay marks delivered rows published and a re-drain finds nothing (published rows stay
    published; unpublished rows are what remain)."""
    _missions_table, outbox_table = tables
    runtime.run_transition(lambda e: e.run_simple("q", tenant, "instr"))

    assert _unpublished(observer, outbox_table) == 4
    assert runtime.relay() == 4
    assert _unpublished(observer, outbox_table) == 0
    # A second drain delivers nothing new — idempotent once published.
    assert runtime.relay() == 0
    assert len(runtime.audit) == 4


def test_relay_at_least_once_on_lost_mark(
    runtime: MissionRuntime,
    observer: psycopg.Connection,
    tables: tuple[str, str],
    tenant: TenantContext,
) -> None:
    """At-least-once: if the published-mark is lost (a crash after delivery, before the mark
    commits), the event is re-delivered on the next drain — never dropped. We reproduce the lost
    mark with a non-autocommit relay connection that we roll back after the drain."""
    from mission_store import DeliveryBusPublisher, OutboxRelay

    _missions_table, outbox_table = tables
    mission = runtime.run_transition(lambda e: e.create("g", tenant))

    audit = MissionAuditSink()
    delivery = InProcessEventBus()
    delivery.subscribe(ALL_EVENTS, audit.record)

    marker = psycopg.connect(store_dsn(), autocommit=False)
    try:
        # deliver once, but the mark never commits (simulated crash)
        assert OutboxRelay(connection=marker, table=outbox_table).drain(
            DeliveryBusPublisher(delivery)
        ) == 1
        marker.rollback()
    finally:
        marker.close()

    # The row is still unpublished → a fresh drain re-delivers it (duplicate delivery is allowed).
    assert _unpublished(observer, outbox_table) == 1
    assert OutboxRelay(connection=observer, table=outbox_table).drain(
        DeliveryBusPublisher(delivery)
    ) == 1
    assert audit.event_names_for(mission.id) == ["mission.created", "mission.created"]


def test_unpublished_rows_stay_in_outbox_until_relayed(
    runtime: MissionRuntime,
    observer: psycopg.Connection,
    tables: tuple[str, str],
    tenant: TenantContext,
) -> None:
    """Events that have not been relayed remain in the outbox (unpublished), reachable by a later
    drain — the store-and-forward guarantee behind at-least-once delivery."""
    _missions_table, outbox_table = tables
    runtime.run_transition(lambda e: e.create("g1", tenant))
    runtime.run_transition(lambda e: e.create("g2", tenant))

    # Both creations are committed but undelivered — they wait in the outbox.
    assert _unpublished(observer, outbox_table) == 2
    assert len(runtime.audit) == 0  # nothing delivered yet

    assert runtime.relay() == 2
    assert _unpublished(observer, outbox_table) == 0
    assert len(runtime.audit) == 2


# ── 6. Audit ─────────────────────────────────────────────────────────────────────────────
def test_all_published_events_reach_the_audit_sink(
    runtime: MissionRuntime,
    tables: tuple[str, str],
    tenant: TenantContext,
) -> None:
    """Every published event reaches the Audit Sink — across two independent missions, delivered in
    outbox insertion order, each event carrying its mission and tenant stamp intact through the
    whole path."""
    _missions_table, _outbox_table = tables
    m1 = runtime.run_transition(lambda e: e.run_simple("q1", tenant, "i1"))
    m2 = runtime.run_transition(lambda e: e.create("q2", tenant))

    total = runtime.relay()
    assert total == 5  # 4 for the simple mission + 1 create

    # Every delivered event kept its stamps (tenant isolation preserved end-to-end).
    assert all(e.tenant_id == tenant.tenant_id for e in runtime.audit.records)
    assert runtime.audit.event_names_for(m1.id) == [
        "mission.created",
        "mission.planned",
        "mission.step_completed",
        "mission.completed",
    ]
    assert runtime.audit.event_names_for(m2.id) == ["mission.created"]
    assert len(runtime.audit) == 5
