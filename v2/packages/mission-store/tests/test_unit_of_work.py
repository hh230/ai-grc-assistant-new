"""Slice 3 — the `UnitOfWork` transaction boundary (ADR 0043 §8).

Two tiers, mirroring the rest of the package:

- **Driver-free tests** drive the lifecycle with a recording `_FakeConnection`, so every rule —
  commit, rollback, autocommit rejection, the single-use state machine, and owned-vs-injected
  disposal — is proven without a database (owned mode is exercised by monkeypatching
  `psycopg.connect`).
- **DB-gated tests** (auto-skip without a reachable Postgres, exactly like the other suites) prove
  the real transactional semantics against Postgres: read-your-writes inside the transaction,
  invisibility before commit, visibility after commit, rollback discarding writes, and an
  `IdempotencyConflict` inside the block rolling the whole unit back atomically.

The store is never asked to commit or roll back in any of these; the UnitOfWork owns that.
"""

from __future__ import annotations

import uuid

import pytest

psycopg = pytest.importorskip("psycopg")

from mission_engine import Mission  # noqa: E402
from mission_store import (  # noqa: E402
    IdempotencyConflict,
    PostgresMissionStore,
    UnitOfWork,
    UnitOfWorkError,
)
from mission_store.config import dsn  # noqa: E402
from mission_store.schema import apply_schema  # noqa: E402


class _FakeConnection:
    """A minimal stand-in for psycopg's connection: records commit/rollback/close and carries an
    autocommit flag, so the UnitOfWork's lifecycle is provable with no live database."""

    def __init__(self, *, autocommit: bool = False) -> None:
        self.autocommit = autocommit
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def close(self) -> None:
        self.closed = True


# ── commit / rollback happy paths ─────────────────────────────────────────────
def test_commit_commits_the_connection() -> None:
    fake = _FakeConnection()
    uow = UnitOfWork(connection=fake)
    uow.begin()
    uow.commit()
    assert fake.commits == 1 and fake.rollbacks == 0


def test_rollback_rolls_back_the_connection() -> None:
    fake = _FakeConnection()
    uow = UnitOfWork(connection=fake)
    uow.begin()
    uow.rollback()
    assert fake.rollbacks == 1 and fake.commits == 0


def test_context_manager_commits_on_clean_exit() -> None:
    fake = _FakeConnection()
    with UnitOfWork(connection=fake) as uow:
        assert uow.connection is fake
    assert fake.commits == 1 and fake.rollbacks == 0


def test_exception_in_block_rolls_back_and_propagates() -> None:
    fake = _FakeConnection()
    with pytest.raises(RuntimeError, match="boom"), UnitOfWork(connection=fake) as uow:
        _ = uow.connection
        raise RuntimeError("boom")
    assert fake.rollbacks == 1 and fake.commits == 0


# ── connection ownership: owned vs injected ───────────────────────────────────
def test_owned_connection_is_opened_non_autocommit_and_closed_on_exit(monkeypatch) -> None:
    fake = _FakeConnection()
    created: dict[str, object] = {}

    def fake_connect(conninfo, *, autocommit):
        created["conninfo"] = conninfo
        created["autocommit"] = autocommit
        return fake

    monkeypatch.setattr(psycopg, "connect", fake_connect)
    with UnitOfWork(dsn="postgresql://unit/of/work") as uow:
        assert uow.connection is fake
    assert created["autocommit"] is False  # owned connection is opened with autocommit off
    assert created["conninfo"] == "postgresql://unit/of/work"
    assert fake.commits == 1  # clean exit commits
    assert fake.closed is True  # the UoW owns and disposes the connection it opened


def test_injected_connection_is_never_closed() -> None:
    fake = _FakeConnection(autocommit=False)
    with UnitOfWork(connection=fake) as uow:
        assert uow.connection is fake
    assert fake.commits == 1
    assert fake.closed is False  # the caller owns the injected connection's lifetime


def test_owned_connection_is_disposed_even_on_error(monkeypatch) -> None:
    fake = _FakeConnection()
    monkeypatch.setattr(psycopg, "connect", lambda conninfo, *, autocommit: fake)
    with pytest.raises(RuntimeError), UnitOfWork(dsn="x") as uow:
        _ = uow.connection
        raise RuntimeError("fail")
    assert fake.rollbacks == 1
    assert fake.closed is True  # owned connection disposed on the failure path too


def test_owned_uow_never_begun_opens_no_connection(monkeypatch) -> None:
    calls = {"n": 0}

    def fake_connect(conninfo, *, autocommit):  # pragma: no cover - must never run
        calls["n"] += 1
        return _FakeConnection()

    monkeypatch.setattr(psycopg, "connect", fake_connect)
    UnitOfWork(dsn="x")  # constructed but never begun
    assert calls["n"] == 0  # connection acquisition is lazy, in begin()


# ── autocommit rule: fatal for an injected connection ─────────────────────────
def test_injected_autocommit_connection_is_rejected_immediately() -> None:
    fake = _FakeConnection(autocommit=True)
    with pytest.raises(UnitOfWorkError, match="autocommit"):
        UnitOfWork(connection=fake)  # fails at construction, before any begin()


# ── single-use state machine: illegal transitions all raise ───────────────────
def test_begin_twice_is_an_error() -> None:
    uow = UnitOfWork(connection=_FakeConnection())
    uow.begin()
    with pytest.raises(UnitOfWorkError):
        uow.begin()


def test_commit_twice_is_an_error() -> None:
    fake = _FakeConnection()
    uow = UnitOfWork(connection=fake)
    uow.begin()
    uow.commit()
    with pytest.raises(UnitOfWorkError):
        uow.commit()
    assert fake.commits == 1  # the illegal second commit did not reach the connection


