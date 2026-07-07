-- Invite-Based Access & Organization Onboarding (KI-P9, ADR-0034): replaces the in-memory
-- `SEED_USERS` demo directory (lib/auth/users.ts) with a real, Postgres-backed identity store,
-- plus the public request-access -> admin-approval -> invitation -> account-creation flow that
-- lets a brand-new company self-provision a tenant without a hardcoded seed list or open
-- public signup.

-- The real user directory. `user_organizations` (0012_organizations.sql) already models
-- membership as a join table; it never had a foreign key on `user_id` (there was no `users`
-- table yet), so this migration adds one without touching that table's shape.
CREATE TABLE IF NOT EXISTS users (
  id text PRIMARY KEY,
  email text NOT NULL,
  name text NOT NULL,
  -- scrypt hash — see lib/auth/password.ts. Never a plaintext password.
  password_hash text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS users_email_unique_idx ON users (lower(email));

-- A visitor's request to gain access to the platform (PUBLIC FLOW). Reviewed by an
-- owner/admin; approving one creates an `invitations` row (never a user directly — the
-- requester still has to set their own password via the invite link).
CREATE TABLE IF NOT EXISTS access_requests (
  id text PRIMARY KEY,
  name text NOT NULL,
  email text NOT NULL,
  organization_name text NOT NULL,
  role_title text NOT NULL,
  message text,
  status text NOT NULL DEFAULT 'pending', -- pending | approved | rejected
  created_at timestamptz NOT NULL DEFAULT now(),
  reviewed_at timestamptz,
  reviewed_by text
);

CREATE INDEX IF NOT EXISTS access_requests_status_idx ON access_requests (status, created_at);

-- A one-time, expiring credential that lets its holder create exactly one account. Created
-- only by approving an access request (ADMIN FLOW); the organization named on it does not
-- exist yet and is created at acceptance time (USER FLOW), so this table stores the org name
-- rather than an `organizations.id` foreign key.
CREATE TABLE IF NOT EXISTS invitations (
  id text PRIMARY KEY,
  email text NOT NULL,
  organization_name text NOT NULL,
  invited_role text NOT NULL, -- owner | admin | member
  -- sha256 hex of the raw token. The raw token exists only in the invite URL, never at rest
  -- (mirrors "never store a plaintext password" for the same reason: a DB dump must not hand
  -- out usable credentials).
  token_hash text NOT NULL,
  expires_at timestamptz NOT NULL,
  used_at timestamptz,
  access_request_id text REFERENCES access_requests (id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS invitations_token_hash_unique_idx ON invitations (token_hash);
CREATE INDEX IF NOT EXISTS invitations_email_idx ON invitations (email);
