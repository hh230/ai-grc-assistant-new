-- Saudi Regulations Ingestion Pipeline (Knowledge Intelligence KI-P6, ADR-0030): its own
-- enable/interval/manual-trigger control row, identical in shape to worker_control (KI-P5)
-- and read/written through the exact same WorkerControlRepository class and
-- grc_knowledge_worker.WorkerControlPort contract — a separate row (and therefore an
-- independent cadence) so an admin pausing/rescheduling the Knowledge Worker never affects
-- this pipeline, and vice versa.
CREATE TABLE IF NOT EXISTS regulation_worker_control (
  id text PRIMARY KEY DEFAULT 'default',
  enabled boolean NOT NULL DEFAULT true,
  interval_hours real NOT NULL DEFAULT 24,
  manual_trigger_requested_at timestamptz,
  updated_at timestamptz NOT NULL DEFAULT now(),
  updated_by text,
  CONSTRAINT regulation_worker_control_singleton_check CHECK (id = 'default'),
  CONSTRAINT regulation_worker_control_interval_hours_check CHECK (interval_hours > 0)
);

INSERT INTO regulation_worker_control (id) VALUES ('default') ON CONFLICT (id) DO NOTHING;
