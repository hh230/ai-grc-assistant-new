"""`UnitOfWork` — the transaction boundary behind the frozen `MissionStorePort` (ADR 0043 §8,
Slice 3).

Slice 1/2 gave `PostgresMissionStore` a constructor-injected connection but treated it as a
*test/embedding affordance* running in autocommit: each `save`/`get` was its own durable
statement, and no caller could group several writes into one atomic unit. This slice adds the
object that owns that group — **a single flat transaction over one connection** — without adding
a single method to the store or the port.

The division of labour is deliberate and total:

- **The store** executes SQL, serializes, and deserializes. It never begins, commits, or rolls
  back a transaction. (Its Slice-1 owned mode still runs autocommit; that path is untouched.)
- **The `UnitOfWork`** owns `BEGIN` / `COMMIT` / `ROLLBACK` and the connection's lifecycle. It
  owns **no stores**: it exposes only the `connection`, which the caller binds a store to.

        with UnitOfWork(dsn=...) as uow:
            mission_store = PostgresMissionStore(connection=uow.connection)
            mission_store.save(mission)          # not yet durable
        # clean exit commits; an exception rolls back — the store did neither

Because every participant shares the one `connection`, a future transactional outbox, approval
write, or mission lease (all out of scope here) becomes *atomic* with the mission write by
construction — a second store bound to the same `uow.connection`, no change to this class.

Design rules this class enforces (all from the approved Slice-3 review):

- **Two connection modes.** *Owned* — the UoW opens the connection (lazily, in `begin`) and
  closes it on disposal. *Injected* — the caller supplies the connection and owns its lifetime;
  the UoW **never** closes it.
- **Autocommit is fatal for an injected connection.** Autocommit destroys atomicity, so an
  injected `autocommit=True` connection is rejected **immediately**, at construction — never
  silently tolerated. (An owned connection is opened with `autocommit=False`, so it cannot occur.)
- **Single flat transaction, single use.** No savepoints, no nesting, no re-entrant `begin`.
  `begin`/`commit`/`rollback` each fire at most once and only from the one legal state; a second
  `begin`, a second `commit`/`rollback`, a `commit` after `rollback` (or vice versa), or touching
  `connection` outside the active window is a loud `UnitOfWorkError`, never undefined behaviour.
- **No hidden state.** No globals, no contextvars, no ambient transaction, no implicit connection
  lookup — the connection is passed explicitly to every store.

The psycopg driver is imported **lazily** (only owned mode connects), so importing this module —
and the package — needs no driver, matching the store and the Retrieval Engine's pgvector adapter.
"""

from __future__ import annotations

import enum
from types import TracebackType
from typing import TYPE_CHECKING, Any, Literal

from mission_store.config import dsn as default_dsn
from mission_store.errors import MissionStoreError

if TYPE_CHECKING:  # type-only; the driver is never needed to import this module
    import psycopg


class UnitOfWorkError(MissionStoreError):
    """A `UnitOfWork` was misused or could not guarantee atomicity: an injected autocommit
    connection (which would silently defeat the transaction), or an illegal lifecycle step — a
    re-entrant `begin`, a double `commit`/`rollback`, a `commit` after `rollback`, or reaching for
    the `connection` outside an active transaction. A store operation's own failure is *not* this
    error; it surfaces as the store's `MissionStoreError`/`IdempotencyConflict`, and the UnitOfWork
    reacts by rolling back."""


class _State(enum.Enum):
    """The single-use lifecycle. Transitions are one-way: NEW → ACTIVE → (COMMITTED | ROLLED_BACK).
    There is no path back to ACTIVE — the object is not reusable."""

    NEW = "new"
    ACTIVE = "active"
    COMMITTED = "committed"
    ROLLED_BACK = "rolled_back"


