-- Risk register: 5x5 likelihood/impact scoring, mitigating-control linkage, and a status
-- workflow. Accepting a risk is a human-gated, consequential action (CLAUDE.md §1).
CREATE TABLE IF NOT EXISTS risks (
  id text PRIMARY KEY,
  tenant_id text NOT NULL,
  title text NOT NULL,
  description text,
  category text NOT NULL,
  likelihood integer NOT NULL,
  impact integer NOT NULL,
  status text NOT NULL,
  owner_name text NOT NULL,
  control_ids jsonb NOT NULL DEFAULT '[]',
  mitigation_plan text,
  residual_likelihood integer,
  residual_impact integer,
  created_by_user_id text NOT NULL,
  created_by_name text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  accepted_by_name text,
  accepted_at timestamptz
);

CREATE INDEX IF NOT EXISTS risks_tenant_id_idx ON risks (tenant_id);
CREATE INDEX IF NOT EXISTS risks_tenant_updated_idx ON risks (tenant_id, updated_at DESC);
