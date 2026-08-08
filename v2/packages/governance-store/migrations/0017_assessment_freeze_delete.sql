-- Rasheed V2 — Assessment Freeze, corrected for DELETE (fixes 0014).
--
-- PROPERTY THIS MIGRATION PROVES: a DELETE on an OPEN assessment's rows actually deletes them.
--
-- 0014 wrote the guard as `RETURN NEW`. In a BEFORE INSERT/UPDATE trigger that is correct. In a
-- BEFORE DELETE trigger `NEW` is NULL, and a BEFORE ROW trigger that returns NULL **cancels the
-- operation** — without an error, without a warning, with `rowcount = 0`. So the guard written to
-- refuse writes to a CONCLUDED assessment was in fact swallowing every DELETE on `sector_answers`
-- and `template_selections`, including on assessments that were still open.
--
-- The refusals never depended on the return value — they `RAISE`, which aborts before any return —
-- so the property 0014 set out to prove was never weakened. What was wrong is the permitted path:
-- it reported success and did nothing. That is the failure mode this whole family of triggers
-- exists to prevent, arriving through the trigger itself: a database that hides the outcome of an
-- operation instead of refusing it outright.
--
-- Found in production, not in review: a cleanup deleted one open assessment's rows, reported
-- three rows removed, and the foreign key then refused the parent because the children were still
-- there.
--
-- `COALESCE(NEW, OLD)` is the whole fix. On INSERT/UPDATE it is NEW, unchanged. On DELETE it is
-- OLD, which is what a BEFORE DELETE trigger must return to let the delete proceed.
--
-- Corrective rather than an edit to 0014: migrations here are re-applied on every release with no
-- apply-tracking ledger (ADR 0045), so a silent edit to an applied file would leave no trace that
-- the behaviour ever changed. `CREATE OR REPLACE` makes this idempotent and re-runnable; the
-- triggers in 0014 keep pointing at the same function name and need no change.

CREATE OR REPLACE FUNCTION assessment_must_be_open() RETURNS trigger AS $$
DECLARE
    finished timestamptz;
    target   text;
BEGIN
    -- OLD on DELETE, NEW otherwise — the row whose assessment is being checked.
    target := COALESCE(NEW.assessment_id, OLD.assessment_id);
    SELECT completed_at INTO finished FROM assessments WHERE id = target;
    IF finished IS NOT NULL THEN
        RAISE EXCEPTION
            'assessment % concluded at % and accepts no further writes (ADR 0067): open a new '
            'assessment instead of changing a finished one', target, finished;
    END IF;
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;
