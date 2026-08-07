-- Rasheed V2 — Sector Knowledge Packs — active_templates (ADR 0067 §4).
--
-- PROPERTIES THIS MIGRATION PROVES:
--   1. an industry can never have two active releases — the primary key IS the guarantee;
--   2. a release that was never `released` can never be activated — enforced declaratively by a
--      composite foreign key, not by a trigger and not by application code.
--
-- WHY A POINTER AND NOT "the newest release wins" (§4, alternative D): publish v4 at 10:00, find
-- a bad question at 11:00. Under "newest wins", undoing it requires minting a v5 that exists only
-- to reverse a mistake — polluting the version history, and still losing the record of what was
-- actually live between 10:00 and 11:00. Here, rollback is ONE UPDATE of `release_id`; every
-- release row is untouched, and 0010 keeps the history of what was live and when.
--
-- The composite FK to `(id, status)` plus the CHECK is what makes rule 2 declarative. ON UPDATE
-- CASCADE is deliberate: if a release is later moved out of `released`, the cascade rewrites this
-- row's `release_status`, which then violates the CHECK — so a release cannot be demoted while it
-- is the active one. That is the correct behaviour, not an accident.

CREATE TABLE IF NOT EXISTS active_templates (
    industry_slug  text        PRIMARY KEY REFERENCES industries(slug),
    release_id     text        NOT NULL,
    release_status text        NOT NULL,
    activated_by   text        NOT NULL,
    activated_at   timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT active_templates_must_be_released CHECK (release_status = 'released'),
    CONSTRAINT active_templates_release_fk
        FOREIGN KEY (release_id, release_status)
        REFERENCES template_releases (id, status)
        ON UPDATE CASCADE
);

CREATE INDEX IF NOT EXISTS active_templates_release_idx ON active_templates (release_id);
