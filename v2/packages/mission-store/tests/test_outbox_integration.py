"""Postgres-specific guarantees of the Transactional Outbox (ADR 0043-S4). DB-gated: connects to
`MISSION_STORE_DSN` (default: the isolated `rasheed_v2` dev DB) and **skips cleanly** when no
database is reachable, exactly like the other integration suites.

Each test stands the missions + outbox schema up on throwaway `*_s4_*` tables and drops them after,
so nothing pollutes the canonical tables. The Capture Bus is wired per transition (per-transition
only — no whole-run, Rev.3), and its only side-effecting subscriber is the `OutboxSink`; the
Delivery Bus is a separate `RecordingEventBus` the relay publishes onto.

Invariants exercised end-to-end: I1/I2 (event committed iff state committed), I3 (sink never
commits), §6 (any event-write failure rolls back *all* of the transition's events), I6
(at-least-once), I8 (unregistered event left unpublished), I11 (relay only publishes committed).
"""

from __future__ import annotations

import uuid

import pytest

psycopg = pytest.importorskip("psycopg")

from event_bus import ALL_EVENTS, InProcessEventBus, RecordingEventBus  # noqa: E402
from mission_engine import (  # noqa: E402
    EchoExecutor,
    MissionEngine,
    MissionStatus,
    Plan,
    PlanStep,
)
from mission_store import (  # noqa: E402
    DeliveryBusPublisher,
    OutboxRelay,
    OutboxSink,
    PostgresMissionStore,
    UnitOfWork,
    UnsupportedEventType,
)
from mission_store.config import dsn  # noqa: E402
from mission_store.outbox_schema import apply_outbox_schema  # noqa: E402
from mission_store.schema import apply_schema  # noqa: E402
from psycopg.types.json import Jsonb  # noqa: E402


def _connect(**kw):
    try:
        return psycopg.connect(dsn(), connect_timeout=3, **kw)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"no reachable PostgreSQL ({exc})")


@pytest.fixture
def observer():
    c = _connect(autocommit=True)
    yield c
    c.close()


@pytest.fixture
def tables(observer):
    suffix = uuid.uuid4().hex[:8]
    missions_table = f"missions_s4_{suffix}"
    outbox_table = f"outbox_s4_{suffix}"
    apply_schema(observer, missions_table)
    apply_outbox_schema(observer, outbox_table)
    yield missions_table, outbox_table
    observer.execute(f"DROP TABLE IF EXISTS {missions_table}")
    observer.execute(f"DROP TABLE IF EXISTS {outbox_table}")


# ── helpers ───────────────────────────────────────────────────────────────────
def _event_names(conn, table, mission_id):
    rows = conn.execute(
        f"SELECT event_name FROM {table} WHERE mission_id = %s ORDER BY id", (mission_id,)
    ).fetchall()
    return [r[0] for r in rows]


def _count(conn, table, mission_id):
    return conn.execute(
        f"SELECT count(*) FROM {table} WHERE id = %s", (mission_id,)
    ).fetchone()[0]


def _unpublished_count(conn, table):
    return conn.execute(
        f"SELECT count(*) FROM {table} WHERE published_at IS NULL"
    ).fetchone()[0]


def _run_transition(missions_table, outbox_table, apply):
    """Drive ONE engine transition inside its own UnitOfWork (per-transition only): store + outbox
    sink bound to the same connection, a synchronous Capture Bus with the sink subscribed."""
    writer = _connect(autocommit=False)
    try:
        with UnitOfWork(connection=writer) as uow:
            store = PostgresMissionStore(connection=uow.connection, table=missions_table)
            capture_bus = InProcessEventBus()  # any EventBus impl; synchronous, no isolation
            capture_bus.subscribe(
                ALL_EVENTS, OutboxSink(connection=uow.connection, table=outbox_table).write
            )
            engine = MissionEngine(store, EchoExecutor(), events=capture_bus)
            return apply(engine)
    finally:
        writer.close()


# ── I1/I2 & invisibility before commit ────────────────────────────────────────
def test_transition_commits_mission_and_its_event_atomically(observer, tables, tenant):
    missions_table, outbox_table = tables
    writer = _connect(autocommit=False)
    try:
        with UnitOfWork(connection=writer) as uow:
            store = PostgresMissionStore(connection=uow.connection, table=missions_table)
            capture_bus = InProcessEventBus()
            capture_bus.subscribe(
                ALL_EVENTS, OutboxSink(connection=uow.connection, table=outbox_table).write
            )
            engine = MissionEngine(store, EchoExecutor(), events=capture_bus)
            mission = engine.create("g", tenant)  # save(mission) + publish(MissionCreated)
            # invisible before commit: an outside connection sees neither the mission nor its event
            assert _count(observer, missions_table, mission.id) == 0
            assert _unpublished_count(observer, outbox_table) == 0
        # after commit: both present, together (I1/I2)
        assert _count(observer, missions_table, mission.id) == 1
        assert _event_names(observer, outbox_table, mission.id) == ["mission.created"]
    finally:
        writer.close()


# ── §6: any event-write failure rolls back ALL events of the transition ────────
class _FailOnNthSink:
    """A capture-bus subscriber that writes through a real OutboxSink but raises on the Nth event —
    to prove that a failure mid-transition discards *every* event of that transition, not just the
    failing one (ADR 0043-S4 Rev.3 §6)."""

    def __init__(self, real: OutboxSink, *, fail_on: int) -> None:
        self._real = real
        self._fail_on = fail_on
        self._seen = 0

    def write(self, event) -> None:
        self._seen += 1
        if self._seen == self._fail_on:
            raise RuntimeError("event write blew up")
        self._real.write(event)


