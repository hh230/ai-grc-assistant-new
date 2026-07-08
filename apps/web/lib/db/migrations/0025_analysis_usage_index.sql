-- Beta usage limits: each authenticated user may start at most N document analyses per
-- calendar day (see lib/analysis/usage.ts). We enforce this by counting existing rows in
-- `analyses` per `requested_by_user_id` for the current day — every analysis run already
-- inserts exactly one row carrying the requester and a `created_at` timestamp, so no new
-- table or column is needed. This purely-additive index makes that per-user, per-day count
-- cheap. Existing users, documents, and analyses are untouched.
CREATE INDEX IF NOT EXISTS analyses_requested_by_created_at_idx
  ON analyses (requested_by_user_id, created_at);
