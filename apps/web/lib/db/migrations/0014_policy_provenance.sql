-- Provenance for AI-authored policy drafts (Policy Builder Agent). An AI-generated draft is
-- a normal `policies` row (status='draft') that flows through the existing human-gated
-- workflow unchanged (in_review -> published still requires the `publish` permission) — these
-- columns only make the authorship and grounding explainable (CLAUDE.md §19), they do not
-- change the approval workflow itself.
ALTER TABLE policies
  ADD COLUMN ai_generated boolean NOT NULL DEFAULT false,
  ADD COLUMN generated_by_tool text,
  ADD COLUMN generation_metadata jsonb;

COMMENT ON COLUMN policies.generation_metadata IS
  'When ai_generated: {"model", "promptVersion", "confidence", "citations": [...], "sourceDocumentIds": [...], "invocationId"} — invocationId references ai_tool_invocations.id.';
