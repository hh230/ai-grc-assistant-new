-- AI Worker Control Center (Knowledge Intelligence KI-P5, ADR-0029): durable admin control
-- over the Autonomous Knowledge Worker (KI-P4, ADR-0028) — enable/disable, a configurable
-- learning-cycle interval, and a one-shot manual trigger — plus the run history and
-- append-only activity timeline the Control Center's dashboard reads. Platform-scope, not
-- tenant-scope, matching `knowledge_items` (0018): the worker researches shared
-- GRC/compliance/legal reference knowledge, not any one tenant's data. Both tables were
-- explicitly deferred as future work by ADR-0028 ("no durable last_run_at... no API endpoint,
-- no UI") — this migration is that future work.

-- Singleton control row: exactly one knowledge worker process exists platform-wide, so its
-- admin-configurable settings need exactly one row, not a table keyed by tenant.
CREATE TABLE IF NOT EXISTS worker_control (
  id text PRIMARY KEY DEFAULT 'default',
  enabled boolean NOT NULL DEFAULT true,
  interval_hours real NOT NULL DEFAULT 12,
  manual_trigger_requested_at timestamptz,
  updated_at timestamptz NOT NULL DEFAULT now(),
  updated_by text,
  CONSTRAINT worker_control_singleton_check CHECK (id = 'default'),
  CONSTRAINT worker_control_interval_hours_check CHECK (interval_hours > 0)
);

INSERT INTO worker_control (id) VALUES ('default') ON CONFLICT (id) DO NOTHING;

-- One row per learning cycle that actually ran (scheduled or manual) — "last run"/"next run"
-- and the Learning Reports trend data the Control Center surfaces.
CREATE TABLE IF NOT EXISTS worker_run_history (
  id text PRIMARY KEY,
  reason text NOT NULL,
  started_at timestamptz NOT NULL,
  completed_at timestamptz,
  questions_considered integer NOT NULL DEFAULT 0,
  gaps_detected integer NOT NULL DEFAULT 0,
  items_saved integer NOT NULL DEFAULT 0,
  error_count integer NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT worker_run_history_reason_check CHECK (reason IN ('due', 'manual'))
);

CREATE INDEX IF NOT EXISTS worker_run_history_started_at_idx
  ON worker_run_history (started_at DESC);

-- The append-only activity timeline, and — for the admin-control event types
-- (worker_enabled/disabled, interval_changed, manual_trigger_requested) — the audit trail
-- CLAUDE.md §19/§23 requires for any consequential admin action. Never a model's raw
-- reasoning: `message`/`metadata` are short, already-public operational facts (a count, a
-- status, a source name), by construction of every writer, not enforced by this schema.
CREATE TABLE IF NOT EXISTS worker_events (
  id text PRIMARY KEY,
  event_type text NOT NULL,
  question_id text,
  message text NOT NULL,
  metadata jsonb NOT NULL DEFAULT '{}',
  actor_user_id text,
  actor_tenant_id text,
  occurred_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT worker_events_event_type_check CHECK (
    event_type IN (
      'cycle_started', 'questions_loaded', 'gap_detected', 'source_searched',
      'knowledge_discovered', 'item_saved', 'error', 'cycle_completed',
      'worker_enabled', 'worker_disabled', 'interval_changed', 'manual_trigger_requested'
    )
  )
);

CREATE INDEX IF NOT EXISTS worker_events_occurred_at_idx ON worker_events (occurred_at DESC);
