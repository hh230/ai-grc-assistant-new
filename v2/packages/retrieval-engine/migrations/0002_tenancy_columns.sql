-- Rasheed V2 — Retrieval Engine — add the ADR 0040 tenancy columns to an EXISTING table.
--
-- Why this exists as a separate migration: 0001 declares the columns, but `CREATE TABLE IF NOT
-- EXISTS` is a no-op against a database provisioned before they were added. Every such database
-- keeps a table the current code cannot query at all — the provider puts `scope_kind` in the
-- WHERE clause of every search, so the failure is total, not partial, and it surfaces only
-- against a real Postgres (the pgvector tests skip without one).
--
-- Safe on a loaded corpus: ADD COLUMN with a constant DEFAULT does not rewrite the table on
-- PostgreSQL 11+, and the 'global' default is precisely the intended classification for an
-- existing corpus — the shared framework/law/standard library IS global knowledge. Organization
-- data is written later with scope_kind='organization' and an organization_id.

ALTER TABLE knowledge_vectors
    ADD COLUMN IF NOT EXISTS scope_kind      text NOT NULL DEFAULT 'global';

ALTER TABLE knowledge_vectors
    ADD COLUMN IF NOT EXISTS organization_id text;

-- The tenant-scope predicate is applied on every query — index it (ADR 0040 §4).
CREATE INDEX IF NOT EXISTS kv_scope_idx ON knowledge_vectors (scope_kind, organization_id);
