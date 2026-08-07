-- Rasheed V2 — Sector Knowledge Packs — knowledge_templates (ADR 0067 §4).
--
-- PROPERTY THIS MIGRATION PROVES: exactly one knowledge container per industry.
--
-- The container is deliberately almost empty. It names an industry's knowledge once; every
-- version's content, lifecycle and provenance lives on `template_releases` (§4, "the template is
-- a container; the release is the version" — build versus deploy). A second container for the
-- same industry would make "which template does real estate use?" ambiguous, so the UNIQUE
-- constraint makes that unrepresentable rather than merely discouraged.

CREATE TABLE IF NOT EXISTS knowledge_templates (
    id            text        PRIMARY KEY,
    industry_slug text        NOT NULL REFERENCES industries(slug),
    created_at    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT knowledge_templates_one_per_industry UNIQUE (industry_slug)
);
