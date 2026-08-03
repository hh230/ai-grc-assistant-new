"""Postgres-specific guarantees for GovernancePlan/PlanItem/events/organization-profile
persistence (ADR 0066 §3.1, §5). DB-gated: connects to `GOVERNANCE_STORE_DSN` (default: the
isolated `rasheed_v2` dev DB) and skips cleanly when no database is reachable.

Each test uses a unique tenant_id and deletes everything it wrote in a `finally` block, so nothing
pollutes the canonical tables or collides with other tests/sessions.
"""

from __future__ import annotations

import uuid

import pytest

psycopg = pytest.importorskip("psycopg")

from governance_discovery.plan import GovernancePlan, PlanItem  # noqa: E402
from governance_discovery.signal import Signal, SignalSet, ValueType  # noqa: E402
from governance_store import PostgresGovernanceStore  # noqa: E402
from governance_store.config import dsn  # noqa: E402


def _connect():
    try:
        return psycopg.connect(dsn(), autocommit=True, connect_timeout=3)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"no reachable PostgreSQL ({exc})")


def _tenant() -> str:
    return f"it_tenant_{uuid.uuid4().hex[:8]}"


def _plan(tenant_id: str, **overrides) -> GovernancePlan:
    base = GovernancePlan(
        id=f"plan_{uuid.uuid4().hex[:8]}",
        tenant_id=tenant_id,
        source_mission_id="mission_1",
        status="active",
        version=1,
        inferred_frameworks=(
            {"framework_id": "framework:iso_27001", "confidence": 0.6, "rationale_key": "x"},
        ),
        maturity_baseline={"governance": {"score": 2, "stars": 1, "label": "limited"}},
        created_at=1000.0,
        updated_at=1000.0,
    )
    return base if not overrides else base.__class__(**{**base.__dict__, **overrides})


def _item(tenant_id: str, plan_id: str, **overrides) -> PlanItem:
    base = PlanItem(
        id=f"item_{uuid.uuid4().hex[:8]}",
        plan_id=plan_id,
        tenant_id=tenant_id,
        pillar="risk",
        title="Establish a risk register",
        objective="Track operational risks",
        expected_outcome="Risks reviewed regularly",
        rationale="No risk register found",
        timeframe_bucket="week_1",
        priority="high",
        effort_size="small",
        depends_on_item_ids=(),
        status="not_started",
        source_signal_keys=("risk_register_state",),
        source_framework_refs=(),
        created_at=1000.0,
        updated_at=1000.0,
        resolves_signal={"signal": "risk_register_state", "value": "approved"},
    )
    return base if not overrides else base.__class__(**{**base.__dict__, **overrides})


@pytest.fixture
def store():
    conn = _connect()
    from governance_store.schema import apply_schema

    apply_schema(conn)
    s = PostgresGovernanceStore(connection=conn)
    yield s
    conn.close()


def _cleanup(conn, tenant_id: str) -> None:
    conn.execute(
        "DELETE FROM governance_plan_events WHERE tenant_id = %(t)s", {"t": tenant_id}
    )
    conn.execute("DELETE FROM governance_plan_items WHERE tenant_id = %(t)s", {"t": tenant_id})
    conn.execute("DELETE FROM governance_plans WHERE tenant_id = %(t)s", {"t": tenant_id})
    conn.execute("DELETE FROM organization_profiles WHERE tenant_id = %(t)s", {"t": tenant_id})


def test_plan_round_trip_and_version_lineage(store: PostgresGovernanceStore) -> None:
    tenant_id = _tenant()
    try:
        plan_v1 = _plan(tenant_id)
        store.create_plan(plan_v1)

        fetched = store.get_plan(plan_v1.id, tenant_id)
        assert fetched is not None
        assert fetched.status == "active"
        assert fetched.maturity_baseline == plan_v1.maturity_baseline

        active = store.get_active_plan(tenant_id)
        assert active is not None and active.id == plan_v1.id

        # A new version supersedes the old one — both rows persist, never edited in place.
        superseded_ok = store.supersede_plan(
            plan_v1.id, tenant_id,
            maturity_at_supersession={
                "governance": {"score": 6, "stars": 3, "label": "developing"}
            },
            now=2000.0,
        )
        assert superseded_ok is True
        plan_v2 = _plan(
            tenant_id, id=f"plan_{uuid.uuid4().hex[:8]}", version=2, previous_plan_id=plan_v1.id
        )
        store.create_plan(plan_v2)

        versions = store.list_plan_versions(tenant_id)
        assert [p.version for p in versions] == [1, 2]
        assert versions[0].status == "superseded"
        assert versions[0].maturity_at_supersession is not None
        # supersede_plan never touches content — the original snapshot is untouched.
        assert versions[0].maturity_baseline == plan_v1.maturity_baseline
        assert versions[1].status == "active"
        assert versions[1].previous_plan_id == plan_v1.id

        assert store.get_active_plan(tenant_id).id == plan_v2.id
    finally:
        _cleanup(store._conn, tenant_id)  # noqa: SLF001


