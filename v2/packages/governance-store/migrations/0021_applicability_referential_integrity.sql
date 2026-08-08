-- Rasheed V2 — Signal Resolution (ADR 0068): the references become enforced, and tenant-safe.
--
-- PROPERTY THIS MIGRATION PROVES: an applicability version cannot describe a session that does not
-- exist, a plan cannot cite an analysis that does not exist, and neither reference can cross a
-- tenant boundary.
--
-- 0018 and 0020 wrote `session_id` and `source_applicability_id` as plain text. Review caught what
-- that permits, by doing it: deleting a session left its version behind as an orphan, and a plan
-- was pointed at a version id that had never existed. Both were accepted silently. An unenforced
-- reference is a comment about intent.
--
-- COMPOSITE, not simple. `sector_answers` already does this (`0015_assessment_tenant_binding`):
-- `FOREIGN KEY (assessment_id, tenant_id) REFERENCES assessments(id, tenant_id)`. A simple FK on
-- the id alone would let a row in tenant A cite a row in tenant B — the id would resolve, and the
-- isolation would depend on every query remembering to filter. Tenant isolation belongs in the
-- schema (CLAUDE.md §20), so the tenant travels in the key.
--
-- The composite form needs a unique key on the parent's `(id, tenant_id)`, which `assessments`
-- gained in 0015 for exactly this reason and which `discovery_sessions` gains below. Both are
-- additive: `id` is already the primary key, so the pair is unique by construction and the index
-- cannot fail on existing data.
--
-- On NULL: `source_applicability_id` is nullable and `tenant_id` is not. Under MATCH SIMPLE (the
-- default) a composite FK is satisfied whenever ANY column is NULL, so a plan with no recorded
-- version still inserts — which is required, because plans that predate this table keep NULL.

-- --- the unique keys the composite references need ------------------------------------------

-- Guarded on the table's existence, like everything below: the ADR 0067 knowledge fixture builds
-- a database from migrations 4 and up, where neither `discovery_sessions` (0002) nor
-- `governance_plans` (0003) exists. Verified by running it, not assumed.
DO $$
BEGIN
    IF to_regclass('public.discovery_sessions') IS NOT NULL THEN
        BEGIN
            ALTER TABLE discovery_sessions ADD CONSTRAINT discovery_sessions_id_tenant_key
                UNIQUE (id, tenant_id);
        EXCEPTION
            WHEN duplicate_table THEN NULL;   -- already applied; migrations re-run every release
            WHEN duplicate_object THEN NULL;
        END;
    END IF;
END
$$;

DO $$
BEGIN
    ALTER TABLE session_applicability_versions ADD CONSTRAINT applicability_versions_id_tenant_key
        UNIQUE (id, tenant_id);
EXCEPTION
    WHEN duplicate_table THEN NULL;
    WHEN duplicate_object THEN NULL;
END
$$;

-- --- a version belongs to a real session, in the same tenant --------------------------------

DO $$
BEGIN
    IF to_regclass('public.discovery_sessions') IS NOT NULL THEN
        BEGIN
            ALTER TABLE session_applicability_versions
                ADD CONSTRAINT applicability_versions_session_tenant_fk
                FOREIGN KEY (session_id, tenant_id) REFERENCES discovery_sessions (id, tenant_id);
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END;
    END IF;
END
$$;

-- --- a plan cites a real analysis, in the same tenant ----------------------------------------
--
-- Guarded on the table's existence for the same reason as 0020: the ADR 0067 knowledge fixture
-- builds a database from migrations 4 and up, where `governance_plans` does not exist.

DO $$
BEGIN
    IF to_regclass('public.governance_plans') IS NOT NULL THEN
        BEGIN
            ALTER TABLE governance_plans
                ADD CONSTRAINT governance_plans_applicability_tenant_fk
                FOREIGN KEY (source_applicability_id, tenant_id)
                REFERENCES session_applicability_versions (id, tenant_id);
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END;
    END IF;
END
$$;