def test_rollback_twice_is_an_error() -> None:
    fake = _FakeConnection()
    uow = UnitOfWork(connection=fake)
    uow.begin()
    uow.rollback()
    with pytest.raises(UnitOfWorkError):
        uow.rollback()
    assert fake.rollbacks == 1


def test_commit_after_rollback_is_an_error() -> None:
    fake = _FakeConnection()
    uow = UnitOfWork(connection=fake)
    uow.begin()
    uow.rollback()
    with pytest.raises(UnitOfWorkError):
        uow.commit()
    assert fake.commits == 0


def test_rollback_after_commit_is_an_error() -> None:
    fake = _FakeConnection()
    uow = UnitOfWork(connection=fake)
    uow.begin()
    uow.commit()
    with pytest.raises(UnitOfWorkError):
        uow.rollback()
    assert fake.rollbacks == 0


def test_commit_before_begin_is_an_error() -> None:
    with pytest.raises(UnitOfWorkError):
        UnitOfWork(connection=_FakeConnection()).commit()


def test_object_is_single_use() -> None:
    uow = UnitOfWork(connection=_FakeConnection())
    uow.begin()
    uow.commit()
    with pytest.raises(UnitOfWorkError):
        uow.begin()  # terminal state — not reusable


# ── connection handle is valid only inside the active window ──────────────────
def test_connection_is_unavailable_before_begin_and_after_commit() -> None:
    fake = _FakeConnection()
    uow = UnitOfWork(connection=fake)
    with pytest.raises(UnitOfWorkError):
        _ = uow.connection  # before begin
    uow.begin()
    assert uow.connection is fake  # active
    uow.commit()
    with pytest.raises(UnitOfWorkError):
        _ = uow.connection  # after commit


def test_close_is_idempotent_and_leaves_injected_connection_open() -> None:
    fake = _FakeConnection()
    uow = UnitOfWork(connection=fake)
    uow.begin()
    uow.commit()
    uow.close()
    uow.close()  # second close must not raise or double-act
    assert fake.closed is False  # injected: never closed by the UoW


# ─────────────────────────── DB-gated integration ────────────────────────────
# These prove the *real* transactional semantics against Postgres, and auto-skip without a DB,
# exactly like the other suites. An autocommit `observer` connection witnesses external visibility;
# the UoW's writer connection carries the transaction.


def _connect(**kw):
    try:
        return psycopg.connect(dsn(), connect_timeout=3, **kw)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"no reachable PostgreSQL ({exc})")


def _count(conn, table: str, mission_id: str) -> int:
    return conn.execute(
        f"SELECT count(*) FROM {table} WHERE id = %s", (mission_id,)
    ).fetchone()[0]


@pytest.fixture
def observer():
    c = _connect(autocommit=True)
    yield c
    c.close()


@pytest.fixture
def uow_table(observer):
    name = f"missions_uow_{uuid.uuid4().hex[:8]}"
    apply_schema(observer, name)
    yield name
    observer.execute(f"DROP TABLE IF EXISTS {name}")


def test_read_your_writes_and_commit_visibility(observer, uow_table, tenant) -> None:
    writer = _connect(autocommit=False)
    try:
        mission = Mission.create(goal="g", tenant=tenant)
        with UnitOfWork(connection=writer) as uow:
            store = PostgresMissionStore(connection=uow.connection, table=uow_table)
            store.save(mission)
            # read-your-writes: the same transaction sees its own not-yet-committed write
            assert store.get(mission.id, tenant) is not None
            # invisible before commit: a separate connection sees nothing yet
            assert _count(observer, uow_table, mission.id) == 0
        # visible after commit
        assert _count(observer, uow_table, mission.id) == 1
    finally:
        writer.close()


def test_rollback_discards_all_writes(observer, uow_table, tenant) -> None:
    writer = _connect(autocommit=False)
    try:
        mission = Mission.create(goal="g", tenant=tenant)
        with pytest.raises(RuntimeError, match="fail after write"), UnitOfWork(
            connection=writer
        ) as uow:
            store = PostgresMissionStore(connection=uow.connection, table=uow_table)
            store.save(mission)
            raise RuntimeError("fail after write")
        assert _count(observer, uow_table, mission.id) == 0  # nothing persisted
        assert not writer.closed  # injected connection stays open and reusable
    finally:
        writer.close()


def test_idempotency_conflict_inside_transaction_rolls_back_atomically(
    observer, uow_table, tenant
) -> None:
    writer = _connect(autocommit=False)
    try:
        first = Mission.create(goal="a", tenant=tenant, idempotency_key="dup")
        second = Mission.create(goal="b", tenant=tenant, idempotency_key="dup")  # same key, new id
        with pytest.raises(IdempotencyConflict), UnitOfWork(connection=writer) as uow:
            store = PostgresMissionStore(connection=uow.connection, table=uow_table)
            store.save(first)  # ok
            store.save(second)  # trips the partial unique index → IdempotencyConflict
        # the conflict propagated out → the UoW rolled the whole unit back → NOTHING persisted,
        # not even `first` (all-or-nothing), and the connection is clean and reusable afterwards
        assert _count(observer, uow_table, first.id) == 0
        assert _count(observer, uow_table, second.id) == 0
        assert not writer.closed
        assert writer.execute("SELECT 1").fetchone()[0] == 1  # transaction cleanup verified
    finally:
        writer.close()


def test_owned_mode_commit_persists(observer, uow_table, tenant) -> None:
    mission = Mission.create(goal="g", tenant=tenant)
    with UnitOfWork(dsn=dsn()) as uow:  # the UoW opens and owns its own connection
        store = PostgresMissionStore(connection=uow.connection, table=uow_table)
        store.save(mission)
    assert _count(observer, uow_table, mission.id) == 1