def test_supersede_plan_only_ever_applies_once(store: PostgresGovernanceStore) -> None:
    """The `WHERE status = 'active'` gate (Phase 3 hardening): a second attempt to supersede an
    already-superseded plan is a no-op, not a double-transition — the DB enforces it, not
    convention. Also proves the `False` return means "genuinely nothing happened", not an
    exception a careless caller might not catch."""
    tenant_id = _tenant()
    try:
        plan = _plan(tenant_id)
        store.create_plan(plan)

        first = store.supersede_plan(
            plan.id,
            tenant_id,
            maturity_at_supersession={"governance": {"score": 4, "stars": 2, "label": "initial"}},
            now=2000.0,
        )
        assert first is True

        second = store.supersede_plan(
            plan.id,
            tenant_id,
            maturity_at_supersession={
                "governance": {"score": 8, "stars": 4, "label": "established"}
            },
            now=3000.0,
        )
        assert second is False  # already superseded — refused, not silently reapplied

        fetched = store.get_plan(plan.id, tenant_id)
        # the FIRST supersession's snapshot survives untouched — the second never landed.
        assert fetched.maturity_at_supersession == {
            "governance": {"score": 4, "stars": 2, "label": "initial"}
        }
        assert fetched.updated_at == 2000.0
    finally:
        _cleanup(store._conn, tenant_id)  # noqa: SLF001


def test_supersede_plan_never_touches_the_other_tenants_plan(
    store: PostgresGovernanceStore,
) -> None:
    tenant_a, tenant_b = _tenant(), _tenant()
    try:
        plan = _plan(tenant_a)
        store.create_plan(plan)

        applied = store.supersede_plan(
            plan.id,
            tenant_b,
            maturity_at_supersession={"governance": {"score": 1, "stars": 0, "label": "none"}},
            now=2000.0,
        )
        assert applied is False

        fetched = store.get_plan(plan.id, tenant_a)
        assert fetched.status == "active"  # tenant-b's call never touched tenant-a's plan
    finally:
        _cleanup(store._conn, tenant_a)
        _cleanup(store._conn, tenant_b)


def _transition(store, prior_item, updated_item, event_type, *, event_id=None):
    return store.record_item_transition(
        updated_item,
        expected_updated_at=prior_item.updated_at,
        event_id=event_id or f"evt_{uuid.uuid4().hex[:8]}",
        event_type=event_type,
        actor_id="user_1",
        created_at=updated_item.updated_at,
    )


def test_plan_item_completion_is_reversible_via_effective_signals(
    store: PostgresGovernanceStore,
) -> None:
    from governance_discovery.execution import effective_signals

    tenant_id = _tenant()
    try:
        plan = _plan(tenant_id)
        store.create_plan(plan)
        item = _item(tenant_id, plan.id)
        store.create_plan_item(item)

        baseline = SignalSet().with_signal(
            Signal(key="risk_register_state", value_type=ValueType.ENUM, value="absent")
        )

        # Nothing completed yet -> effective state is just the baseline.
        assert store.list_completed_resolutions(tenant_id) == []
        assert effective_signals(baseline, store.list_completed_resolutions(tenant_id)).value(
            "risk_register_state"
        ) == "absent"

        # Mark done -> the resolution appears, and effective_signals reflects it.
        done = item.marked_done(now=1500.0)
        assert _transition(store, item, done, "completed") is True
        resolutions = store.list_completed_resolutions(tenant_id)
        assert len(resolutions) == 1
        assert effective_signals(baseline, resolutions).value("risk_register_state") == "approved"

        # Reopen -> no undo logic needed; it just stops appearing.
        reopened = done.reopened(now=1600.0)
        assert _transition(store, done, reopened, "reopened") is True
        assert store.list_completed_resolutions(tenant_id) == []
        assert effective_signals(baseline, store.list_completed_resolutions(tenant_id)).value(
            "risk_register_state"
        ) == "absent"
    finally:
        _cleanup(store._conn, tenant_id)  # noqa: SLF001


