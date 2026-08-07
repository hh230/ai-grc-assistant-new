-- Rasheed V2 — Sector Knowledge Packs — template_selections (ADR 0067 §4, §5).
--
-- PROPERTY THIS MIGRATION PROVES: an assessment cites at least one RELEASE, never a sector name —
-- which is what keeps a report explicable years later.
--
-- Real estate will have v1, v2, v3. A report written today must stay readable in three years,
-- which requires knowing the organization answered v1's questions and not today's. A sector name
-- cannot carry that; a release id can.
--
-- The list is plural because reality is not one sector (§5): a brokerage that also builds is
-- "Construction + Real Estate", and a holding company is neither of its subsidiaries' sectors.
--
-- `suggested_industry_slug` is stored ALONGSIDE the decision so the two stay comparable: a
-- suggestion the reviewer kept and a suggestion nobody examined are different facts, and only
-- keeping both can tell them apart.

CREATE TABLE IF NOT EXISTS template_selections (
    assessment_id           text        PRIMARY KEY REFERENCES assessments(id),
    tenant_id               text        NOT NULL,
    suggested_industry_slug text,
    selected_release_ids    text[]      NOT NULL,
    selected_by             text        NOT NULL,
    selected_at             timestamptz NOT NULL DEFAULT now(),
    -- coalesce is load-bearing: `array_length(ARRAY[]::text[], 1)` is NULL, not 0, and a CHECK
    -- that evaluates to NULL PASSES. Without it an assessment could cite no release at all — the
    -- exact thing this constraint exists to prevent.
    CONSTRAINT template_selections_cites_a_release CHECK (
        coalesce(array_length(selected_release_ids, 1), 0) >= 1
    )
);

CREATE INDEX IF NOT EXISTS template_selections_tenant_idx ON template_selections (tenant_id);
-- Answers "which assessments used this release?" — the query an auditor asks after a bad release
-- is found, and the reason the ids are indexed rather than merely stored.
CREATE INDEX IF NOT EXISTS template_selections_releases_idx
    ON template_selections USING gin (selected_release_ids);
