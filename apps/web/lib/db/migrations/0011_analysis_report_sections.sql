-- V2 Production Polish: extends the AI assessment output to a full consulting-report
-- structure — Compliance Overview, Critical Risks, Gap Analysis, Business Impact, overall
-- Priority, References, and Next Actions — alongside the existing summary/findings/
-- frameworks/recommendations. Also records the UI locale the report was generated in, so an
-- Arabic-language analysis can be identified and reproduced for audit (CLAUDE.md §19).
-- `summary` (renamed `executiveSummary` in the application layer) keeps its existing column.

ALTER TABLE analyses
  ADD COLUMN compliance_overview text,
  ADD COLUMN critical_risks jsonb NOT NULL DEFAULT '[]',
  ADD COLUMN gaps jsonb NOT NULL DEFAULT '[]',
  ADD COLUMN business_impact text,
  ADD COLUMN overall_priority jsonb,
  ADD COLUMN reference_list jsonb NOT NULL DEFAULT '[]',
  ADD COLUMN next_actions jsonb NOT NULL DEFAULT '[]',
  ADD COLUMN locale text;
