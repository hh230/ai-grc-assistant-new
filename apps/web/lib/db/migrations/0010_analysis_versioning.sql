-- V2-P2.5: move `analyses` from "one row per document" to full version history — every
-- analysis run now inserts a new row instead of overwriting the previous one. `id` was
-- previously == document_id (one-to-one); existing rows keep their id (still globally
-- unique) and become version 1. New rows get a fresh id and an explicit next version number
-- computed by the application (the DEFAULT below only backfills existing rows).
--
-- Also adds the deterministic-scoring result columns computed by the new scoring engine
-- (compliance/risk score, maturity level, strengths, weaknesses, recommendations) and
-- `title` for the rename capability.

ALTER TABLE analyses
  ADD COLUMN version integer NOT NULL DEFAULT 1,
  ADD COLUMN title text,
  ADD COLUMN compliance_score integer,
  ADD COLUMN risk_score integer,
  ADD COLUMN maturity_level text,
  ADD COLUMN strengths jsonb NOT NULL DEFAULT '[]',
  ADD COLUMN weaknesses jsonb NOT NULL DEFAULT '[]',
  ADD COLUMN recommendations jsonb NOT NULL DEFAULT '[]';

UPDATE analyses SET title = file_name || ' · v' || version WHERE title IS NULL;
ALTER TABLE analyses ALTER COLUMN title SET NOT NULL;

DROP INDEX IF EXISTS analyses_tenant_document_idx;
CREATE UNIQUE INDEX IF NOT EXISTS analyses_tenant_document_version_idx
  ON analyses (tenant_id, document_id, version);
CREATE INDEX IF NOT EXISTS analyses_tenant_document_idx ON analyses (tenant_id, document_id);
