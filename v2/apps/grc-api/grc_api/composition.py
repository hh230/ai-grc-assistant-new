"""How the host composes storage (ADR 0052 — the composition root; ADR 0053 — the read models;
ADR 0055 — the transaction boundary is the **command**).

**The property this module exists to hold:**

> No durable store lives in the application. Only factories live; each creates a store for one
> operation, and it is gone when the operation ends.

A `Store` has no business owning a lifetime — a *connection* owns one, and a `UnitOfWork` owns the
transaction around it. If the long-lived object were a store, then sooner or later someone would put
a `PostgresMissionStore` on `app.state` because "it's just a store", and the command-owned boundary
would quietly become a process-wide one. There is no such object here to share.

So the two sides are composed differently, on purpose:

- **Reads** go through a long-lived *reader service* that holds configuration, not state. Each
  `get` opens its own short connection, builds a store for that one read, and disposes both. It
  carries no transaction because a read is not a write.
- **Writes** go through a *command scope factory*. Opening a scope creates the `UnitOfWork` and,
  bound to its single connection, the mission store, the outbox sink, and the projection — the
  three participants ADR 0055 names. The command runs inside; on clean exit they commit together, on
  an exception they roll back together. Then all of it is discarded.

Two further decisions kept from the read-model wiring:

- **Production defaults to durable; a test declares its environment** (`storage=Storage.MEMORY`).
- **Nothing here creates schema.** A store that is asked to write does not build its own tables.
  Migrations are a deployment concern and land in their own change; the DDL already exists as
  `mission-store/migrations/*.sql` and `*_read_model.create_table_sql`.
"""

from __future__ import annotations

import contextlib
import enum
import os
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

from document_read_model import InMemoryDocumentReadModel, PostgresDocumentReadModel
from document_read_model.schema import DEFAULT_TABLE as DOCUMENTS_TABLE
from event_bus import ALL_EVENTS, InProcessEventBus
from mission_engine import MissionEngine
from mission_read_model import InMemoryMissionListReadModel, PostgresMissionListReadModel
from mission_read_model.schema import DEFAULT_TABLE as MISSIONS_VIEW_TABLE
from mission_store import OutboxSink, PostgresMissionStore, UnitOfWork
from mission_store.config import TABLE as MISSIONS_TABLE
from mission_store.config import dsn as default_dsn
from mission_store.outbox_schema import OUTBOX_TABLE

from grc_api.launch import (
    MissionLaunchPort,
)

DSN_ENV_VAR = "MISSION_STORE_DSN"


def database_dsn() -> str:
    """The V2 database. One setting configures the missions, the outbox and the read models, so they
    cannot drift into different databases."""
    return os.environ.get(DSN_ENV_VAR) or default_dsn()


class Storage(str, enum.Enum):
    """Which adapters the app is built with. There is no "unspecified": production defaults to
    `DURABLE`, and a test that wants `MEMORY` says so."""

    DURABLE = "durable"
    MEMORY = "memory"


@dataclass(frozen=True)
class Tables:
    """Where the durable composition writes. Overridable so a test can point the *host itself* at
    throwaway tables instead of handing it a pre-built store — which is what lets a test observe the
    real composition rather than a substitute for it."""

    missions: str = MISSIONS_TABLE
    outbox: str = OUTBOX_TABLE
    missions_view: str = MISSIONS_VIEW_TABLE
    documents_view: str = DOCUMENTS_TABLE


def _connect(*, autocommit: bool) -> Any:
    import psycopg

    return psycopg.connect(database_dsn(), autocommit=autocommit)


def open_autocommit_connection() -> Any:
    """A fresh autocommit connection to the V2 database — the seam the durable launch opens its own
    connection through, so execution never borrows the command's."""
    return _connect(autocommit=True)


# --- reads: a service that holds configuration, never a store -----------------------------


class DurableMissionReader:
    """Loads a mission for the read side. Owns **no** store and **no** connection: it creates both
    for the one read and disposes them, so nothing durable outlives the call. Autocommit, because a
    read carries no transaction."""

    def __init__(self, table: str) -> None:
        self._table = table

    def get(self, mission_id: str, tenant: Any) -> Any:
        connection = _connect(autocommit=True)
        try:
            store = PostgresMissionStore(connection=connection, table=self._table)
            return store.get(mission_id, tenant)
        finally:
            connection.close()


