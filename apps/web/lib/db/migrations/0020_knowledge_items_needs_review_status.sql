-- Knowledge Intelligence KI-P5 follow-up (ADR-0025 §6 revised): a fresh discovery can now be
-- stored as either 'discovered' or 'needs_review' — a below-confidence-threshold answer is
-- still real, grounded research (never garbage), but should not look indistinguishable from a
-- confidently-grounded one. 'needs_review' at this point legitimately means "nobody has looked
-- at this yet", so — unlike 'verified'/'outdated', which only a human decision ever produces —
-- it must not be forced to carry a last_verified timestamp.
ALTER TABLE knowledge_items DROP CONSTRAINT knowledge_items_last_verified_required_check;

ALTER TABLE knowledge_items ADD CONSTRAINT knowledge_items_last_verified_required_check CHECK (
  status IN ('discovered', 'needs_review') OR last_verified IS NOT NULL
);
