"""The Transactional Outbox's driver-facing components (ADR 0043-S4, Slice 4).

- **`OutboxSink`** — an `EventBus` subscriber (`EventHandler`, `(DomainEvent) -> None`). Subscribed
  to the **Capture Bus** the engine emits onto during a transition, it writes each event as a
  row **on the injected connection** — the same connection `PostgresMissionStore` is using, inside
  the same `UnitOfWork` transaction (Invariant I1). It therefore commits atomically with the mission
  `save` (I2). Like the store, the sink **never commits and never rolls back** — the `UnitOfWork`
  owns the transaction (I3). Its failure must propagate to abort the transaction, so the Capture Bus
  must not isolate it (I4).

- **`OutboxRelay`** — drains committed-but-unpublished rows (I11: only committed rows are in the
  table) in insertion order, rehydrates each into a typed `DomainEvent`, hands it to an
  `OutboxPublisher` (the Delivery Bus), then marks the row published. At-least-once (I6): a crash
  after publish and before the mark re-publishes on the next drain. An unregistered event raises
  `UnsupportedEventType` and the row is **left unpublished** — never deleted, never marked (§6, I8).

The psycopg driver is imported **lazily**, inside the methods that touch the DB, so the package
(and the pure codec/schema/publisher/errors modules) imports with no driver — as store.py and
the Retrieval Engine's pgvector adapter do. Retry/DLQ/pruning/multi-worker are out of scope (Rev.3).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from mission_store.config import dsn as default_dsn
from mission_store.outbox_codec import (
    JSONB_COLUMNS,
    OUTBOX_READ_COLUMNS,
    OUTBOX_WRITE_COLUMNS,
    event_from_record,
    event_to_row,
    record_from_row,
)
from mission_store.outbox_publisher import OutboxPublisher
from mission_store.outbox_schema import OUTBOX_TABLE

if TYPE_CHECKING:  # import only for type checkers; never required at runtime to import the module
    import psycopg
    from event_bus.events import DomainEvent

_MISSING_PG = (
    "The Mission Store outbox needs the 'psycopg' package. "
    "Install the optional extra: mission-store[postgres]"
)

_SELECT_LIST = ", ".join(OUTBOX_READ_COLUMNS)


def _load_pg() -> tuple[Any, Any, Any]:
    """Import the psycopg pieces lazily: the module, the JSONB adapter, and the dict row factory.
    Kept out of module import so the package loads without the driver."""
    try:
        import psycopg
        from psycopg.rows import dict_row
        from psycopg.types.json import Jsonb
    except ImportError as exc:  # pragma: no cover - exercised only without the extra installed
        raise ImportError(_MISSING_PG) from exc
    return psycopg, Jsonb, dict_row


class OutboxSink:
    """Captures every event emitted on the Capture Bus into the outbox table, transactionally.

    Bound to the **caller's connection** (the `UnitOfWork`'s) at construction: there is no owned /
    autocommit mode, because the outbox write only has meaning *inside* a transaction it shares with
    the mission `save`. Subscribe `sink.write` to the Capture Bus (`subscribe(ALL_EVENTS, ...)`).
    """

    def __init__(self, *, connection: psycopg.Connection[Any], table: str = OUTBOX_TABLE) -> None:
        self._conn = connection
        self._table = table

    def write(self, event: DomainEvent) -> None:
        """Insert the event as an outbox row on the shared connection (the `EventHandler` seam). No
        commit and no rollback — the `UnitOfWork` owns the transaction (I3); a failure here must
        propagate to abort it (I4)."""
        _, jsonb, _ = _load_pg()
        row = event_to_row(event)
        params = {
            col: (jsonb(row[col]) if col in JSONB_COLUMNS else row[col])
            for col in OUTBOX_WRITE_COLUMNS
        }
        placeholders = ", ".join(f"%({col})s" for col in OUTBOX_WRITE_COLUMNS)
        sql = (
            f"INSERT INTO {self._table} ({', '.join(OUTBOX_WRITE_COLUMNS)}) "
            f"VALUES ({placeholders})"
        )
        self._conn.execute(sql, params)


class OutboxRelay:
    """Drains unpublished outbox rows onto the Delivery Bus, in insertion order.

    Mirrors the store's connection model: an **owned** connection (opened lazily from `dsn`, in
    autocommit so each mark is durable on execute) or an **injected** one (the caller's, used as-is;
    the caller owns its lifetime and transaction). Single-worker only — multi-worker
    (`FOR UPDATE SKIP LOCKED`), retry, and pruning are deferred (Rev.3)."""

    def __init__(
        self,
        *,
        dsn: str | None = None,
        connection: psycopg.Connection[Any] | None = None,
        table: str = OUTBOX_TABLE,
    ) -> None:
        self._table = table
        self._owns_conn = connection is None
        if connection is not None:
            self._conn = connection
        else:
            psycopg, _, _ = _load_pg()
            # autocommit: each published-mark is a single statement and must be durable on return,
            # exactly as the owned mission store runs (Slice 1).
            self._conn = psycopg.connect(dsn or default_dsn(), autocommit=True)

    def drain(self, publisher: OutboxPublisher, *, limit: int = 100) -> int:
        """Publish every unpublished row (up to `limit`) in insertion order, marking each published
        after it is delivered. Returns the count delivered. Only committed rows are ever in the
        table, so nothing uncommitted is published (I11). An `UnsupportedEventType` (unregistered
        event) propagates and the row is left unpublished — never deleted or marked (I8)."""
        _, _, dict_row = _load_pg()
        select_sql = (
            f"SELECT {_SELECT_LIST} FROM {self._table} "
            f"WHERE published_at IS NULL ORDER BY id LIMIT %(limit)s"
        )
        with self._conn.cursor(row_factory=dict_row) as cur:
            cur.execute(select_sql, {"limit": limit})
            rows = cur.fetchall()

        published = 0
        for row in rows:
            record = record_from_row(row)
            event = event_from_record(record)  # raises UnsupportedEventType → row left unpublished
            publisher.publish(event)
            self._conn.execute(
                f"UPDATE {self._table} SET published_at = now() WHERE id = %(id)s",
                {"id": record.id},
            )
            published += 1
        return published

    def close(self) -> None:
        """Close the connection only if this relay opened it. An injected connection is the caller's
        to close."""
        if self._owns_conn:
            self._conn.close()
