-- Rasheed V2 — Signal Resolution (ADR 0068): applicability becomes VERSIONED.
--
-- PROPERTY THIS MIGRATION PROVES: a decision, once recorded, can never be rewritten — not by a
-- newer knowledge pack, not by a code deploy, not by a second conclusion.
--
-- Until now a session held ONE `applicability`, computed at discovery conclusion. The sector
-- interview happens after that, so a sector answer arrived too late to matter and, by design,
-- reached only the plan's prose. ADR 0068 opens a narrow declared channel — and the moment a
-- decision can be recomputed, "which decision was this plan built on?" stops having an obvious
-- answer. Versioning is what keeps it obvious.
--
--   v1  source='core_conclusion'    written when the discovery interview concludes
--   v2  source='sector_conclusion'  written when the sector assessment concludes, ONCE
--       source='recomputation'      reserved: a future, explicit, human-gated operation. Not a
--                                   re-conclusion, and not built here — the vocabulary is opened
--                                   now so that adding it later needs no ALTER on live data.
--
-- The table is APPEND-ONLY, enforced below rather than promised in prose: a plan drafted last year
-- must still be explicable by the analysis it was actually built from, and the only way to
-- guarantee that is to make the row incapable of changing.

CREATE TABLE IF NOT EXISTS session_applicability_versions (
    id                   text        PRIMARY KEY,
    tenant_id            text        NOT NULL,
    session_id           text        NOT NULL,
    version              integer     NOT NULL,
    source               text        NOT NULL,
    -- Present exactly when the version came from a sector assessment; the CHECK below makes that
    -- an invariant rather than a convention.
    assessment_id        text,
    -- The frozen output. Stored whole, not recomputed on read — that is the entire point.
    applicability        jsonb       NOT NULL,
    -- ResolvedSignal[]: what each signal resolved to and everyone who spoke (ADR 0068 §D6).
    resolved_signals     jsonb       NOT NULL DEFAULT '[]'::jsonb,
    conflicts            jsonb       NOT NULL DEFAULT '[]'::jsonb,
    -- A fingerprint of the inputs, so a reader can tell "same answers" from "same result".
    answer_set_hash      text        NOT NULL,
    -- Which pack versions ruled. Without this, reproducing an old decision means guessing.
    engine_pack_versions jsonb       NOT NULL DEFAULT '{}'::jsonb,
    computed_at          timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT session_applicability_versions_source_ck
        CHECK (source IN ('core_conclusion', 'sector_conclusion', 'recomputation')),
    -- Sector versions carry their assessment; the others must not pretend to.
    CONSTRAINT session_applicability_versions_assessment_ck
        CHECK ((source = 'sector_conclusion') = (assessment_id IS NOT NULL)),
    -- Version 1 is the core conclusion and nothing else can claim to be.
    CONSTRAINT session_applicability_versions_v1_ck
        CHECK ((version = 1) = (source = 'core_conclusion')),
    CONSTRAINT session_applicability_versions_version_ck CHECK (version >= 1)
);

-- One version number per session, and one version per assessment. The second is the structural
-- guard against a sector assessment being concluded twice: `assessments_conclude_once` already
-- makes conclusion one-way, and this makes a SECOND version impossible even if some future caller
-- found a way around it. Two independent guards, because this one is cheap.
CREATE UNIQUE INDEX IF NOT EXISTS session_applicability_versions_session_version_uq
    ON session_applicability_versions (tenant_id, session_id, version);
CREATE UNIQUE INDEX IF NOT EXISTS session_applicability_versions_assessment_uq
    ON session_applicability_versions (tenant_id, assessment_id)
    WHERE assessment_id IS NOT NULL;

-- The read the plan pipeline makes: the newest version of one session, tenant-scoped.
CREATE INDEX IF NOT EXISTS session_applicability_versions_latest_idx
    ON session_applicability_versions (tenant_id, session_id, version DESC);

-- Append-only, enforced.
--
-- `RETURN COALESCE(NEW, OLD)` and not `RETURN NEW`: on DELETE, `NEW` is NULL, and a BEFORE ROW
-- trigger returning NULL CANCELS the operation silently instead of refusing it. That exact line
-- shipped in 0014 and had to be corrected in 0017 — a guard that hides an outcome is worse than
-- no guard. Here every path RAISEs, so the return is unreachable; it is written correctly anyway,
-- because the next person to copy this function will not know that.
CREATE OR REPLACE FUNCTION applicability_versions_are_append_only() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION
        'applicability version % is immutable (ADR 0068): a recorded decision is never rewritten '
        '— record a new version instead', COALESCE(OLD.id, NEW.id);
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS session_applicability_versions_append_only_trg
    ON session_applicability_versions;
CREATE TRIGGER session_applicability_versions_append_only_trg
    BEFORE UPDATE OR DELETE ON session_applicability_versions
    FOR EACH ROW EXECUTE FUNCTION applicability_versions_are_append_only();

-- `governance_plans.source_applicability_id` lives in 0020, and the referential integrity for
-- both new references lives in 0021 — see those files for why each is separate.
