"""Schema DDL for the Mission read-model table (ADR 0053), parameterised by table name.

The read model is a self-contained projection: one row per mission carrying the list-row fields
(the product `mission_type` + `title`/scope the Core omits, plus a `status` snapshot and the
mission's own timestamps). The projector upserts rows here; `GET /v1/missions` reads them. The
adapter never issues DDL at runtime — this is the single source of truth for the table shape, used
by a throwaway test table and (later) a canonical migration.

Indexes support the Missions View's access pattern: filter by tenant (always), then by status/type,
ordered newest-first.
"""

from __future__ import annotations

DEFAULT_TABLE = "mission_read_model"


def create_table_sql(table: str = DEFAULT_TABLE) -> str:
    return f"""\
CREATE TABLE IF NOT EXISTS {table} (
    mission_id   text             PRIMARY KEY,
    tenant_id    text             NOT NULL,
    mission_type text             NOT NULL,
    title        text             NOT NULL DEFAULT '',
    status       text             NOT NULL,
    created_at   double precision NOT NULL,
    updated_at   double precision NOT NULL,
    row_updated_at timestamptz    NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS {table}_tenant_updated_idx
    ON {table} (tenant_id, updated_at DESC, created_at DESC, mission_id DESC);
CREATE INDEX IF NOT EXISTS {table}_tenant_status_idx ON {table} (tenant_id, status);
CREATE INDEX IF NOT EXISTS {table}_tenant_type_idx ON {table} (tenant_id, mission_type);
"""
