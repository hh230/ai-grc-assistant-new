"""Exercise the store's query-construction and reconstruction paths **without a live database**,
using a recording fake connection. Covers what the DB-gated suites otherwise witness alone: the
upsert shape (tenant guard + revision increment), JSONB wrapping, `payload_schema_version` in the
params, the tenant-scoped read predicates, the empty-key short-circuit, and row→aggregate rebuild.
"""

from __future__ import annotations

import pytest

psycopg = pytest.importorskip("psycopg")  # the store wraps JSONB via psycopg's adapter

from mission_engine import Mission  # noqa: E402
from mission_store import (  # noqa: E402
    IdempotencyConflict,
    MissionStoreError,
    PostgresMissionStore,
)
from mission_store.codec import COLUMNS, mission_to_row  # noqa: E402
from psycopg.types.json import Jsonb  # noqa: E402


class _RecordingCursor:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows
        self.executed: list[tuple[str, object]] = []

    def __enter__(self) -> _RecordingCursor:
        return self

    def __exit__(self, *exc: object) -> bool:
        return False

    def execute(self, sql: str, params: object = None) -> _RecordingCursor:
        self.executed.append((sql, params))
        return self

    def fetchone(self) -> dict | None:
        return self._rows.pop(0) if self._rows else None


class _RecordingConnection:
    """Records every statement and returns canned rows/rowcount, so store logic runs with no DB."""

    def __init__(self, *, rowcount: int = 1, rows: list[dict] | None = None) -> None:
        self._rowcount = rowcount
        self._rows = rows or []
        self.write_calls: list[tuple[str, dict]] = []
        self.cursors: list[_RecordingCursor] = []

    def execute(self, sql: str, params: dict | None = None):  # save()'s path
        self.write_calls.append((sql, params or {}))
        return type("R", (), {"rowcount": self._rowcount})()

    def cursor(self, row_factory=None) -> _RecordingCursor:  # get()/find()'s path
        cur = _RecordingCursor(list(self._rows))
        self.cursors.append(cur)
        return cur


def test_save_builds_a_tenant_guarded_upsert_that_bumps_revision(rich_mission: Mission) -> None:
    conn = _RecordingConnection(rowcount=1)
    PostgresMissionStore(connection=conn, table="missions").save(rich_mission)

    sql, params = conn.write_calls[0]
    assert "INSERT INTO missions" in sql
    assert "ON CONFLICT (id) DO UPDATE SET" in sql
    assert "revision = missions.revision + 1" in sql  # store-managed write counter
    assert "row_updated_at = now()" in sql
    assert "WHERE missions.tenant_id = EXCLUDED.tenant_id" in sql  # the cross-tenant guard
    assert set(params.keys()) == set(COLUMNS)
    assert params["tenant_id"] == "org_acme"
    assert params["payload_schema_version"] == 2  # ADR 0044 Slice 1 bumped the write version 1 → 2
    # `rich_mission` has no active gate, so its approval column is a plain NULL (not JSONB-wrapped).
    assert params["approval"] is None
    for col in ("roles", "plan", "plan_versions", "step_results"):
        assert isinstance(params[col], Jsonb), col
    assert not isinstance(params["goal"], Jsonb)


def test_save_rejects_a_blocked_cross_tenant_overwrite(rich_mission: Mission) -> None:
    conn = _RecordingConnection(rowcount=0)  # the tenant guard matched no row
    with pytest.raises(MissionStoreError):
        PostgresMissionStore(connection=conn, table="missions").save(rich_mission)


class _UniqueViolationConnection(_RecordingConnection):
    """A connection whose write raises the driver's uniqueness violation — simulates the partial
    unique index tripping, so the wrapping is provable without a live database."""

    def execute(self, sql: str, params: dict | None = None):
        raise psycopg.errors.UniqueViolation("duplicate key value violates unique constraint")


def test_save_wraps_unique_violation_as_idempotency_conflict(rich_mission: Mission) -> None:
    conn = _UniqueViolationConnection()
    with pytest.raises(IdempotencyConflict) as exc_info:
        PostgresMissionStore(connection=conn, table="missions").save(rich_mission)
    err = exc_info.value
    # the typed error carries the collision's scope, and the raw driver error is preserved as cause
    assert err.tenant_id == "org_acme"
    assert err.idempotency_key == "k-rich"
    assert err.mission_id == rich_mission.id
    assert isinstance(err.__cause__, psycopg.errors.UniqueViolation)
    # and crucially: no raw driver exception escapes to the caller
    assert not isinstance(err, psycopg.Error)


def test_get_filters_by_id_and_tenant_and_reconstructs(rich_mission, tenant) -> None:
    conn = _RecordingConnection(rows=[mission_to_row(rich_mission)])
    restored = PostgresMissionStore(connection=conn, table="missions").get(rich_mission.id, tenant)
    sql, params = conn.cursors[0].executed[0]
    assert "WHERE id = %(id)s AND tenant_id = %(tenant_id)s" in sql
    assert params == {"id": rich_mission.id, "tenant_id": "org_acme"}
    assert restored is not None
    assert restored.to_dict() == rich_mission.to_dict()


def test_get_returns_none_when_absent(tenant) -> None:
    conn = _RecordingConnection(rows=[])
    assert PostgresMissionStore(connection=conn, table="missions").get("mis_x", tenant) is None


def test_find_by_empty_key_short_circuits_without_touching_the_db(tenant) -> None:
    conn = _RecordingConnection(rows=[])
    store = PostgresMissionStore(connection=conn, table="missions")
    assert store.find_by_idempotency_key(tenant, "") is None
    assert conn.cursors == []  # never queried


def test_find_by_key_filters_by_tenant_and_key(rich_mission, tenant) -> None:
    conn = _RecordingConnection(rows=[mission_to_row(rich_mission)])
    found = PostgresMissionStore(connection=conn, table="missions").find_by_idempotency_key(
        tenant, "k-rich"
    )
    sql, params = conn.cursors[0].executed[0]
    assert "WHERE tenant_id = %(tenant_id)s AND idempotency_key = %(key)s" in sql
    assert params == {"tenant_id": "org_acme", "key": "k-rich"}
    assert found is not None and found.id == rich_mission.id
