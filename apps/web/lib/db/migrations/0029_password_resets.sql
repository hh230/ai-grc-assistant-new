-- One-time, expiring password-reset tokens (mirrors `invitations`, 0024_access_onboarding.sql).
-- Only the sha256 hash of the raw token is ever persisted — a database dump cannot hand out
-- usable credentials. Scoped to `user_id` (not email) since the account already exists.
CREATE TABLE IF NOT EXISTS password_reset_tokens (
  id text PRIMARY KEY,
  user_id text NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  token_hash text NOT NULL UNIQUE,
  expires_at timestamptz NOT NULL,
  used_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS password_reset_tokens_user_idx
  ON password_reset_tokens (user_id, created_at DESC);
