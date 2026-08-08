-- Rasheed V2 — Signal Resolution (ADR 0068): which analysis a plan was built from.
--
-- PROPERTY THIS MIGRATION PROVES: a plan can name the exact analysis it rests on.
--
-- Nullable, and it stays nullable: a plan whose session never stored an applicability has no
-- version to point at, and inventing one would be worse than admitting it. `NULL` here means
-- "not recorded", which is a true statement about the past.
--
-- A CORRECTIVE migration rather than an edit to 0003. The column belongs to a table 0003 created,
-- and it was briefly added there — but 0003 is applied everywhere already, and this project
-- re-runs every migration on every release with no apply-tracking ledger (ADR 0045), so editing an
-- applied file changes behaviour with nothing in the history saying it ever did.
--
-- The ALTER is GUARDED because the two fixtures in this repository build different databases: the
-- ADR 0067 knowledge suite applies migrations 4 and up, where `governance_plans` does not exist,
-- and an unguarded ALTER fails there with `UndefinedTable` — verified, not assumed. `IF NOT EXISTS`
-- does not help: it forgives a missing COLUMN, never a missing TABLE. A migration that only works
-- when an unrelated earlier file happened to run is not idempotent DDL, whatever it says.

DO $$
BEGIN
    IF to_regclass('public.governance_plans') IS NOT NULL THEN
        ALTER TABLE governance_plans
            ADD COLUMN IF NOT EXISTS source_applicability_id text;
    END IF;
END
$$;
