-- Autonomous Knowledge Engine (KI-P1, CLAUDE.md §1/§12-13/§19, ADR-0025): the persistent
-- knowledge repository behind the Knowledge Question Generator, Gap Detector, and Discovery
-- engine. Reusable by Policy Hunter, Policy Analyst, Policy Builder, and a future Contract
-- Reviewer — none of which are wired to read from it yet (ADR-0025 is deliberately scoped to
-- the engine + storage layer, not consumer integration).
--
-- Platform-scope, not tenant-scope: GRC/compliance/legal knowledge ("what clauses should
-- exist in a vendor contract") is shared reference data every tenant draws from, exactly like
-- `regulatory_obligations` (0016_regulatory_intelligence.sql) and the Framework Engine's
-- framework definitions. No `tenant_id` column here by design.
--
-- One row per `question_id` (UNIQUE): a re-discovery replaces the current answer and bumps
-- `version` rather than accumulating a full history table — this phase does not need answer
-- history, only "what do we currently believe, and how much do we trust it."

CREATE TABLE IF NOT EXISTS knowledge_items (
  id text PRIMARY KEY,
  question_id text NOT NULL,
  question text NOT NULL,
  answer text NOT NULL,
  domain text NOT NULL,
  category text NOT NULL,
  applicable_context text NOT NULL,
  source_id text NOT NULL,
  source_name text NOT NULL,
  source_type text NOT NULL,
  source_url text NOT NULL,
  jurisdiction text NOT NULL,
  citation text NOT NULL,
  confidence real NOT NULL,
  status text NOT NULL DEFAULT 'discovered',
  last_verified timestamptz,
  verified_by text,
  version integer NOT NULL DEFAULT 1,
  version_hash text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT knowledge_items_question_id_key UNIQUE (question_id),
  CONSTRAINT knowledge_items_version_hash_key UNIQUE (version_hash),
  CONSTRAINT knowledge_items_domain_check CHECK (
    domain IN (
      'governance', 'risk_management', 'compliance', 'internal_controls', 'audit',
      'contracts', 'vendor_management', 'data_protection', 'cybersecurity_governance',
      'policies_procedures', 'regulatory_obligations'
    )
  ),
  CONSTRAINT knowledge_items_source_type_check CHECK (
    source_type IN (
      'government_regulator', 'official_framework', 'standards_body', 'law_regulation',
      'official_guidance'
    )
  ),
  -- Knowledge is never absolute (ADR-0025 §6): every item is created 'discovered' and only an
  -- explicit human decision moves it forward — the same never-auto-confirm posture
  -- `regulatory_obligations.classification_status` already established.
  CONSTRAINT knowledge_items_status_check CHECK (
    status IN ('discovered', 'verified', 'needs_review', 'outdated')
  ),
  CONSTRAINT knowledge_items_confidence_range_check CHECK (confidence >= 0 AND confidence <= 1),
  CONSTRAINT knowledge_items_version_check CHECK (version >= 1),
  -- A verified/needs_review/outdated item must record when it was last looked at by a human;
  -- only a freshly discovered item may still have this unset.
  CONSTRAINT knowledge_items_last_verified_required_check CHECK (
    status = 'discovered' OR last_verified IS NOT NULL
  )
);

CREATE INDEX IF NOT EXISTS knowledge_items_domain_idx ON knowledge_items (domain);
CREATE INDEX IF NOT EXISTS knowledge_items_status_idx
  ON knowledge_items (status, last_verified);
