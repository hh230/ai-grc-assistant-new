-- Rasheed V2 — Sector Knowledge Packs — Assessment Freeze (ADR 0067 repository contract).
--
-- PROPERTY THIS MIGRATION PROVES: no write is permitted after an Assessment reaches Concluded.
--
-- The interview is over; what it produced is evidence, and evidence that can still change is not
-- evidence. Three things follow:
--
--   * `load_plan_context` needs no snapshot isolation — there is nothing left to tear. An earlier
--     draft of the contract reached for REPEATABLE READ to stop a concurrent answer producing a
--     context whose questions and answers disagree; that treated the symptom. Freezing the source
--     is stronger, because a snapshot would have made the late write INVISIBLE to the read while
--     still letting it land, leaving a stored plan that disagrees with its own assessment and no
--     error anywhere.
--   * A plan can always be rebuilt from its assessment and produce the identical result
--     (CLAUDE.md §19).
--   * Conclusion becomes a real event with a before and an after, rather than a flag.
--
-- Enforced here rather than only in the repository, for the same reason Knowledge Freeze is: a
-- caller that bypasses the repository must not be able to bypass the rule.
--
-- If a future requirement genuinely needs to change a concluded assessment, the answer is a NEW
-- assessment — the same shape ADR 0067 already uses for knowledge, where a released asset is
-- never edited but superseded.
--
-- `completed_at IS NOT NULL` IS the concluded state; no second column can disagree with it.

CREATE OR REPLACE FUNCTION assessment_must_be_open() RETURNS trigger AS $$
DECLARE
    finished timestamptz;
    target   text;
BEGIN
    target := COALESCE(NEW.assessment_id, OLD.assessment_id);
    SELECT completed_at INTO finished FROM assessments WHERE id = target;
    IF finished IS NOT NULL THEN
        RAISE EXCEPTION
            'assessment % concluded at % and accepts no further writes (ADR 0067): open a new '
            'assessment instead of changing a finished one', target, finished;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS sector_answers_assessment_open_trg ON sector_answers;
CREATE TRIGGER sector_answers_assessment_open_trg
    BEFORE INSERT OR UPDATE OR DELETE ON sector_answers
    FOR EACH ROW EXECUTE FUNCTION assessment_must_be_open();

DROP TRIGGER IF EXISTS template_selections_assessment_open_trg ON template_selections;
CREATE TRIGGER template_selections_assessment_open_trg
    BEFORE INSERT OR UPDATE OR DELETE ON template_selections
    FOR EACH ROW EXECUTE FUNCTION assessment_must_be_open();

-- Re-opening a concluded assessment would defeat everything above, so the transition is one-way.
CREATE OR REPLACE FUNCTION assessments_conclude_once() RETURNS trigger AS $$
BEGIN
    IF OLD.completed_at IS NOT NULL AND NEW.completed_at IS DISTINCT FROM OLD.completed_at THEN
        RAISE EXCEPTION
            'assessment % is already concluded (ADR 0067): conclusion is one-way', OLD.id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS assessments_conclude_once_trg ON assessments;
CREATE TRIGGER assessments_conclude_once_trg
    BEFORE UPDATE ON assessments
    FOR EACH ROW EXECUTE FUNCTION assessments_conclude_once();
