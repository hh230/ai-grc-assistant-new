"""Postgres-specific guarantees the store adds on top of the shared port contract — the ones the
in-memory store does not (and need not) replicate. DB-gated: connects to `MISSION_STORE_DSN`
(default: the isolated `rasheed_v2` dev DB) and **skips cleanly** when no database is reachable.

Each test stands the schema up on a throwaway `missions_it_*` table and drops it afterwards, so
nothing pollutes the canonical `missions` table and tests never collide.
"""

from __future__ import annotations

import uuid

import pytest

psycopg = pytest.importorskip("psycopg")

from mission_engine import (  # noqa: E402
    ApprovalRequest,
    EchoExecutor,
    Mission,
    MissionEngine,
    MissionStatus,
    Plan,
    PlanStep,
)
from mission_store import (  # noqa: E402
    IdempotencyConflict,
    MissionStoreError,
    PostgresMissionStore,
)
from mission_store.config import dsn  # noqa: E402
from mission_store.schema import apply_schema  # noqa: E402


def _connect():
    try:
        return psycopg.connect(dsn(), autocommit=True, connect_timeout=3)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"no reachable PostgreSQL ({exc})")


@pytest.fixture(scope="module")
def conn():
    c = _connect()
    yield c
    c.close()


@pytest.fixture
def table(conn):
    name = f"missions_it_{uuid.uuid4().hex[:8]}"
    apply_schema(conn, name)
    yield name
    conn.execute(f"DROP TABLE IF EXISTS {name}")


@pytest.fixture
def store(conn, table):
    return PostgresMissionStore(connection=conn, table=table)


# ── idempotency conflict: DB enforcement, wrapped as a typed error (Slice 2) ──
def test_duplicate_idempotency_key_raises_idempotency_conflict(store, tenant):
    """A *different* mission reusing this tenant's key trips the partial unique index; the store
    wraps the raw driver violation into IdempotencyConflict (ADR 0043 §9, §11)."""
    first = Mission.create(goal="a", tenant=tenant, idempotency_key="dup")
    second = Mission.create(
        goal="b", tenant=tenant, idempotency_key="dup"
    )  # different id, same key
    store.save(first)
    with pytest.raises(IdempotencyConflict) as exc_info:
        store.save(second)
    err = exc_info.value
    assert err.tenant_id == tenant.tenant_id
    assert err.idempotency_key == "dup"
    assert err.mission_id == second.id
    # the DB genuinely enforced it (cause preserved), and no raw driver exception escaped
    assert isinstance(err.__cause__, psycopg.errors.UniqueViolation)
    assert not isinstance(err, psycopg.Error)


def test_same_key_allowed_across_tenants(store, tenant, other_tenant):
    """Tenant isolation preserved exactly (ADR 0043 §9): the key is unique *per tenant*, so two
    tenants may reuse it without any conflict."""
    a = Mission.create(goal="a", tenant=tenant, idempotency_key="shared")
    b = Mission.create(goal="b", tenant=other_tenant, idempotency_key="shared")
    store.save(a)
    store.save(b)  # no violation: the unique index is (tenant_id, idempotency_key)
    assert store.find_by_idempotency_key(tenant, "shared").id == a.id
    assert store.find_by_idempotency_key(other_tenant, "shared").id == b.id


# ── tenant immutability (defence in depth) ────────────────────────────────────
def test_save_refuses_cross_tenant_overwrite(store, rich_mission, tenant, other_tenant):
    store.save(rich_mission)
    forged = Mission(
        id=rich_mission.id,
        tenant=other_tenant,
        goal="hijacked",
        trace_id="trc_forged",
        status=MissionStatus.CREATED,
        created_at=1.0,
        updated_at=1.0,
    )
    with pytest.raises(MissionStoreError):
        store.save(forged)
    original = store.get(rich_mission.id, tenant)
    assert original is not None and original.goal == "draft an access-control policy"


# ── store-managed revision ────────────────────────────────────────────────────
def test_revision_increments_on_each_update(store, conn, table, tenant):
    mission = Mission.create(goal="g", tenant=tenant)
    store.save(mission)  # insert → revision 0

    def revision() -> int:
        return conn.execute(
            f"SELECT revision FROM {table} WHERE id = %s", (mission.id,)
        ).fetchone()[0]

    assert revision() == 0
    store.save(mission)  # update → 1
    store.save(mission)  # update → 2
    assert revision() == 2


# ── lifecycle upsert, driven end-to-end by the engine ─────────────────────────
def test_engine_drives_a_mission_to_a_single_completed_row(store, conn, table, tenant):
    engine = MissionEngine(store, EchoExecutor())
    mission = engine.run_simple("MFA lookup", tenant, "what does NCA ECC say about MFA?")

    reloaded = store.get(mission.id, tenant)
    assert reloaded is not None
    assert reloaded.status is MissionStatus.COMPLETED
    assert len(reloaded.step_results) == 1
    count = conn.execute(f"SELECT count(*) FROM {table} WHERE id = %s", (mission.id,)).fetchone()[0]
    assert count == 1  # upsert, not append


# ── ADR 0044 Slice 1: a paused mission's ApprovalRequest survives save → reload ──
def test_pending_approval_survives_save_and_reload(store, tenant):
    """The persistence proof for Slice 1: a mission paused at a gate is durably stored WITH its
    `ApprovalRequest`, and a reload (`get` — the same read a resume uses) returns it unchanged. No
    approve/reject, no resume logic — only that the data round-trips through real PostgreSQL."""
    mission = Mission.create(goal="draft an access-control policy", tenant=tenant)
    mission.set_plan(
        Plan(steps=(PlanStep(description="author", instruction="write", consequential=True),))
    )
    mission.begin_execution()
    request = ApprovalRequest(
        reason="writes an access-control policy", requested_by="mission", requested_at=7.0
    )
    mission.await_approval(request)

    store.save(mission)
    reloaded = store.get(mission.id, tenant)

    assert reloaded is not None
    assert reloaded.status is MissionStatus.AWAITING_APPROVAL
    assert reloaded.approval == request  # every field of the request survived the round-trip
    assert reloaded.approval is not None and reloaded.approval.is_pending
    assert reloaded.has_active_approval


# ── migration idempotency ─────────────────────────────────────────────────────
def test_apply_schema_is_idempotent(conn):
    name = f"missions_idem_{uuid.uuid4().hex[:8]}"
    try:
        apply_schema(conn, name)
        apply_schema(conn, name)  # second application must not error (IF NOT EXISTS)
        row = conn.execute(f"SELECT count(*) FROM {name}").fetchone()
        assert row[0] == 0
    finally:
        conn.execute(f"DROP TABLE IF EXISTS {name}")
