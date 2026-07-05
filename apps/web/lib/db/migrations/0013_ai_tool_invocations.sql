-- AI transparency & auditability (CLAUDE.md §19): an append-only record of every Tool
-- invocation made by the AI runtime (apps/api), regardless of caller (Orchestrator, API,
-- Scheduled Jobs, ...). Populated by packages/persistence-web from apps/api — apps/web never
-- writes this table directly. Tenant-scoped except for platform-level (cross-tenant) runs,
-- which record tenant_id = NULL (e.g. regulatory-source polling, which is reference data, not
-- tenant data — see the Regulatory Intelligence subsystem).
CREATE TABLE IF NOT EXISTS ai_tool_invocations (
  id text PRIMARY KEY,
  tenant_id text,
  tool_name text NOT NULL,
  tool_version text NOT NULL,
  agent text,
  caller text NOT NULL,
  model text,
  prompt_version text,
  inputs_hash text,
  output_ref text,
  confidence real,
  citations jsonb NOT NULL DEFAULT '[]',
  requires_human_approval boolean NOT NULL DEFAULT false,
  status text NOT NULL,
  error_detail text,
  prompt_tokens integer,
  completion_tokens integer,
  total_tokens integer,
  latency_ms integer,
  cost_usd numeric(12, 6),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ai_tool_invocations_tenant_created_idx
  ON ai_tool_invocations (tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ai_tool_invocations_tool_name_idx
  ON ai_tool_invocations (tool_name, tool_version);
