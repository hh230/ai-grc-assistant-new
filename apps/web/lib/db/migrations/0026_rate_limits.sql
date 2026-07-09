-- Fixed-window rate-limit counters, shared across every serverless instance (replaces the
-- old in-memory Map, which gave each instance its own independent counter). One row per
-- bucket key (e.g. "login:1.2.3.4:user@example.com", "chat:tenant:<id>"); a single atomic
-- upsert both increments and resets the window, so concurrent requests can't race past the
-- limit.
CREATE TABLE IF NOT EXISTS rate_limit_buckets (
  bucket_key text PRIMARY KEY,
  count integer NOT NULL DEFAULT 0,
  reset_at timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS rate_limit_buckets_reset_at_idx ON rate_limit_buckets (reset_at);
