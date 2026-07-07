-- Saudi Regulations Ingestion Pipeline (Knowledge Intelligence KI-P6, ADR-0030): the first
-- production Postgres persistence for grc_domain.knowledge's KnowledgeSource ->
-- KnowledgeSourceVersion -> KnowledgeDocument -> KnowledgeSection model. Platform-scope (no
-- tenant_id), matching knowledge_items/regulatory_raw_documents: Saudi regulations are shared
-- reference data every tenant draws from, not any one tenant's own data.
--
-- Deliberately NOT built on packages/persistence's SQLAlchemy UnitOfWork/outbox — the M6
-- Extraction Engine's own intended KnowledgeIngestionPort persistence path. That path is
-- explicitly blocked pending Product Owner approval to re-align it with the refactored domain
-- (ADL-0008, see PROJECT_STATE.md). This migration follows the same direct-asyncpg pattern
-- every prior Knowledge Intelligence phase already uses instead (0018_knowledge_items.sql,
-- 0016_regulatory_intelligence.sql).
--
-- Every fetched regulation lands as a version with status = 'in_review' ("pending_review") —
-- never auto-trusted. Only an explicit admin approval (a later phase, KI-P7) moves a version
-- to 'approved'/'published'; nothing in this migration or its writers can do that itself.

CREATE TABLE IF NOT EXISTS regulation_sources (
  id text PRIMARY KEY,
  short_code text NOT NULL,
  title_ar text NOT NULL,
  title_en text,
  authority text NOT NULL,
  jurisdiction text NOT NULL,
  knowledge_domain text NOT NULL,
  document_type text NOT NULL,
  boe_source_url text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT regulation_sources_short_code_key UNIQUE (short_code),
  CONSTRAINT regulation_sources_knowledge_domain_check CHECK (
    knowledge_domain IN (
      'legal_regulatory', 'standards_frameworks', 'governance', 'organizational', 'operational'
    )
  ),
  CONSTRAINT regulation_sources_document_type_check CHECK (
    document_type IN (
      'law', 'executive_regulation', 'government_guide', 'standard', 'framework', 'policy',
      'procedure', 'template', 'contract', 'internal_document', 'other'
    )
  )
);

-- One row per fetched revision of a regulation. `content_hash` is the dedup key: re-fetching
-- unchanged content is a no-op (KnowledgeItemRepository's own idiom); a real content change
-- drafts a new version, it never edits a prior (possibly already-approved/published) one —
-- mirroring KnowledgeSourceVersion's own domain immutability rule.
CREATE TABLE IF NOT EXISTS regulation_source_versions (
  id text PRIMARY KEY,
  source_id text NOT NULL REFERENCES regulation_sources (id),
  version_label text NOT NULL,
  status text NOT NULL DEFAULT 'in_review',
  official_citation text,
  effective_start date,
  effective_end date,
  publication_date date,
  change_summary_ar text,
  change_summary_en text,
  content_hash text NOT NULL,
  approved_by text,
  approved_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT regulation_source_versions_content_hash_key UNIQUE (content_hash),
  CONSTRAINT regulation_source_versions_status_check CHECK (
    status IN (
      'draft', 'in_review', 'approved', 'published', 'superseded', 'withdrawn', 'archived',
      'rejected'
    )
  ),
  -- Only a human approval (KI-P7) ever populates these — never set by the ingestion writer.
  CONSTRAINT regulation_source_versions_approval_check CHECK (
    (approved_by IS NULL) = (approved_at IS NULL)
  )
);

CREATE INDEX IF NOT EXISTS regulation_source_versions_source_id_idx
  ON regulation_source_versions (source_id, created_at DESC);
CREATE INDEX IF NOT EXISTS regulation_source_versions_status_idx
  ON regulation_source_versions (status);

CREATE TABLE IF NOT EXISTS regulation_documents (
  id text PRIMARY KEY,
  version_id text NOT NULL REFERENCES regulation_source_versions (id),
  language text NOT NULL,
  document_format text NOT NULL,
  source_url text NOT NULL,
  content_hash text NOT NULL,
  byte_size integer,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT regulation_documents_document_format_check CHECK (
    document_format IN ('pdf', 'docx', 'xlsx', 'html', 'markdown', 'txt')
  ),
  CONSTRAINT regulation_documents_byte_size_check CHECK (byte_size IS NULL OR byte_size >= 0)
);

CREATE INDEX IF NOT EXISTS regulation_documents_version_id_idx
  ON regulation_documents (version_id);

-- One row per legal unit (article/chapter/clause/...) — never split across rows. `path` is
-- the chapter breadcrumb (e.g. {'الباب الأول'}) for display; `parent_section_id` links an
-- article back to its chapter row for structural traversal.
CREATE TABLE IF NOT EXISTS regulation_sections (
  id text PRIMARY KEY,
  document_id text NOT NULL REFERENCES regulation_documents (id),
  section_type text NOT NULL,
  code text NOT NULL,
  path text[] NOT NULL DEFAULT '{}',
  title_ar text,
  title_en text,
  text_ar text,
  text_en text,
  position integer NOT NULL DEFAULT 0,
  parent_section_id text REFERENCES regulation_sections (id),
  amendment_note_ar text,
  amendment_note_en text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT regulation_sections_section_type_check CHECK (
    section_type IN (
      'part', 'chapter', 'article', 'clause', 'section', 'subsection', 'annex', 'schedule',
      'appendix'
    )
  ),
  CONSTRAINT regulation_sections_position_check CHECK (position >= 0)
);

CREATE INDEX IF NOT EXISTS regulation_sections_document_position_idx
  ON regulation_sections (document_id, position);