class UnitOfWork:
    def __init__(
        self,
        *,
        dsn: str | None = None,
        connection: psycopg.Connection[Any] | None = None,
    ) -> None:
        """Create a unit of work in one of two connection modes.

        - **Owned** (no `connection`): the UoW opens its own connection in `begin` — lazily, so a
          UoW that is never begun never touches the database — and closes it on disposal. `dsn`
          selects the target (defaulting to the isolated V2 dev database, as the store does).
        - **Injected** (`connection` given): the caller's connection is used as-is and is the
          caller's to close; the UoW never closes it. It is rejected **now** if it is in
          autocommit mode, because autocommit makes `commit`/`rollback` no-ops and silently
          destroys the atomicity this object exists to provide.
        """
        self._owns_conn = connection is None
        self._dsn = dsn
        self._state = _State.NEW
        self._closed = False
        if connection is not None and connection.autocommit:
            # Fail immediately and loudly (ADR 0043 §8 autocommit rule): an autocommit connection
            # cannot carry a multi-statement transaction, so tolerating it would silently break
            # read-your-writes and all-or-nothing commit.
            raise UnitOfWorkError(
                "UnitOfWork was given an injected connection with autocommit=True; this destroys "
                "transaction atomicity. Pass a connection with autocommit=False."
            )
        self._conn: psycopg.Connection[Any] | None = connection

    # --- transaction lifecycle ----------------------------------------------------------

    def begin(self) -> UnitOfWork:
        """Start the transaction. In owned mode this opens the connection (autocommit off); in
        injected mode the connection already exists. psycopg begins the transaction implicitly on
        the first statement of a non-autocommit connection, so this method's job is to acquire the
        connection and mark the UoW active. Callable exactly once."""
        if self._state is not _State.NEW:
            raise UnitOfWorkError(
                f"begin() is only valid on a fresh UnitOfWork (state={self._state.value}); "
                "this object is single-use and cannot be re-begun."
            )
        if self._owns_conn:
            import psycopg  # lazy: only owned mode connects, so the module imports without a driver

            self._conn = psycopg.connect(self._dsn or default_dsn(), autocommit=False)
        self._state = _State.ACTIVE
        return self

    def commit(self) -> None:
        """Commit the transaction, making every write on the connection durable together. Legal
        only from the active state — a second commit, or a commit after rollback, is an error."""
        self._require_active("commit")
        assert self._conn is not None  # guaranteed by the ACTIVE state (set only after begin)
        self._conn.commit()
        self._state = _State.COMMITTED

    def rollback(self) -> None:
        """Roll the transaction back, discarding every write on the connection. Legal only from the
        active state — a second rollback, or a rollback after commit, is an error. This is the
        store's safety net: the store never rolls back, the UnitOfWork always does."""
        self._require_active("rollback")
        assert self._conn is not None  # guaranteed by the ACTIVE state (set only after begin)
        self._conn.rollback()
        self._state = _State.ROLLED_BACK

    def close(self) -> None:
        """Dispose of resources. Closes the connection **only** in owned mode; an injected
        connection belongs to the caller and is never closed here. Idempotent, so the
        context-manager exit and an explicit `close()` cannot double-close."""
        if self._closed:
            return
        self._closed = True
        if self._owns_conn and self._conn is not None:
            self._conn.close()

    # --- connection handle --------------------------------------------------------------

    @property
    def connection(self) -> psycopg.Connection[Any]:
        """The live connection to bind stores to, valid **only** while the transaction is active.
        Reaching for it before `begin` or after `commit`/`rollback` is a programming error (it
        would bind a store to a connection with no transaction, or a finished one), so it raises
        rather than hand back a connection whose writes would not be governed by this UoW."""
        if self._state is not _State.ACTIVE or self._conn is None:
            raise UnitOfWorkError(
                f"connection is only available inside an active transaction (state="
                f"{self._state.value}); call begin() first and do not use it after commit/rollback."
            )
        return self._conn

    # --- context manager ----------------------------------------------------------------

    def __enter__(self) -> UnitOfWork:
        return self.begin()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> Literal[False]:
        """On a clean exit, commit; on an exception (including a store failure), roll back — then
        dispose either way. Both actions are guarded by the active state, so an explicit
        `commit()`/`rollback()` inside the block is respected and never double-fired. Never
        suppresses the exception (returns False)."""
        try:
            if self._state is _State.ACTIVE:
                if exc_type is None:
                    self.commit()
                else:
                    self.rollback()
        finally:
            self.close()
        return False

    # --- internals ----------------------------------------------------------------------

    def _require_active(self, action: str) -> None:
        if self._state is not _State.ACTIVE:
            raise UnitOfWorkError(
                f"cannot {action}() from state '{self._state.value}': a UnitOfWork runs a single "
                f"flat transaction and {action}() is legal only while it is active."
            )