def test_record_item_transition_rejects_a_stale_write(store: PostgresGovernanceStore) -> None:
    """The optimistic lock (Phase 3 hardening): two callers read the same item, then both try to
    write. The first wins; the second's `expected_updated_at` no longer matches, so it is refused
    — never a silent lost update (e.g. the second caller's evidence overwriting the first's)."""
    tenant_id = _tenant()
    try:
        plan = _plan(tenant_id)
        store.create_plan(plan)
        item = _item(tenant_id, plan.id)
        store.create_plan_item(item)

        # Both "read" the same version (item.updated_at == 1000.0).
        writer_a = item.with_evidence(("ev_a",), now=1500.0)
        writer_b = item.with_evidence(("ev_b",), now=1600.0)

        assert _transition(store, item, writer_a, "evidence_attached") is True
        # writer_b still expects the OLD updated_at (1000.0) — it lost the race.
        assert _transition(store, item, writer_b, "evidence_attached") is False

        fetched = store.get_plan_item(item.id, tenant_id)
        assert set(fetched.evidence_ids) == {"ev_a"}  # writer_b's evidence never landed

        events = store.list_plan_events(item.id, tenant_id)
        assert len(events) == 1  # the rejected write appended no event either — atomic, not partial
    finally:
        _cleanup(store._conn, tenant_id)  # noqa: SLF001


def test_record_item_transition_rolls_back_the_item_update_if_the_event_insert_fails(
    store: PostgresGovernanceStore,
) -> None:
    """The stronger atomicity claim, proven directly rather than inferred from reading the code:
    force the item's UPDATE to succeed and THEN force the event's INSERT to fail (a colliding
    primary key) — a genuine mid-transaction failure, not merely a lock rejection. If
    `record_item_transition` were only two separate autocommitted statements, the item would stay
    `done` with no matching event even though the call raised. Instead, psycopg3's
    `with self._conn.transaction():` rolls the WHOLE block back on the exception, including the
    already-executed UPDATE — the item is left exactly as it was before the call."""
    tenant_id = _tenant()
    try:
        plan = _plan(tenant_id)
        store.create_plan(plan)
        item = _item(tenant_id, plan.id)
        store.create_plan_item(item)

        colliding_event_id = f"evt_collide_{uuid.uuid4().hex[:8]}"
        store._conn.execute(  # noqa: SLF001 — pre-seed a row that will collide on id
            "INSERT INTO governance_plan_events "
            "(id, plan_item_id, tenant_id, event_type, actor_id, created_at) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (colliding_event_id, item.id, tenant_id, "manual_seed", "system", 999.0),
        )

        done = item.marked_done(now=1500.0)
        with pytest.raises(Exception, match="duplicate key"):
            store.record_item_transition(
                done,
                expected_updated_at=item.updated_at,
                event_id=colliding_event_id,  # collides -> the event INSERT fails
                event_type="completed",
                actor_id="user_1",
                created_at=1500.0,
            )

        # The item UPDATE ran (rowcount > 0) before the event INSERT failed — if the two writes
        # were not in one transaction, this would now read "done". They are, so it doesn't.
        fetched = store.get_plan_item(item.id, tenant_id)
        assert fetched.status == "not_started"
        assert fetched.updated_at == 1000.0

        events = store.list_plan_events(item.id, tenant_id)
        assert [e.event_type for e in events] == ["manual_seed"]  # only the pre-seeded row exists
    finally:
        _cleanup(store._conn, tenant_id)  # noqa: SLF001


