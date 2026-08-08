-- Rasheed V2 — Signal Resolution (ADR 0068): a sector question may DECLARE the signal it writes.
--
-- PROPERTY THIS MIGRATION PROVES: a question that claims to write a signal cannot exist without a
-- complete, explicit map from its options to that signal's values.
--
-- The map is keyed by a stable `option_id`, never by the option's text. Arabic wording gets
-- revised, an English translation gets added, a typo gets fixed — and none of that may move a
-- compliance decision. Keying on text would make a translator's edit a governance event.
--
-- `signal_value_map` is `{option_id: value}` where `value` may be JSON `null`, and null is a
-- DECISION, not a gap: "we don't know" contributes nothing. The resolver drops nulls before it
-- merges, so an unanswered question, an unknown option and a declared-null boolean branch all
-- behave the same way — they leave the signal alone. What they must never do is become `false`.
-- Boolean questions use the same mechanism with the reserved ids 'true' and 'false', so there is
-- one declaration shape for every question type rather than one per type.
--
-- Completeness in BOTH directions (every option has an entry, every entry has an option) is
-- checked by `grc_api.signal_declarations` at seed time, where the option list is in hand. What
-- the schema can state on its own, it states here: a declaration without a map is refused.

ALTER TABLE release_questions
    ADD COLUMN IF NOT EXISTS writes_signal    text,
    ADD COLUMN IF NOT EXISTS signal_value_map jsonb;

DO $$
BEGIN
    ALTER TABLE release_questions
        ADD CONSTRAINT release_questions_signal_map_ck
        CHECK (writes_signal IS NULL OR signal_value_map IS NOT NULL);
EXCEPTION
    WHEN duplicate_object THEN NULL;   -- already applied; migrations re-run every release
END
$$;
