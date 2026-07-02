-- Mandatory document classification (V2-P2.5 upload wizard). Backfill existing rows to
-- "other" before enforcing NOT NULL so this stays a safe, standard additive migration.
ALTER TABLE documents ADD COLUMN category text;
UPDATE documents SET category = 'other' WHERE category IS NULL;
ALTER TABLE documents ALTER COLUMN category SET NOT NULL;
