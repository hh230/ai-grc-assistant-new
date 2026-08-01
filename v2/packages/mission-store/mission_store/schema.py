"""Schema DDL for the missions table, parameterised by table name (ADR 0043 §7).

`store.py` never issues DDL — a store reads and writes rows, it does not create schema. This
module is the single source of truth for the table shape, used by (1) the canonical migration
`migrations/0001_missions.sql`, kept in lock-step by a parity test, and (2) tests that stand the
schema up on a throwaway table.

Two columns exist from day one that Slice 1 does not yet *use* the full power of, by deliberate
design (ADR 0043 Architectural assumption 2 and §6): `revision` (a store-managed write counter —
the hook a future optimistic-concurrency slice needs, so enabling it later is a `WHERE revision =`
clause with no migration) and `payload_schema_version` (the serialization-version seam). Putting
them in the first migration is the whole point: the schema pre-pays for those futures.

Index names are derived from the table name so a throwaway test table never collides with the
canonical `missions` indexes in the same database.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mission_store.config import TABLE

if TYPE_CHECKING:  # import only for type checkers; the driver is never needed to import this module
    import psycopg

# The column definitions — the one authoritative list. `created_at`/`updated_at` are the
# mission's own epoch-second timestamps (the domain clock, `time.time()`); `stored_at`/
# `row_updated_at` are DB-managed ops timestamps.
COLUMNS_DDL = """\
    id                     text             PRIMARY KEY,
    tenant_id              text             NOT NULL,
    principal_id           text             NOT NULL DEFAULT '',
    region                 text             NOT NULL DEFAULT '',
    roles                  jsonb            NOT NULL DEFAULT '[]'::jsonb,
    goal                   text             NOT NULL,
    trace_id               text             NOT NULL,
    status                 text             NOT NULL,
    execution_profile      text,
    plan_version           integer          NOT NULL DEFAULT 0,
    idempotency_key        text             NOT NULL DEFAULT '',
    plan                   jsonb,
    plan_versions          jsonb            NOT NULL DEFAULT '[]'::jsonb,
    step_results           jsonb            NOT NULL DEFAULT '[]'::jsonb,
    approval               jsonb,
    payload_schema_version integer          NOT NULL DEFAULT 1,
    revision               bigint           NOT NULL DEFAULT 0,
    created_at             double precision NOT NULL,
    updated_at             double precision NOT NULL,
    stored_at              timestamptz      NOT NULL DEFAULT now(),
    row_updated_at         timestamptz      NOT NULL DEFAULT now()"""


def create_table_sql(table: str = TABLE) -> str:
    return f"CREATE TABLE IF NOT EXISTS {table} (\n{COLUMNS_DDL}\n);"


def index_sql(table: str = TABLE) -> list[str]:
    """Indexes the store's three access paths rely on:

    - every read is tenant-scoped (`get`, `find_by_idempotency_key`) → index `tenant_id`;
    - idempotency is unique **per tenant** and only for a non-empty key (ADR 0040 §5) → a
      *partial* unique index, which both enforces the invariant at the database and backs the
      `find_by_idempotency_key` lookup;
    - listing a tenant's missions by state (a later read-model / recovery need) → `(tenant_id,
      status)`.
    """
    return [
        f"CREATE INDEX IF NOT EXISTS {table}_tenant_idx ON {table} (tenant_id)",
        f"CREATE UNIQUE INDEX IF NOT EXISTS {table}_idem_idx "
        f"ON {table} (tenant_id, idempotency_key) WHERE idempotency_key <> ''",
        f"CREATE INDEX IF NOT EXISTS {table}_tenant_status_idx ON {table} (tenant_id, status)",
    ]


def apply_schema(conn: psycopg.Connection, table: str = TABLE) -> None:
    """Create the table and its indexes if absent. Convenient for tests and first-run setup;
    production applies the canonical migration. Idempotent (`IF NOT EXISTS`)."""
    conn.execute(create_table_sql(table))
    for ddl in index_sql(table):
        conn.execute(ddl)
    conn.commit()
