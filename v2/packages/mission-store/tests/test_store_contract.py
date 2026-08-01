"""The behavioural contract of `MissionStorePort`, run against **both** implementations — the
reference `InMemoryMissionStore` and `PostgresMissionStore`. This is the real proof of drop-in
equivalence (ADR 0043 §4, §13): the same assertions must hold for both. The Postgres
parametrization auto-skips when no database is reachable, so the in-memory contract still runs
anywhere.

Only the semantics *both* stores guarantee live here. Postgres-specific guarantees (DB-level
unique-index enforcement, cross-tenant overwrite refusal, revision increments) are in
`test_postgres_integration.py` — they are not part of the shared port contract because the
in-memory store is safe by different construction.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from mission_engine import InMemoryMissionStore, Mission, MissionStorePort, single_step_plan
from mission_store import PostgresMissionStore
from mission_store.config import dsn
from pipeline_contracts import TenantContext


@pytest.fixture(params=["inmemory", "postgres"])
def store(request: pytest.FixtureRequest) -> Iterator[MissionStorePort]:
    """Yield each store implementation in turn. Postgres runs on a throwaway table and auto-skips
    without a reachable database."""
    if request.param == "inmemory":
        yield InMemoryMissionStore()
        return

    psycopg = pytest.importorskip("psycopg")
    from mission_store.schema import apply_schema

    try:
        conn = psycopg.connect(dsn(), autocommit=True, connect_timeout=3)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"no reachable PostgreSQL ({exc})")
    table = f"missions_ct_{uuid.uuid4().hex[:8]}"
    apply_schema(conn, table)
    try:
        yield PostgresMissionStore(connection=conn, table=table)
    finally:
        conn.execute(f"DROP TABLE IF EXISTS {table}")
        conn.close()


def test_save_then_get_round_trips(store: MissionStorePort, rich_mission: Mission, tenant) -> None:
    store.save(rich_mission)
    restored = store.get(rich_mission.id, tenant)
    assert restored is not None
    assert restored.to_dict() == rich_mission.to_dict()
    assert [p.version for p in restored.plan_versions] == [
        p.version for p in rich_mission.plan_versions
    ]


def test_get_is_tenant_scoped(store: MissionStorePort, rich_mission, tenant, other_tenant) -> None:
    store.save(rich_mission)
    assert store.get(rich_mission.id, other_tenant) is None  # a foreign tenant cannot read it
    assert store.get(rich_mission.id, tenant) is not None


def test_get_missing_returns_none(store: MissionStorePort, tenant) -> None:
    assert store.get("mis_does_not_exist", tenant) is None


def test_find_by_idempotency_key_is_tenant_scoped(
    store: MissionStorePort, rich_mission, tenant, other_tenant
) -> None:
    store.save(rich_mission)  # idempotency_key == "k-rich"
    found = store.find_by_idempotency_key(tenant, "k-rich")
    assert found is not None and found.id == rich_mission.id
    assert store.find_by_idempotency_key(other_tenant, "k-rich") is None  # keys are per-tenant
    assert store.find_by_idempotency_key(tenant, "") is None  # empty key is never a key
    assert store.find_by_idempotency_key(tenant, "no-such-key") is None


def test_save_is_an_idempotent_upsert(store: MissionStorePort, tenant: TenantContext) -> None:
    """Saving the same mission id repeatedly across transitions yields one logical mission whose
    latest state is what `get` returns — an upsert, not an append."""
    mission = Mission.create(goal="g", tenant=tenant)
    store.save(mission)  # CREATED
    mission.set_plan(single_step_plan("do it"))
    store.save(mission)  # PLANNED — same id
    restored = store.get(mission.id, tenant)
    assert restored is not None
    assert restored.status.value == "planned"
    assert restored.plan is not None


def test_resaving_a_keyed_mission_is_not_a_conflict(
    store: MissionStorePort, tenant: TenantContext
) -> None:
    """Re-saving the SAME mission (same id) that carries an idempotency key, across lifecycle
    transitions, is a normal upsert — never an idempotency conflict. The conflict is only a
    *different* mission id reusing the same (tenant, key). Both stores must agree, so the Slice 2
    wrapping cannot misfire on legitimate re-saves."""
    mission = Mission.create(goal="g", tenant=tenant, idempotency_key="k1")
    store.save(mission)  # CREATED, keyed
    mission.set_plan(single_step_plan("do it"))
    store.save(mission)  # same id, same key — must not raise
    found = store.find_by_idempotency_key(tenant, "k1")
    assert found is not None and found.id == mission.id
    assert found.status.value == "planned"