class _LazyAdapter:
    """Defers construction to first use, so importing the package never opens a connection —
    `grc_api.app` builds a module-level `app = create_app()` for uvicorn, and that import must work
    without a database. Forwards everything; holds no behaviour of its own."""

    def __init__(self, factory: Callable[[], Any], *, name: str) -> None:
        self._factory = factory
        self._name = name
        self._inner: Any | None = None

    def __getattr__(self, attribute: str) -> Any:
        if self._inner is None:
            self._inner = self._factory()
        return getattr(self._inner, attribute)

    def __repr__(self) -> str:
        return f"<durable {self._name} ({'connected' if self._inner else 'not yet connected'})>"


def build_mission_read_model(storage: Storage, tables: Tables) -> Any:
    if storage is Storage.MEMORY:
        return InMemoryMissionListReadModel()
    return _LazyAdapter(
        lambda: PostgresMissionListReadModel(dsn=database_dsn(), table=tables.missions_view),
        name="mission read model",
    )


def build_document_read_model(storage: Storage, tables: Tables) -> Any:
    if storage is Storage.MEMORY:
        return InMemoryDocumentReadModel()
    return _LazyAdapter(
        lambda: PostgresDocumentReadModel(dsn=database_dsn(), table=tables.documents_view),
        name="document read model",
    )


# --- writes: a factory that creates one transaction's worth of collaborators ---------------


@dataclass
class CommandScope:
    """One command's transactional world. Every participant here shares a single connection, so the
    mission write, its events and its projection commit together or not at all (ADR 0055).

    `launches` is the buffer the workflow appends to when a command asks to *start execution*. The
    scope does not run them — it fires them through the `MissionLaunchPort` **after** the
    transaction commits — which is what makes "the command owns the transaction, not progress"
    true."""

    engine: Any
    store: Any
    mission_read_model: Any
    launches: list[tuple[str, Any]] = field(default_factory=list)


CommandScopeFactory = Callable[[], "contextlib.AbstractContextManager[CommandScope]"]


def durable_command_scope_factory(
    executor: Any, tables: Tables, launch: MissionLaunchPort
) -> CommandScopeFactory:
    """The write side in production: a factory, and nothing else, lives in the app.

    Each scope opens a connection, wraps it in a `UnitOfWork`, and binds to that one connection the
    mission store, an `OutboxSink` subscribed to the engine's event bus, and the mission read model.
    Clean exit commits all three; an exception rolls back all three. **Then**, and only after the
    commit, any launch the command recorded is fired through the `MissionLaunchPort` — so execution
    starts outside the committed transaction, never inside it. A rolled-back command fires nothing.
    """

    @contextlib.contextmanager
    def scope() -> Iterator[CommandScope]:
        connection = _connect(autocommit=False)
        active: CommandScope | None = None
        try:
            with UnitOfWork(connection=connection) as unit:
                store = PostgresMissionStore(connection=unit.connection, table=tables.missions)
                # Synchronous capture bus: the sink writes inside this transaction, not after it.
                capture = InProcessEventBus()
                capture.subscribe(
                    ALL_EVENTS,
                    OutboxSink(connection=unit.connection, table=tables.outbox).write,
                )
                active = CommandScope(
                    engine=MissionEngine(store, executor, events=capture),
                    store=store,
                    mission_read_model=PostgresMissionListReadModel(
                        connection=unit.connection, table=tables.missions_view
                    ),
                )
                yield active
            # Reached only on a clean commit; a rollback raises out of the `with` and skips this.
            for mission_id, tenant in active.launches:
                launch.launch(mission_id, tenant)
        finally:
            connection.close()

    return scope


def memory_command_scope_factory(
    engine: Any, store: Any, mission_read_model: Any, launch: MissionLaunchPort
) -> CommandScopeFactory:
    """The in-memory equivalent: the same seam, no transaction. Launches still fire through the Port
    after the (no-op) scope, so a test exercises the same command→launch boundary as production."""

    @contextlib.contextmanager
    def scope() -> Iterator[CommandScope]:
        active = CommandScope(engine=engine, store=store, mission_read_model=mission_read_model)
        yield active
        for mission_id, tenant in active.launches:
            launch.launch(mission_id, tenant)

    return scope
