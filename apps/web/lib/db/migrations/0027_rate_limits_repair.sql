-- Repairs `rate_limit_buckets` in environments where it already existed under a different
-- shape before migration 0026 ran (production hit "column bucket_key of relation
-- rate_limit_buckets does not exist" — the table was already present, so 0026's
-- `CREATE TABLE IF NOT EXISTS` silently no-op'd and never added the columns the app needs).
--
-- Additive only: never drops a column, constraint, or row. Safe to run whether the table
-- doesn't exist yet, already has the correct 0026 shape, or exists with something else
-- entirely — every step is idempotent and guarded.

CREATE TABLE IF NOT EXISTS rate_limit_buckets ();

ALTER TABLE rate_limit_buckets ADD COLUMN IF NOT EXISTS bucket_key text;
ALTER TABLE rate_limit_buckets ADD COLUMN IF NOT EXISTS count integer NOT NULL DEFAULT 0;
ALTER TABLE rate_limit_buckets ADD COLUMN IF NOT EXISTS reset_at timestamptz;

-- Backfill only what's needed to satisfy the NOT NULL/UNIQUE constraints below. These are
-- throttling counters with no business meaning outside their own row, so a synthetic key and
-- an already-expired reset_at (harmless — the next request just rolls the window over) are
-- sufficient; nothing here is user-facing data.
UPDATE rate_limit_buckets
   SET bucket_key = 'legacy:' || ctid::text
 WHERE bucket_key IS NULL;
UPDATE rate_limit_buckets
   SET reset_at = now()
 WHERE reset_at IS NULL;

ALTER TABLE rate_limit_buckets ALTER COLUMN bucket_key SET NOT NULL;
ALTER TABLE rate_limit_buckets ALTER COLUMN reset_at SET NOT NULL;

-- If an old schema had its own NOT NULL column(s) with no default (anything other than the
-- three above), the app's insert — which only ever sets bucket_key/count/reset_at — would
-- fail on those instead. Relax them to nullable rather than dropping them, so old columns
-- and their historical data stay intact but no longer block new rows.
DO $$
DECLARE
  col record;
BEGIN
  FOR col IN
    SELECT column_name FROM information_schema.columns
     WHERE table_schema = 'public' AND table_name = 'rate_limit_buckets'
       AND is_nullable = 'NO' AND column_default IS NULL
       AND column_name NOT IN ('bucket_key', 'count', 'reset_at')
  LOOP
    EXECUTE format('ALTER TABLE rate_limit_buckets ALTER COLUMN %I DROP NOT NULL', col.column_name);
  END LOOP;
END $$;

-- `checkRateLimit`'s `ON CONFLICT (bucket_key)` upsert needs a unique constraint on
-- bucket_key — add one if the column pre-dates this migration without it. Does not assume
-- (or force) bucket_key to be the primary key, in case an old schema already has one.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'rate_limit_buckets_bucket_key_key'
  ) THEN
    ALTER TABLE rate_limit_buckets ADD CONSTRAINT rate_limit_buckets_bucket_key_key UNIQUE (bucket_key);
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS rate_limit_buckets_reset_at_idx ON rate_limit_buckets (reset_at);
