-- Rasheed V2 — Mission Store — the outbox table (ADR 0043-S4, Slice 4: Transactional Outbox).
-- Applied to the ISOLATED V2 database (default: rasheed_v2). Does not touch V1's `aigrc`.
--
-- Each domain event the Mission Engine emits during a transition is written here BY the OutboxSink,
-- on the SAME connection and in the SAME transaction as the mission `save` (Invariant I1), so a
-- mission's state change and its events commit atomically (I2). A separate relay later drains the
-- unpublished rows (published_at IS NULL) onto the Delivery Bus, in insertion order.
--
-- `id` is a bigserial: a monotonic sequence that IS the publish order (I7). `occurred_at` is the
-- event's own epoch-second domain timestamp; `created_at`/`published_at` are DB-managed ops columns
-- (published_at NULL means "not yet delivered"). `payload` is the event's canonical to_dict();
-- `payload_schema_version` is the serialization-version seam (as the missions table).
--
-- Per ADR 0043-S4 Rev.3 there is deliberately NO `attempts` column: retry / dead-letter is deferred
-- and out of scope for this slice.
--
-- This DDL is kept in lock-step with mission_store/outbox_schema.py (a parity test enforces it).

CREATE TABLE IF NOT EXISTS outbox (
    id                     bigserial        PRIMARY KEY,
    event_name             text             NOT NULL,
    trace_id               text             NOT NULL,
    tenant_id              text             NOT NULL,
    mission_id             text             NOT NULL,
    occurred_at            double precision NOT NULL,
    payload                jsonb            NOT NULL,
    payload_schema_version integer          NOT NULL DEFAULT 1,
    created_at             timestamptz      NOT NULL DEFAULT now(),
    published_at           timestamptz
);

-- The relay polls unpublished rows in insertion order: a partial index on id where published_at is
-- NULL backs `SELECT ... WHERE published_at IS NULL ORDER BY id`.
CREATE INDEX IF NOT EXISTS outbox_unpublished_idx ON outbox (id) WHERE published_at IS NULL;

-- Every row (and every republished event) carries its tenant (I5).
CREATE INDEX IF NOT EXISTS outbox_tenant_idx ON outbox (tenant_id);
