-- Rasheed V2 — Sector Knowledge Packs — release_questions (ADR 0067 §2, §4).
--
-- PROPERTY THIS MIGRATION PROVES: a question id is unique within its release, because answers are
-- keyed by it — a duplicate would silently overwrite an answer.
--
-- `canonical_text_ar` is the ONLY authored text (§3): Arabic is the single source of truth, and
-- every other language is a row in `question_translations`.
--
-- `why_we_ask` lives here but never leaves the review console (§2). The database cannot enforce
-- that; the API can, and does, by projecting a customer view that omits it.
--
-- What is ABSENT is the point (§2): no writes_signal, no rule, no predicate, no effect, no
-- severity, no maturity_delta, no priority, no plan_seed. Claude authors language, not truth. A
-- column here would be an invitation to put an LLM-asserted fact on the decision path, so none
-- exists — the schema refuses it structurally, not by convention.

CREATE TABLE IF NOT EXISTS release_questions (
    release_id        text        NOT NULL REFERENCES template_releases(id),
    question_id       text        NOT NULL,
    canonical_text_ar text        NOT NULL,
    type              text        NOT NULL,
    options           jsonb       NOT NULL DEFAULT '[]'::jsonb,
    required          boolean     NOT NULL DEFAULT true,
    category          text        NOT NULL,
    importance        text        NOT NULL,
    -- A question may rest on several clauses at once; `clause` inside each entry is optional
    -- because demanding one would push the model to invent clause numbers (§4).
    "references"      jsonb       NOT NULL DEFAULT '[]'::jsonb,
    why_we_ask        text        NOT NULL,
    -- `[]` is a real answer meaning "self-attested". The column is NOT NULL so that "nothing can
    -- prove this" and "nobody decided" stay different facts.
    evidence_required jsonb       NOT NULL DEFAULT '[]'::jsonb,
    position          integer     NOT NULL DEFAULT 0,
    PRIMARY KEY (release_id, question_id),
    CONSTRAINT release_questions_type_renderable CHECK (
        type IN ('boolean', 'enum', 'numeric', 'date', 'text')
    ),
    CONSTRAINT release_questions_importance_known CHECK (
        importance IN ('critical', 'high', 'medium', 'low')
    ),
    CONSTRAINT release_questions_enum_has_options CHECK (
        type <> 'enum' OR jsonb_array_length(options) >= 2
    ),
    CONSTRAINT release_questions_has_a_reference CHECK (jsonb_array_length("references") >= 1)
);

CREATE INDEX IF NOT EXISTS release_questions_release_idx ON release_questions (release_id);
