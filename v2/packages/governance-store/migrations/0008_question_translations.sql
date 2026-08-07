-- Rasheed V2 — Sector Knowledge Packs — question_translations (ADR 0067 §3).
--
-- PROPERTY THIS MIGRATION PROVES: Arabic can never be stored as a translation.
--
-- Arabic is the single source of truth and lives on the question itself. Storing it again here
-- would create a second copy of the same string, and the first reviewer to edit only one of them
-- forks the question silently — two meanings, no record of which is authoritative. The CHECK makes
-- that unrepresentable rather than merely discouraged.
--
-- A translation has its OWN lifecycle so Arabic can be reviewed without touching English, English
-- without touching Arabic, and a third language added without regenerating any knowledge.

CREATE TABLE IF NOT EXISTS question_translations (
    release_id  text        NOT NULL,
    question_id text        NOT NULL,
    language    text        NOT NULL,
    text        text        NOT NULL,
    status      text        NOT NULL DEFAULT 'generated',
    created_at  timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (release_id, question_id, language),
    FOREIGN KEY (release_id, question_id)
        REFERENCES release_questions (release_id, question_id),
    CONSTRAINT question_translations_never_arabic CHECK (language <> 'ar'),
    CONSTRAINT question_translations_status_known CHECK (
        status IN ('generated', 'reviewed', 'published')
    ),
    CONSTRAINT question_translations_text_present CHECK (length(btrim(text)) > 0)
);

-- "Which languages are behind?" answered without a table scan. Only `published` counts as
-- coverage (§3); a generated-but-unreviewed string is not coverage.
CREATE INDEX IF NOT EXISTS question_translations_language_status_idx
    ON question_translations (language, status);