def test_any_event_write_failure_rolls_back_the_whole_transition(observer, tables, tenant):
    missions_table, outbox_table = tables
    # setup: create + plan committed, each in its own transition
    mission = _run_transition(missions_table, outbox_table, lambda e: e.create("g", tenant))
    two_step = Plan(
        steps=(
            PlanStep(description="a", instruction="x"),
            PlanStep(description="b", instruction="y"),
        )
    )
    _run_transition(missions_table, outbox_table, lambda e: e.plan(mission, two_step))
    assert _event_names(observer, outbox_table, mission.id) == [
        "mission.created",
        "mission.planned",
    ]

    # execute in one transition, but the 2nd emitted event write fails: step-1's event was already
    # written (uncommitted) — it must roll back too, along with the whole execute.
    writer = _connect(autocommit=False)
    try:
        with pytest.raises(RuntimeError, match="blew up"), UnitOfWork(connection=writer) as uow:
            store = PostgresMissionStore(connection=uow.connection, table=missions_table)
            sink = OutboxSink(connection=uow.connection, table=outbox_table)
            capture_bus = InProcessEventBus()
            capture_bus.subscribe(ALL_EVENTS, _FailOnNthSink(sink, fail_on=2).write)
            engine = MissionEngine(store, EchoExecutor(), events=capture_bus)
            engine.execute(mission)  # emits step1, step2(fails), ...
            uow.commit()
    finally:
        writer.close()

    # the mission stayed PLANNED (execute rolled back), no step results, and NONE of execute's
    # events landed — not step-1's, which was written before the failure (§6)
    reloaded = PostgresMissionStore(connection=observer, table=missions_table).get(
        mission.id, tenant
    )
    assert reloaded is not None
    assert reloaded.status is MissionStatus.PLANNED
    assert len(reloaded.step_results) == 0
    assert _event_names(observer, outbox_table, mission.id) == [
        "mission.created",
        "mission.planned",
    ]


# ── end-to-end: capture per transition, then drain to the Delivery Bus in order ─
def test_end_to_end_capture_then_drain_delivers_in_order(observer, tables, tenant):
    missions_table, outbox_table = tables
    mission = _run_transition(missions_table, outbox_table, lambda e: e.create("g", tenant))
    _run_transition(
        missions_table,
        outbox_table,
        lambda e: e.plan(mission, Plan(steps=(PlanStep(description="s", instruction="i"),))),
    )
    _run_transition(missions_table, outbox_table, lambda e: e.execute(mission))

    delivery = RecordingEventBus()  # the Delivery Bus (outside the transaction)
    relay = OutboxRelay(connection=observer, table=outbox_table)
    n = relay.drain(DeliveryBusPublisher(delivery))

    assert n == 4
    assert [e.name for e in delivery.events] == [
        "mission.created",
        "mission.planned",
        "mission.step_completed",
        "mission.completed",
    ]
    assert all(e.tenant_id == tenant.tenant_id for e in delivery.events)  # tenant stamp kept (I5)
    assert _unpublished_count(observer, outbox_table) == 0  # every row marked published
    # a second drain finds nothing — idempotent once published
    assert relay.drain(DeliveryBusPublisher(delivery)) == 0
    assert len(delivery.events) == 4


# ── I6: at-least-once — a lost mark re-publishes on the next drain ─────────────
def test_at_least_once_when_mark_is_not_persisted(observer, tables, tenant):
    missions_table, outbox_table = tables
    _run_transition(missions_table, outbox_table, lambda e: e.create("g", tenant))
    delivery = RecordingEventBus()

    marker = _connect(autocommit=False)  # non-autocommit: marks are not durable until commit
    try:
        assert OutboxRelay(connection=marker, table=outbox_table).drain(
            DeliveryBusPublisher(delivery)
        ) == 1
        marker.rollback()  # simulate a crash after publish, before the mark committed
    finally:
        marker.close()

    # the event is still unpublished → a fresh drain re-publishes it (at-least-once, I6)
    assert _unpublished_count(observer, outbox_table) == 1
    assert OutboxRelay(connection=observer, table=outbox_table).drain(
        DeliveryBusPublisher(delivery)
    ) == 1
    assert [e.name for e in delivery.events] == ["mission.created", "mission.created"]  # duplicate


# ── I8: an unregistered event is left unpublished, never delivered ────────────
def test_unsupported_event_type_leaves_row_unpublished(observer, tables, tenant):
    _missions_table, outbox_table = tables
    observer.execute(
        f"INSERT INTO {outbox_table} (event_name, trace_id, tenant_id, mission_id, "
        "occurred_at, payload, payload_schema_version) VALUES (%s, %s, %s, %s, %s, %s, %s)",
        ("mystery.event", "trc", "org_acme", "mis_x", 1.0, Jsonb({"name": "mystery.event"}), 1),
    )
    delivery = RecordingEventBus()
    relay = OutboxRelay(connection=observer, table=outbox_table)

    with pytest.raises(UnsupportedEventType) as exc_info:
        relay.drain(DeliveryBusPublisher(delivery))

    assert exc_info.value.event_name == "mystery.event"
    assert delivery.events == []  # never delivered
    assert _unpublished_count(observer, outbox_table) == 1  # left unpublished — not deleted/marked