def test_evidence_is_never_required_and_is_reflected_when_present(
    store: PostgresGovernanceStore,
) -> None:
    tenant_id = _tenant()
    try:
        plan = _plan(tenant_id)
        store.create_plan(plan)
        item = _item(tenant_id, plan.id)
        store.create_plan_item(item)

        # Complete WITHOUT evidence — must succeed (ADR 0066 §5.4).
        done = item.marked_done(now=1500.0)
        assert _transition(store, item, done, "completed") is True
        refetched = store.get_plan_item(item.id, tenant_id)
        assert refetched.status == "done"
        assert not refetched.is_evidence_backed

        # Attach evidence afterward.
        with_evidence = refetched.with_evidence(("ev_1", "ev_2"), now=1600.0)
        assert _transition(store, refetched, with_evidence, "evidence_attached") is True
        refetched2 = store.get_plan_item(item.id, tenant_id)
        assert refetched2.is_evidence_backed
        assert set(refetched2.evidence_ids) == {"ev_1", "ev_2"}
    finally:
        _cleanup(store._conn, tenant_id)  # noqa: SLF001


def test_plan_events_are_append_only_and_ordered_by_sequence(
    store: PostgresGovernanceStore,
) -> None:
    """`list_plan_events` orders by `sequence`, not `created_at` (Phase 3 hardening) — this test
    deliberately gives the two events the SAME timestamp, which `created_at` alone could not order
    deterministically, and asserts the database-assigned `sequence` still reflects insertion
    order."""
    tenant_id = _tenant()
    try:
        plan = _plan(tenant_id)
        store.create_plan(plan)
        item = _item(tenant_id, plan.id)
        store.create_plan_item(item)

        same_instant = 1500.0
        done = item.marked_done(now=same_instant)
        assert _transition(store, item, done, "completed", event_id="evt_1") is True
        reopened = done.reopened(now=same_instant)
        assert _transition(store, done, reopened, "reopened", event_id="evt_2") is True

        events = store.list_plan_events(item.id, tenant_id)
        assert [e.event_type for e in events] == ["completed", "reopened"]
        assert [e.created_at for e in events] == [same_instant, same_instant]  # same timestamp...
        assert events[0].sequence < events[1].sequence  # ...but sequence still orders them
    finally:
        _cleanup(store._conn, tenant_id)  # noqa: SLF001


def test_append_plan_event_rejects_an_item_from_a_different_tenant(
    store: PostgresGovernanceStore,
) -> None:
    """Defensive tenant check (Phase 3 hardening): `append_plan_event` verifies `plan_item_id`
    actually belongs to `tenant_id` before inserting, rather than trusting the caller blindly."""
    tenant_a, tenant_b = _tenant(), _tenant()
    try:
        plan = _plan(tenant_a)
        store.create_plan(plan)
        item = _item(tenant_a, plan.id)
        store.create_plan_item(item)

        with pytest.raises(ValueError, match="does not belong to the given tenant"):
            store.append_plan_event(
                event_id=f"evt_{uuid.uuid4().hex[:8]}",
                plan_item_id=item.id,
                tenant_id=tenant_b,  # wrong tenant for this item
                event_type="completed",
                actor_id="user_1",
                created_at=1500.0,
            )
        assert store.list_plan_events(item.id, tenant_a) == []
    finally:
        _cleanup(store._conn, tenant_a)
        _cleanup(store._conn, tenant_b)


def test_organization_baseline_upsert_and_read(store: PostgresGovernanceStore) -> None:
    tenant_id = _tenant()
    try:
        signals = SignalSet().with_signal(
            Signal(key="employee_count", value_type=ValueType.NUMERIC, value=15)
        )
        store.upsert_organization_baseline(
            tenant_id, ("pack:core", "pack:technology"), signals, now=1000.0
        )

        result = store.get_organization_baseline(tenant_id)
        assert result is not None
        fetched_signals, active_packs = result
        assert fetched_signals.value("employee_count") == 15
        assert set(active_packs) == {"pack:core", "pack:technology"}

        # A later conclusion overwrites the baseline (not accumulates).
        newer_signals = SignalSet().with_signal(
            Signal(key="employee_count", value_type=ValueType.NUMERIC, value=42)
        )
        store.upsert_organization_baseline(tenant_id, ("pack:core",), newer_signals, now=2000.0)
        fetched_signals2, active_packs2 = store.get_organization_baseline(tenant_id)
        assert fetched_signals2.value("employee_count") == 42
        assert active_packs2 == ("pack:core",)
    finally:
        _cleanup(store._conn, tenant_id)  # noqa: SLF001
