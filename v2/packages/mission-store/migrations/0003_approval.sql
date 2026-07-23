-- Rasheed V2 — Mission Store — add the mission's optional human-approval request (ADR 0044, Slice 1).
-- Applied to the ISOLATED V2 database (default: rasheed_v2). Does not touch V1's `aigrc`.
--
-- ADR 0044 makes the human-approval `ApprovalRequest` a value object owned by the Mission aggregate
-- (§1), persisted WITH the mission through the frozen MissionStorePort. The real missions schema
-- stores each nested collection in its own JSONB column (roles / plan / plan_versions /
-- step_results), so the approval rides in its own nullable JSONB column — added here rather than in
-- the frozen 0001 migration.
--
-- This is a purely ADDITIVE, backward-compatible change: the column is NULLABLE with no default, so
-- every existing (version-1) row keeps NULL — which the codec reads as "no approval" (approval=None).
-- New writes stamp payload_schema_version = 2 and populate this column only when a gate is active.
-- `IF NOT EXISTS` keeps it idempotent, matching the rest of the V2 migration style.
--
-- Kept in lock-step with mission_store/schema.py (the schema parity test enforces it).

ALTER TABLE missions ADD COLUMN IF NOT EXISTS approval jsonb;
