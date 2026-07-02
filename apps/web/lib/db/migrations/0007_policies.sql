-- Authored governance policies with an approval workflow (publish is a human gate —
-- CLAUDE.md §1). `status` is one of draft | in_review | published | archived.
CREATE TABLE IF NOT EXISTS policies (
  id text PRIMARY KEY,
  tenant_id text NOT NULL,
  title text NOT NULL,
  summary text,
  body text,
  status text NOT NULL,
  owner_name text NOT NULL,
  control_ids jsonb NOT NULL DEFAULT '[]',
  created_by_user_id text NOT NULL,
  created_by_name text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  approved_by_name text,
  approved_at timestamptz
);

CREATE INDEX IF NOT EXISTS policies_tenant_id_idx ON policies (tenant_id);
CREATE INDEX IF NOT EXISTS policies_tenant_updated_idx ON policies (tenant_id, updated_at DESC);
