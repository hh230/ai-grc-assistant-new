-- Rasheed V2 — Sector Knowledge Packs — assessments (ADR 0067 §4).
--
-- PROPERTY THIS MIGRATION PROVES: an assessment is a first-class, tenant-scoped thing with a
-- beginning and an end — not a browser session, and not the organization.
--
-- A session is a browser artifact: interruptible, and one assessment may span several. An
-- organization is assessed repeatedly over years, so binding knowledge provenance there would
-- erase which knowledge produced which report. The chain is
-- Organization -> Assessment -> TemplateSelection -> TemplateRelease.
--
-- `source_session_id` is a nullable, informational back-reference. NOT a foreign key and NOT
-- required: ADR 0067's migration plan forbids backfill, so an assessment must be creatable
-- without inventing a session, and sessions that predate this ADR keep working with no assessment
-- at all.
--
-- tenant_id starts here (CLAUDE.md §20). Tables 0004-0010 are shared knowledge and deliberately
-- carry none.

CREATE TABLE IF NOT EXISTS assessments (
    id                text        PRIMARY KEY,
    tenant_id         text        NOT NULL,
    organization_id   text        NOT NULL,
    source_session_id text,
    started_at        timestamptz NOT NULL DEFAULT now(),
    completed_at      timestamptz,
    CONSTRAINT assessments_ends_after_it_starts CHECK (
        completed_at IS NULL OR completed_at >= started_at
    )
);

CREATE INDEX IF NOT EXISTS assessments_tenant_org_idx
    ON assessments (tenant_id, organization_id, started_at DESC);
