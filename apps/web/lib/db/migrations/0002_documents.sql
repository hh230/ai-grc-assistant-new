-- Uploaded documents (the platform's "knowledge source" — CLAUDE.md §21 naming). One row
-- per document; tenant-scoped by CLAUDE.md §20 (default deny — every query below filters
-- on tenant_id).
CREATE TABLE IF NOT EXISTS documents (
  id text PRIMARY KEY,
  tenant_id text NOT NULL,
  uploaded_by_user_id text NOT NULL,
  uploaded_by_name text NOT NULL,
  file_name text NOT NULL,
  content_type text NOT NULL,
  kind text NOT NULL,
  size_bytes bigint NOT NULL,
  checksum_sha256 text NOT NULL,
  storage_key text NOT NULL,
  status text NOT NULL,
  status_detail text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS documents_tenant_id_idx ON documents (tenant_id);
CREATE INDEX IF NOT EXISTS documents_tenant_created_idx ON documents (tenant_id, created_at DESC);
