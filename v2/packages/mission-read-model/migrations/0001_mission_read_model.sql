-- Rasheed V2 — Mission Read Model — the `mission_read_model` projection table (ADR 0053).
-- Applied to the ISOLATED V2 database (default: rasheed_v2). Does not touch V1's `aigrc`.
--
-- One row per mission carrying the list-row fields `GET /v1/missions` reads: the product
-- `mission_type` + `title`/scope the Core omits, plus a `status` snapshot and the mission's own
-- timestamps. The projector upserts rows here on every transition; the route never reads the
-- `missions` table directly. Isolation is enforced in SQL — every read predicates on tenant_id.
--
-- This DDL is kept in lock-step with mission_read_model/schema.py's create_table_sql() (the single
-- source of truth for the table shape) — this file is the canonical migration that schema.py's own
-- docstring names as still outstanding.

CREATE TABLE IF NOT EXISTS mission_read_model (
    mission_id     text             PRIMARY KEY,
    tenant_id      text             NOT NULL,
    mission_type   text             NOT NULL,
    title          text             NOT NULL DEFAULT '',
    status         text             NOT NULL,
    created_at     double precision NOT NULL,
    updated_at     double precision NOT NULL,
    row_updated_at timestamptz      NOT NULL DEFAULT now()
);

-- The Missions View's access pattern: filter by tenant (always), then by status/type, newest first.
CREATE INDEX IF NOT EXISTS mission_read_model_tenant_updated_idx
    ON mission_read_model (tenant_id, updated_at DESC, created_at DESC, mission_id DESC);
CREATE INDEX IF NOT EXISTS mission_read_model_tenant_status_idx ON mission_read_model (tenant_id, status);
CREATE INDEX IF NOT EXISTS mission_read_model_tenant_type_idx ON mission_read_model (tenant_id, mission_type);
