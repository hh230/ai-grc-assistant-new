-- Rasheed V2 — Sector Knowledge Packs — composite translations (ADR 0069, amends 0008).
--
-- PROPERTY THIS MIGRATION PROVES: every customer-facing string of a question can be translated and
-- audited on its own, and no translation can exist for a question that is not in the release it
-- claims to translate.
--
-- WHY: 0008 stored ONE text per question. A question is three kinds of customer-facing text — its
-- own, its options', and its evidence lines' — so two thirds of what a customer reads had nowhere
-- to live. This widens the row rather than adding a second table: two tables would mean two read
-- paths and two lifecycles for what a customer experiences as one screen.
--
-- WHY NOT extend `release_questions`: that table is INSERT-only by design, because a release is an
-- immutable snapshot of what an organization was actually asked. Adding English to it would mean
-- either updating a published release — breaking the property the whole ADR rests on — or minting
-- twelve new versions whose numbers claim the content changed when not one Arabic word did.
--
-- SAFETY WITH EXISTING ROWS. This does NOT assume the table is empty. Every pre-existing row is a
-- question text by construction (the old schema could store nothing else), so the new columns take
-- correct values from their defaults. `source_text_ar` is added NULLABLE and with no default so
-- that a row which cannot be linked to its source stays visibly unfilled; the backfill fills only
-- what genuinely links, and step 5 ABORTS the migration if anything is left over rather than
-- letting a blank pass a later constraint. The two verification gates run BEFORE the primary key
-- is swapped and before NOT NULL is set, so a failure leaves the table in its old, working shape
-- plus three nullable columns — resumable, never half-migrated.
--
-- The new key is a strict refinement of the old one — the two added columns are constant
-- ('question', 0) for every existing row — so a key collision on existing data is impossible.
--
-- Re-runnable: IF NOT EXISTS, a backfill conditioned on IS NULL, a key swap guarded by
-- pg_constraint, and the house's drop-then-add pattern for CHECKs (see 0016).

DO $$
DECLARE
    stray_kinds  bigint;
    unlinked     bigint;
    key_is_current boolean;
BEGIN
    -- 1-2. The new columns. `source_text_ar` deliberately has no DEFAULT: a row that cannot be
    -- linked to its source must remain NULL and be caught, not be quietly filled with ''.
    ALTER TABLE question_translations
        ADD COLUMN IF NOT EXISTS part_kind      text    NOT NULL DEFAULT 'question',
        ADD COLUMN IF NOT EXISTS part_index     integer NOT NULL DEFAULT 0,
        ADD COLUMN IF NOT EXISTS source_text_ar text;

    -- 3. VERIFICATION GATE ONE. Nothing but question texts could exist before this migration; if
    -- something else is here, this database is not what this migration was written for.
    SELECT count(*) INTO stray_kinds
      FROM question_translations WHERE part_kind <> 'question';
    IF stray_kinds > 0 THEN
        RAISE EXCEPTION
            'migration 0022 aborted: % pre-existing row(s) are not question texts; this table '
            'cannot have held them, so the database differs from what was reviewed', stray_kinds;
    END IF;

    -- 4. BACKFILL, restricted to rows that actually link to their source. The composite foreign
    -- key to release_questions means every row should link; this fills exactly those that do.
    UPDATE question_translations t
       SET source_text_ar = q.canonical_text_ar
      FROM release_questions q
     WHERE q.release_id = t.release_id
       AND q.question_id = t.question_id
       AND t.part_kind = 'question'
       AND t.source_text_ar IS NULL;

    -- 5. VERIFICATION GATE TWO. Anything still unfilled could not be linked to a source, and a
    -- translation whose source is unknown is not a translation anyone can audit.
    SELECT count(*) INTO unlinked
      FROM question_translations WHERE source_text_ar IS NULL;
    IF unlinked > 0 THEN
        RAISE EXCEPTION
            'migration 0022 aborted: % row(s) could not be linked to a source question; refusing '
            'to backfill them silently', unlinked;
    END IF;

    -- 6. Only now, with completeness proven, is the column made mandatory.
    ALTER TABLE question_translations ALTER COLUMN source_text_ar SET NOT NULL;

    -- 7. The key IS the anti-duplication guarantee: one translation per part per language, stated
    -- declaratively rather than trusted to an importer. Guarded so a re-run does not rebuild the
    -- index for nothing.
    SELECT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conname = 'question_translations_pkey'
           AND pg_get_constraintdef(oid) LIKE '%part_kind%'
    ) INTO key_is_current;
    IF NOT key_is_current THEN
        ALTER TABLE question_translations DROP CONSTRAINT IF EXISTS question_translations_pkey;
        ALTER TABLE question_translations ADD CONSTRAINT question_translations_pkey
            PRIMARY KEY (release_id, question_id, language, part_kind, part_index);
    END IF;

    -- 8. A closed vocabulary, here and not in application code — a part kind the interface has
    -- never seen must be unrepresentable, exactly as `type` is on release_questions (0016).
    ALTER TABLE question_translations DROP CONSTRAINT IF EXISTS question_translations_part_known;
    ALTER TABLE question_translations ADD CONSTRAINT question_translations_part_known CHECK (
        part_kind IN ('question', 'option', 'evidence')
    );

    -- A question has exactly one text, so exactly one index. Without this the same question text
    -- could be stored twice under two indices and both would look canonical.
    ALTER TABLE question_translations
        DROP CONSTRAINT IF EXISTS question_translations_question_is_singular;
    ALTER TABLE question_translations
        ADD CONSTRAINT question_translations_question_is_singular CHECK (
            part_kind <> 'question' OR part_index = 0
        );

    ALTER TABLE question_translations
        DROP CONSTRAINT IF EXISTS question_translations_index_non_negative;
    ALTER TABLE question_translations
        ADD CONSTRAINT question_translations_index_non_negative CHECK (part_index >= 0);

    -- The defensive copy is only defensive if it is actually there.
    ALTER TABLE question_translations
        DROP CONSTRAINT IF EXISTS question_translations_source_present;
    ALTER TABLE question_translations
        ADD CONSTRAINT question_translations_source_present CHECK (
            length(btrim(source_text_ar)) > 0
        );
END $$;

-- Deliberately NO new index. The read path filters `release_id = ? AND language = ? AND
-- status = 'published'`, and `release_id` leads the primary key, so the key's own index already
-- answers it — over roughly 268 rows per release at that. CLAUDE.md §23: an index needs a query
-- that cannot already be served, and this one is served. The existing
-- `question_translations_language_status_idx` still answers "which languages are behind".
