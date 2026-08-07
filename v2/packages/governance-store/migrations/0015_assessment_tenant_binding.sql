-- Rasheed V2 — Sector Knowledge Packs — the tenant binding (ADR 0067 §4).
--
-- PROPERTY THIS MIGRATION PROVES: a child row cannot claim a different tenant from the assessment
-- it belongs to. Not "does not today" — cannot.
--
-- `tenant_id` is denormalised onto `template_selections` and `sector_answers` so every query can
-- filter on it directly. Until now nothing tied those copies to the parent: the columns agreed by
-- convention. A repository that always passes the right value is not a guarantee — it is a habit
-- that holds until the first caller who does not, and the caller who does not is the attacker.
--
-- Concretely, what was possible before: tenant B posting to tenant A's assessment id wrote a row
-- stamped `tenant_id = B` under A's assessment, and `record_selection`'s upsert would have
-- REPLACED A's chosen releases with B's. After this, both are foreign key violations.
--
-- This is the same technique 0009 uses for `(release_id, release_status)`, applied to the other
-- invariant we had stated in prose and never modelled. The database invents no rule here; it
-- refuses a state that was always outside the domain.
--
-- Touches existing tables — approved explicitly, and non-destructive: it adds constraints and
-- drops two now-redundant single-column foreign keys the composite ones subsume.

-- The composite key a child row can point at. `id` is already unique on its own, so this adds no
-- new restriction to `assessments` — it only makes the pair referenceable.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'assessments_id_tenant_key'
    ) THEN
        ALTER TABLE assessments ADD CONSTRAINT assessments_id_tenant_key UNIQUE (id, tenant_id);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'template_selections_assessment_tenant_fk'
    ) THEN
        ALTER TABLE template_selections
            ADD CONSTRAINT template_selections_assessment_tenant_fk
            FOREIGN KEY (assessment_id, tenant_id) REFERENCES assessments (id, tenant_id);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'sector_answers_assessment_tenant_fk'
    ) THEN
        ALTER TABLE sector_answers
            ADD CONSTRAINT sector_answers_assessment_tenant_fk
            FOREIGN KEY (assessment_id, tenant_id) REFERENCES assessments (id, tenant_id);
    END IF;
END $$;

-- The single-column foreign keys are now implied by the composite ones: a row that satisfies
-- (assessment_id, tenant_id) necessarily satisfies (assessment_id). Keeping both would charge
-- every insert twice for one guarantee.
ALTER TABLE template_selections DROP CONSTRAINT IF EXISTS template_selections_assessment_id_fkey;
ALTER TABLE sector_answers      DROP CONSTRAINT IF EXISTS sector_answers_assessment_id_fkey;
