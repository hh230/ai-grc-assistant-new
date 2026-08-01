-- Rasheed V2 — Mission Store — the missions table (ADR 0043, Slice 1).
-- Applied to the ISOLATED V2 database (default: rasheed_v2). Does not touch V1's `aigrc`.
--
-- Every Mission is stored, no exception (ADR 0042 §11): from the one-step `simple` read to the
-- largest `composite` engagement. The tenant-scoping / lifecycle columns (tenant_id,
-- idempotency_key, status) are first-class indexed columns because the store queries and enforces
-- on them; the nested content (roles, current plan, full plan-version history, step results) rides
-- in JSONB. `created_at`/`updated_at` are the mission's own epoch-second domain timestamps;
-- `stored_at`/`row_updated_at` are DB-managed ops timestamps.
--
-- `revision` and `payload_schema_version` are present from this first migration by design
-- (ADR 0043 Architectural assumption 2 and §6): `revision` is the store-managed write counter that
-- lets a future optimistic-concurrency slice add a `WHERE revision = :expected` guard with NO
-- migration; `payload_schema_version` is the serialization-version seam for forward-migrating old
-- JSON. Slice 1 writes revision (incrementing) and payload_schema_version=1, and enforces neither.
--
-- This DDL is kept in lock-step with mission_store/schema.py (a parity test enforces it).

CREATE TABLE IF NOT EXISTS missions (
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
    payload_schema_version integer          NOT NULL DEFAULT 1,
    revision               bigint           NOT NULL DEFAULT 0,
    created_at             double precision NOT NULL,
    updated_at             double precision NOT NULL,
    stored_at              timestamptz      NOT NULL DEFAULT now(),
    row_updated_at         timestamptz      NOT NULL DEFAULT now()
);

-- Every read is tenant-scoped (get, find_by_idempotency_key) — index the tenant.
CREATE INDEX IF NOT EXISTS missions_tenant_idx ON missions (tenant_id);

-- Idempotency is unique PER TENANT and only for a non-empty key (ADR 0040 §5). A partial unique
-- index both enforces "one mission per (tenant, key)" at the database and backs the
-- find_by_idempotency_key lookup. Two tenants may reuse the same key; a tenant may not.
CREATE UNIQUE INDEX IF NOT EXISTS missions_idem_idx
    ON missions (tenant_id, idempotency_key) WHERE idempotency_key <> '';

-- Listing a tenant's missions by lifecycle state (a later read-model / recovery need).
CREATE INDEX IF NOT EXISTS missions_tenant_status_idx ON missions (tenant_id, status);
