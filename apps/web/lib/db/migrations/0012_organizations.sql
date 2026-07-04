-- V3 Dashboard: real multi-organization membership. A user can belong to more than one
-- organization; the session's `organizationId` (== tenant_id everywhere else in the schema)
-- selects which one is currently active. Because every existing table already scopes by
-- tenant_id (CLAUDE.md §20), switching the active organization is enough to isolate every
-- downstream read/write per company — no other table needs to change.
CREATE TABLE IF NOT EXISTS organizations (
  id text PRIMARY KEY,
  name text NOT NULL,
  org_type text NOT NULL,
  industry text NOT NULL,
  created_by_user_id text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_organizations (
  user_id text NOT NULL,
  organization_id text NOT NULL REFERENCES organizations (id) ON DELETE CASCADE,
  role text NOT NULL DEFAULT 'owner',
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, organization_id)
);

CREATE INDEX IF NOT EXISTS user_organizations_user_id_idx ON user_organizations (user_id);

-- Seed the existing dev tenant so the 7 seeded demo users (lib/auth/users.ts) keep working
-- unchanged and see their current organization as the first entry in the switcher.
INSERT INTO organizations (id, name, org_type, industry, created_by_user_id, created_at)
VALUES ('dev-org', 'Acme Financial Group', 'Enterprise', 'Financial Services', 'dev-user', now())
ON CONFLICT (id) DO NOTHING;

INSERT INTO user_organizations (user_id, organization_id, role)
VALUES
  ('dev-user', 'dev-org', 'owner'),
  ('user-admin', 'dev-org', 'admin'),
  ('user-compliance', 'dev-org', 'compliance_manager'),
  ('user-risk', 'dev-org', 'risk_manager'),
  ('user-analyst', 'dev-org', 'analyst'),
  ('user-auditor', 'dev-org', 'auditor'),
  ('user-viewer', 'dev-org', 'viewer')
ON CONFLICT (user_id, organization_id) DO NOTHING;
