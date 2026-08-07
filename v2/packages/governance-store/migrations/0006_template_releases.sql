-- Rasheed V2 — Sector Knowledge Packs — template_releases (ADR 0067 §4, §6, §7, §8).
--
-- PROPERTIES THIS MIGRATION PROVES:
--   1. a version number is unique within its template;
--   2. a released asset can never be deleted, nor its content or provenance changed (Knowledge
--      Freeze, §7) — enforced by triggers, because no declarative constraint can express "this
--      row is frozen from now on";
--   3. `(id, status)` is uniquely addressable, which is what lets 0009 make "activate something
--      that was never released" unrepresentable without a trigger.
--
-- The provenance trio (§6) is NOT NULL on purpose: `why_we_ask` answers why a question is asked;
-- these answer how it came to exist. A model version alone is not enough — the same model with a
-- revised prompt is a different generator, and so is the same prompt run by changed code. A
-- release that cannot say all three cannot be reproduced, and an output that cannot be reproduced
-- cannot be audited (CLAUDE.md §19).

CREATE TABLE IF NOT EXISTS template_releases (
    id                 text        PRIMARY KEY,
    template_id        text        NOT NULL REFERENCES knowledge_templates(id),
    version            integer     NOT NULL,
    status             text        NOT NULL DEFAULT 'draft',
    expected_outputs   jsonb       NOT NULL DEFAULT '[]'::jsonb,
    -- Reproduction metadata (§6). Never nullable.
    generated_by_model text        NOT NULL,
    prompt_version     text        NOT NULL,
    generator_commit   text        NOT NULL,
    created_by         text        NOT NULL,
    approved_by        text,
    approved_at        timestamptz,
    released_at        timestamptz,
    created_at         timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT template_releases_version_positive CHECK (version >= 1),
    CONSTRAINT template_releases_version_unique UNIQUE (template_id, version),
    CONSTRAINT template_releases_status_known CHECK (
        status IN ('draft', 'in_review', 'approved', 'released',
                   'superseded', 'deprecated', 'archived')
    ),
    -- §8: approval without a recorded identity is not an approval — it is the record of who
    -- accepted content every organization in the sector will be asked.
    CONSTRAINT template_releases_approved_has_identity CHECK (
        status NOT IN ('approved', 'released', 'superseded', 'deprecated', 'archived')
        OR (approved_by IS NOT NULL AND approved_at IS NOT NULL)
    ),
    -- Backs the composite foreign key in 0009. Redundant with the primary key by design.
    CONSTRAINT template_releases_id_status_unique UNIQUE (id, status)
);

CREATE INDEX IF NOT EXISTS template_releases_template_idx ON template_releases (template_id);
CREATE INDEX IF NOT EXISTS template_releases_status_idx   ON template_releases (status);

-- ── Knowledge Freeze (§7) ────────────────────────────────────────────────────────────────────
-- A release that has ever been released is immutable, INCLUDING how it was made. Freezing the
-- questions alone would leave the prompt version or model editable afterwards, and the provenance
-- in §6 would then describe a generator that no longer exists — reproduction metadata that cannot
-- reproduce. Immutability has to cover the whole production path or it guarantees nothing.
--
-- Status may still move forward (released -> superseded -> deprecated -> archived); nothing else
-- may change, and the row may never be deleted (§8: a report issued a year ago must remain
-- literally reconstructable).
CREATE OR REPLACE FUNCTION template_releases_freeze() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION
            'knowledge is never deleted (ADR 0067 §8): release % is %, move it to deprecated or '
            'archived instead', OLD.id, OLD.status;
    END IF;

    IF OLD.status IN ('released', 'superseded', 'deprecated', 'archived') THEN
        IF NEW.version           IS DISTINCT FROM OLD.version
        OR NEW.template_id       IS DISTINCT FROM OLD.template_id
        OR NEW.expected_outputs  IS DISTINCT FROM OLD.expected_outputs
        OR NEW.generated_by_model IS DISTINCT FROM OLD.generated_by_model
        OR NEW.prompt_version    IS DISTINCT FROM OLD.prompt_version
        OR NEW.generator_commit  IS DISTINCT FROM OLD.generator_commit THEN
            RAISE EXCEPTION
                'Knowledge Freeze (ADR 0067 §7): release % has been released; its content and '
                'provenance are immutable. Produce a new release instead.', OLD.id;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS template_releases_freeze_trg ON template_releases;
CREATE TRIGGER template_releases_freeze_trg
    BEFORE UPDATE OR DELETE ON template_releases
    FOR EACH ROW EXECUTE FUNCTION template_releases_freeze();
