-- One latest AI-pipeline analysis per document (id == document_id).
CREATE TABLE IF NOT EXISTS analyses (
  id text PRIMARY KEY,
  document_id text NOT NULL,
  tenant_id text NOT NULL,
  file_name text NOT NULL,
  status text NOT NULL,
  error text,
  char_count integer NOT NULL DEFAULT 0,
  page_count integer,
  chunk_count integer NOT NULL DEFAULT 0,
  embedding_provider text,
  chat_provider text,
  summary text,
  findings jsonb NOT NULL DEFAULT '[]',
  frameworks jsonb NOT NULL DEFAULT '[]',
  key_terms jsonb NOT NULL DEFAULT '[]',
  requested_by_user_id text NOT NULL,
  requested_by_name text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz,
  duration_ms integer
);

CREATE INDEX IF NOT EXISTS analyses_tenant_id_idx ON analyses (tenant_id);
CREATE UNIQUE INDEX IF NOT EXISTS analyses_tenant_document_idx ON analyses (tenant_id, document_id);
