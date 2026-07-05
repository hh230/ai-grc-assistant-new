-- Regulatory Intelligence (Policy Intelligence PI-P1, CLAUDE.md §12-13, ADR-0018): the
-- connector -> raw document -> obligation extraction -> classification -> storage pipeline
-- that feeds the Policy Hunter agent (a later phase) structured obligations.
--
-- Platform-scope, not tenant-scope: a regulation is shared reference data every tenant's
-- Policy Hunter draws from, exactly like the Framework Engine's framework definitions and
-- `ai_tool_invocations.tenant_id = NULL` runs (see 0013_ai_tool_invocations.sql's comment,
-- which named this subsystem in advance). No `tenant_id` column here by design.

CREATE TABLE IF NOT EXISTS regulatory_raw_documents (
  id text PRIMARY KEY,
  source_id text NOT NULL,
  url text NOT NULL,
  fetched_at timestamptz NOT NULL,
  content_hash text NOT NULL,
  raw_text text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT regulatory_raw_documents_content_hash_key UNIQUE (content_hash)
);

CREATE INDEX IF NOT EXISTS regulatory_raw_documents_source_fetched_idx
  ON regulatory_raw_documents (source_id, fetched_at DESC);

CREATE TABLE IF NOT EXISTS regulatory_obligations (
  id text PRIMARY KEY,
  raw_document_id text NOT NULL REFERENCES regulatory_raw_documents (id) ON DELETE CASCADE,
  obligation_text text NOT NULL,
  obligation_type text NOT NULL,
  control_domain text NOT NULL,
  suggested_policy_title text NOT NULL,
  severity text NOT NULL,
  confidence real NOT NULL,
  source_char_start integer NOT NULL,
  source_char_end integer NOT NULL,
  classifier_model text,
  prompt_version text,
  version_hash text NOT NULL,
  classification_status text NOT NULL DEFAULT 'pending_review',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT regulatory_obligations_version_hash_key UNIQUE (version_hash),
  CONSTRAINT regulatory_obligations_obligation_type_check CHECK (
    obligation_type IN (
      'requirement', 'prohibition', 'permission', 'reporting', 'disclosure',
      'record_keeping', 'notification', 'other'
    )
  ),
  CONSTRAINT regulatory_obligations_control_domain_check CHECK (
    control_domain IN (
      'governance', 'risk_management', 'access_control', 'data_protection',
      'asset_management', 'physical_security', 'human_resources_security',
      'incident_management', 'business_continuity', 'third_party_management',
      'compliance_monitoring', 'other'
    )
  ),
  CONSTRAINT regulatory_obligations_severity_check CHECK (
    severity IN ('critical', 'high', 'medium', 'low', 'informational')
  ),
  -- Every obligation is created pending_review (CLAUDE.md §1: human-in-the-loop by default);
  -- a low-confidence classification must never be created confirmed/rejected outright.
  CONSTRAINT regulatory_obligations_classification_status_check CHECK (
    classification_status IN ('pending_review', 'confirmed', 'rejected')
  ),
  CONSTRAINT regulatory_obligations_low_confidence_pending_review_check CHECK (
    confidence >= 0.5 OR classification_status = 'pending_review'
  ),
  CONSTRAINT regulatory_obligations_confidence_range_check CHECK (confidence >= 0 AND confidence <= 1),
  CONSTRAINT regulatory_obligations_span_check CHECK (source_char_end > source_char_start)
);

CREATE INDEX IF NOT EXISTS regulatory_obligations_raw_document_idx
  ON regulatory_obligations (raw_document_id);
CREATE INDEX IF NOT EXISTS regulatory_obligations_status_idx
  ON regulatory_obligations (classification_status, created_at DESC);
CREATE INDEX IF NOT EXISTS regulatory_obligations_control_domain_idx
  ON regulatory_obligations (control_domain);
