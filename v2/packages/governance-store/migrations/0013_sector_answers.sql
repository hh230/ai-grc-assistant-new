-- Rasheed V2 — Sector Knowledge Packs — sector_answers (ADR 0067 §2, §4).
--
-- PROPERTY THIS MIGRATION PROVES: a sector answer belongs to an assessment AND to the exact
-- release question it answers — and it is NOT a signal.
--
-- A Signal is a fact the decision engine relies on, and the knowledge register guarantees every
-- signal drives a rule. "Do you hold a FAL licence?" is true of real estate and meaningless
-- everywhere else; admitting it to the signal space would break that guarantee for every sector
-- added afterwards. Sector answers travel their own path:
--
--     Discovery Answers -> Core Signals -> Sector Answers -> Plan Context
--
-- That is why this table exists at all instead of more rows in `discovery_answers`.
--
-- The composite foreign key is the point: an answer cannot reference a question that is not in
-- the release it claims to answer.

CREATE TABLE IF NOT EXISTS sector_answers (
    assessment_id text        NOT NULL REFERENCES assessments(id),
    release_id    text        NOT NULL,
    question_id   text        NOT NULL,
    tenant_id     text        NOT NULL,
    -- jsonb, not text: the answer's shape follows the question's type (boolean/enum/numeric/
    -- date/text), and flattening it to a string would lose that distinction at the boundary.
    answer        jsonb,
    answered_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (assessment_id, release_id, question_id),
    FOREIGN KEY (release_id, question_id)
        REFERENCES release_questions (release_id, question_id)
);

CREATE INDEX IF NOT EXISTS sector_answers_assessment_idx ON sector_answers (assessment_id);
CREATE INDEX IF NOT EXISTS sector_answers_tenant_idx     ON sector_answers (tenant_id);
