"""How the host chooses its read-model adapters (ADR 0052 — the composition root; ADR 0053 — the
read models).

Two separate decisions live here, and they must not be solved with each other:

- **Production defaults to durable.** A deployment that configures nothing gets PostgreSQL, never an
  in-memory projection that loses a tenant's work on restart. Fail safe, not open.
- **A test declares the environment it wants.** `create_app(storage=Storage.MEMORY)` is how a suite
  says "in-memory", explicitly, once. Nothing is inferred from context, so a new test cannot inherit
  an assumption it never made.

**Why construction is deferred.** `Postgres*ReadModel` connects inside `__init__`, and `grc_api.app`
builds a module-level `app = create_app()` so `uvicorn grc_api.app:app` works. Wiring the durable
adapters eagerly would open a database connection at **import** time, making the package impossible
to import without a reachable PostgreSQL. `_LazyReadModel` defers the connection to the first call.

**What this module does NOT do: schema.** A read model that is asked to read does not create its own
table. Bringing the schema into existence is a *migration* — a bootstrap/deploy responsibility, not
a side effect of a first read. (An earlier draft applied `CREATE TABLE IF NOT EXISTS` on connect; a
test run then quietly created canonical tables in a live database. That is precisely the class of
side effect a migration exists to make deliberate.) The DDL is available as
`mission_read_model.create_table_sql` / `document_read_model.create_table_sql` for whatever applies
it; wiring a runner is its own change, not this one.
"""

from __future__ import annotations

import enum
import os
from collections.abc import Callable
from typing import Any

from document_read_model import InMemoryDocumentReadModel, PostgresDocumentReadModel
from document_read_model.schema import DEFAULT_TABLE as DOCUMENTS_TABLE
from mission_read_model import InMemoryMissionListReadModel, PostgresMissionListReadModel
from mission_read_model.schema import DEFAULT_TABLE as MISSIONS_TABLE

# The V2 database. Shares `MISSION_STORE_DSN` with the Core store on purpose: the read models and
# the missions they project live in one database, so one setting configures both and they cannot
# drift apart. (The literal is duplicated from `mission_store.config` for exactly one commit —
# `mission-store` is still a dev-only dependency here; the store commit promotes it and this
# collapses into an import.)
DSN_ENV_VAR = "MISSION_STORE_DSN"
DEFAULT_DSN = "postgresql://postgres:postgres@localhost:5432/rasheed_v2"


def database_dsn() -> str:
    return os.environ.get(DSN_ENV_VAR, DEFAULT_DSN)


class Storage(str, enum.Enum):
    """Which read-model adapters the app is built with. There is no "unspecified": production
    defaults to `DURABLE`, and a test that wants `MEMORY` says so."""

    DURABLE = "durable"
    MEMORY = "memory"


class _LazyReadModel:
    """A read model that builds itself on first use.

    Every call is forwarded to the real adapter, so this satisfies the same port and is invisible to
    the routes. It holds no behaviour of its own — it exists only to move a connection out of import
    time. `__getattr__` fires for every port method because this class defines none of them.
    """

    def __init__(self, factory: Callable[[], Any], *, name: str) -> None:
        self._factory = factory
        self._name = name
        self._inner: Any | None = None

    def _resolve(self) -> Any:
        if self._inner is None:
            self._inner = self._factory()
        return self._inner

    def __getattr__(self, attribute: str) -> Any:
        return getattr(self._resolve(), attribute)

    def __repr__(self) -> str:
        state = "connected" if self._inner is not None else "not yet connected"
        return f"<durable {self._name} ({state})>"


def build_mission_read_model(storage: Storage, table: str = MISSIONS_TABLE) -> Any:
    """The Mission List projection for this environment."""
    if storage is Storage.MEMORY:
        return InMemoryMissionListReadModel()
    return _LazyReadModel(
        lambda: PostgresMissionListReadModel(dsn=database_dsn(), table=table),
        name="mission read model",
    )


def build_document_read_model(storage: Storage, table: str = DOCUMENTS_TABLE) -> Any:
    """The Document projection for this environment."""
    if storage is Storage.MEMORY:
        return InMemoryDocumentReadModel()
    return _LazyReadModel(
        lambda: PostgresDocumentReadModel(dsn=database_dsn(), table=table),
        name="document read model",
    )
