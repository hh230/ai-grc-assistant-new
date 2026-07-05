-- Lightweight Mission record (CLAUDE.md §8) scoped to Policy Intelligence runs only — not the
-- full generic Workflow Engine (apps/workflow stays out of scope). Enough to make a Policy
-- Hunter/Analyst/Builder run visible, steerable, and auditable in the workspace: a goal, a
-- status, its steps, and whether it is awaiting human approval. Generalize into a
-- platform-wide missions table later if/when apps/workflow lands.
CREATE TABLE IF NOT EXISTS policy_missions (
  id text PRIMARY KEY,
  tenant_id text NOT NULL,
  agent text NOT NULL,
  goal text NOT NULL,
  status text NOT NULL,
  awaiting_approval boolean NOT NULL DEFAULT false,
  created_by_user_id text NOT NULL,
  created_by_name text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS policy_missions_tenant_created_idx
  ON policy_missions (tenant_id, created_at DESC);

CREATE TABLE IF NOT EXISTS policy_mission_steps (
  id text PRIMARY KEY,
  mission_id text NOT NULL REFERENCES policy_missions (id) ON DELETE CASCADE,
  position integer NOT NULL,
  step text NOT NULL,
  detail text NOT NULL,
  citations jsonb NOT NULL DEFAULT '[]',
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS policy_mission_steps_mission_idx
  ON policy_mission_steps (mission_id, position);
