-- Rasheed V2 — Sector Knowledge Packs — industries (ADR 0067 §4).
-- Applied to the ISOLATED V2 database. Adds tables only; touches nothing that exists.
--
-- PROPERTY THIS MIGRATION PROVES: an industry is identified by its slug, and by nothing else.
--
-- Deliberately three columns. ADR 0067 §4 refuses parent_industry / aliases / icon /
-- regulatory_family here: each turns a lookup value into the axis of a system whose axis is the
-- rule engine. What an industry IMPLIES belongs in derivations, where it is auditable.
--
-- NO tenant_id, here or on any of the knowledge tables (0004-0009): sector knowledge is generated
-- once and shared by every organization in that sector — that is the whole point of ADR 0067.
-- Tenant scoping starts at 0011, where customer data does (CLAUDE.md §20).

CREATE TABLE IF NOT EXISTS industries (
    slug              text        PRIMARY KEY,
    canonical_name_ar text        NOT NULL,
    status            text        NOT NULL DEFAULT 'active',
    created_at        timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT industries_status_known CHECK (status IN ('active', 'retired'))
);

-- Retiring an industry never invalidates history (§4): an assessment cites a release, so a
-- retired industry keeps explaining the reports produced under it. This index serves the
-- "what can a customer choose today?" query without making the retired rows unreachable.
CREATE INDEX IF NOT EXISTS industries_status_idx ON industries (status);
