"""Schema DDL for the `outbox` table (ADR 0043-S4, Slice 4), parameterised by table name.

The Transactional Outbox writes each domain event into this table **on the same connection and in
the same transaction** as the mission `save` it accompanies (Invariant I1), so a mission's state
change and its events commit atomically (I2). A separate relay later drains the unpublished rows
onto the Delivery Bus.

As in Slice 1, `outbox.py` never issues DDL — a sink/relay reads and writes rows, it does not create
schema. This module is the single source of truth for the table shape, used by (1) the canonical
migration `migrations/0002_outbox.sql`, kept in lock-step by a parity test, and (2) tests that stand
the schema up on a throwaway table.

Per ADR 0043-S4 Rev.3: **no `attempts` column** (retry/DLQ is deferred and out of scope). Every row
carries `payload_schema_version` — the serialization-version seam, exactly as the missions table.

Index names are derived from the table name so a throwaway test table never collides with the
canonical `outbox` indexes in the same database.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # import only for type checkers; the driver is never needed to import this module
    import psycopg

OUTBOX_TABLE = "outbox"

# The column definitions — the one authoritative list. `occurred_at` is the event's own epoch-second
# domain timestamp (DomainEvent.occurred_at); created_at/published_at are DB-managed ops columns.
# `id` is a bigserial: a monotonic sequence that IS the publish order (Invariant I7).
COLUMNS_DDL = """\
    id                     bigserial        PRIMARY KEY,
    event_name             text             NOT NULL,
    trace_id               text             NOT NULL,
    tenant_id              text             NOT NULL,
    mission_id             text             NOT NULL,
    occurred_at            double precision NOT NULL,
    payload                jsonb            NOT NULL,
    payload_schema_version integer          NOT NULL DEFAULT 1,
    created_at             timestamptz      NOT NULL DEFAULT now(),
    published_at           timestamptz"""


def create_table_sql(table: str = OUTBOX_TABLE) -> str:
    return f"CREATE TABLE IF NOT EXISTS {table} (\n{COLUMNS_DDL}\n);"


def index_sql(table: str = OUTBOX_TABLE) -> list[str]:
    """Indexes the relay's access paths rely on:

    - the relay polls unpublished rows in insertion order → a *partial* index on `id` where
      `published_at IS NULL` backs `SELECT ... WHERE published_at IS NULL ORDER BY id`;
    - every row and republished event carries its tenant (Invariant I5) → index `tenant_id`.
    """
    return [
        f"CREATE INDEX IF NOT EXISTS {table}_unpublished_idx "
        f"ON {table} (id) WHERE published_at IS NULL",
        f"CREATE INDEX IF NOT EXISTS {table}_tenant_idx ON {table} (tenant_id)",
    ]


def apply_outbox_schema(conn: psycopg.Connection, table: str = OUTBOX_TABLE) -> None:
    """Create the outbox table and its indexes if absent. Convenient for tests and first-run setup;
    production applies the canonical migration. Idempotent (`IF NOT EXISTS`)."""
    conn.execute(create_table_sql(table))
    for ddl in index_sql(table):
        conn.execute(ddl)
    conn.commit()
