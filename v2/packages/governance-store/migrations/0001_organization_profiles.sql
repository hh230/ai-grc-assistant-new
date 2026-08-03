-- Rasheed V2 — Governance Store — organization_profiles (ADR 0066 §1).
-- Applied to the ISOLATED V2 database (default: rasheed_v2). Does not touch V1's `aigrc`.
--
-- One row per tenant: the org's current structural facts. `active_packs` is the composable set
-- of Knowledge Packs currently applicable (ADR 0066 §2.1) — an organization is rarely one
-- industry, so this is a set, never a single label; `primary_pack_id` is a display convenience
-- only. Separate from the identity/tenancy `Organization` aggregate, which is unchanged.
--
-- Kept in lock-step with governance_store/schema.py (the schema parity test enforces it).

CREATE TABLE IF NOT EXISTS organization_profiles (
    id                     text             PRIMARY KEY,
    tenant_id              text             NOT NULL UNIQUE,
    primary_pack_id        text,
    active_packs           jsonb            NOT NULL DEFAULT '[]'::jsonb,
    size_band              text,
    maturity_level         text,
    signals                jsonb            NOT NULL DEFAULT '{}'::jsonb,
    created_at             double precision NOT NULL,
    updated_at             double precision NOT NULL
);
