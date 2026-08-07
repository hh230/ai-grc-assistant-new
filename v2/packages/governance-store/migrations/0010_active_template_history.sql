-- Rasheed V2 — Sector Knowledge Packs — active_template_history (ADR 0067 §4).
--
-- PROPERTY THIS MIGRATION PROVES: the activation record is append-only — "what was live at 10:30?"
-- stays answerable forever.
--
-- `active_templates` holds one row per industry and is overwritten on every activation, which is
-- exactly what makes rollback cheap. That row alone therefore cannot answer what was live an hour
-- ago; this table does. Written by the same transaction that moves the pointer.
--
-- Append-only is enforced, not assumed: UPDATE and DELETE both raise. An audit trail that can be
-- rewritten is not an audit trail.

CREATE TABLE IF NOT EXISTS active_template_history (
    id            bigserial   PRIMARY KEY,
    industry_slug text        NOT NULL REFERENCES industries(slug),
    release_id    text        NOT NULL REFERENCES template_releases(id),
    activated_by  text        NOT NULL,
    activated_at  timestamptz NOT NULL DEFAULT now(),
    -- Why the pointer moved. A rollback and a routine upgrade look identical without it.
    reason        text        NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS active_template_history_industry_idx
    ON active_template_history (industry_slug, activated_at DESC);

CREATE OR REPLACE FUNCTION active_template_history_append_only() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION
        'active_template_history is append-only (ADR 0067 §4): the record of what was live must '
        'not be rewritten';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS active_template_history_append_only_trg ON active_template_history;
CREATE TRIGGER active_template_history_append_only_trg
    BEFORE UPDATE OR DELETE ON active_template_history
    FOR EACH ROW EXECUTE FUNCTION active_template_history_append_only();
