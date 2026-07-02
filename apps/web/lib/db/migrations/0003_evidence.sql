-- Evidence artifacts (proof a control is operating) with version history. `evidence` holds
-- the current pointer + metadata; `evidence_versions` is the append-only history, one row
-- per uploaded version, cascade-deleted with its parent.
CREATE TABLE IF NOT EXISTS evidence (
  id text PRIMARY KEY,
  tenant_id text NOT NULL,
  title text NOT NULL,
  description text,
  tags jsonb NOT NULL DEFAULT '[]',
  control_ids jsonb NOT NULL DEFAULT '[]',
  current_version_id text NOT NULL,
  created_by_user_id text NOT NULL,
  created_by_name text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS evidence_tenant_id_idx ON evidence (tenant_id);
CREATE INDEX IF NOT EXISTS evidence_tenant_updated_idx ON evidence (tenant_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS evidence_versions (
  id text PRIMARY KEY,
  evidence_id text NOT NULL REFERENCES evidence (id) ON DELETE CASCADE,
  tenant_id text NOT NULL,
  version_number integer NOT NULL,
  file_name text NOT NULL,
  content_type text NOT NULL,
  kind text NOT NULL,
  size_bytes bigint NOT NULL,
  checksum_sha256 text NOT NULL,
  storage_key text NOT NULL,
  note text,
  uploaded_by_user_id text NOT NULL,
  uploaded_by_name text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (evidence_id, version_number)
);

CREATE INDEX IF NOT EXISTS evidence_versions_evidence_id_idx ON evidence_versions (evidence_id, version_number);
