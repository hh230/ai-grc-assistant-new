-- Rasheed V2 — Sector Knowledge Packs — multi_select questions (ADR 0067 §2).
--
-- PROPERTY THIS MIGRATION PROVES: a question may legitimately have several answers at once, and a
-- question that does still cannot exist without options to choose from.
--
-- WHY: the authored real-estate pack asked "which real-estate activities do you practise?" — and a
-- firm is routinely a broker AND a developer AND a property manager at the same time. The schema
-- could express only "choose one", so the pack's own author had to smuggle the truth into an option
-- reading "أكثر من نشاط" ("more than one activity"), which records that several apply while losing
-- WHICH several. That is a question the product cannot act on, produced by a constraint rather than
-- by a decision.
--
-- Five questions in that pack turned out to be the same shape: activities, government platforms,
-- governance documents, personal-data categories, and PDPL requirements. Each was a registration
-- form wearing a question's clothes.
--
-- The vocabulary stays closed and stays HERE. Adding a member is a reviewed schema change, exactly
-- as `boolean|enum|numeric|date|text` was — the alternative, a free-text `type`, would let any
-- caller (or any model) invent a rendering the interface has never seen.
--
-- Touches an existing table by explicit approval. Non-destructive and additive: it widens what is
-- permitted and narrows nothing, so every row that was valid before is valid after.

DO $$
BEGIN
    -- `multi_select` joins the closed set. Dropped and re-added rather than altered because
    -- PostgreSQL has no ALTER CONSTRAINT for a CHECK.
    ALTER TABLE release_questions DROP CONSTRAINT IF EXISTS release_questions_type_renderable;
    ALTER TABLE release_questions ADD CONSTRAINT release_questions_type_renderable CHECK (
        type IN ('boolean', 'enum', 'multi_select', 'numeric', 'date', 'text')
    );

    -- A choice with fewer than two options is not a choice. The old constraint named `enum`
    -- explicitly; the rule was never about `enum`, it was about choosing, so it now covers both.
    -- Renamed to say what it actually guarantees.
    ALTER TABLE release_questions DROP CONSTRAINT IF EXISTS release_questions_enum_has_options;
    ALTER TABLE release_questions DROP CONSTRAINT IF EXISTS release_questions_choice_has_options;
    ALTER TABLE release_questions ADD CONSTRAINT release_questions_choice_has_options CHECK (
        type NOT IN ('enum', 'multi_select') OR jsonb_array_length(options) >= 2
    );
END $$;

-- `sector_answers.answer` is already `jsonb` and needs no change: an array of chosen options is a
-- valid jsonb value, and the column deliberately never constrained the SHAPE of an answer, only
-- that it belongs to a question in the release it claims (0013's composite foreign key). The shape
-- is the question's business, and the question now says so in its `type`.
