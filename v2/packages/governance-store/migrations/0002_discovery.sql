-- Rasheed V2 — Governance Store — discovery_sessions + discovery_answers (ADR 0066 §2).
-- Applied to the ISOLATED V2 database (default: rasheed_v2). Does not touch V1's `aigrc`.
--
-- discovery_sessions: one adaptive-interview run. `active_pack_ids` is the live, composable set
-- of Knowledge Packs (ADR 0066 §2.1), recomputed every turn; `pack_versions` pins the exact
-- version of every pack that contributed a question or rule, for reproducibility even after a
-- pack file is later updated (CLAUDE.md §19). `applicability` is written exactly once, atomically,
-- by the Tier B one-shot analysis pass when status transitions to 'concluded' — never
-- incrementally, so there is never a partial result to read mid-interview.
--
-- discovery_answers: append-only audit/replay log (never updated). Re-answering a question
-- inserts a new row at a later `sequence` for the same question_id; the engine treats the latest
-- per question_id as authoritative. `raw_answer` shape depends on the question's Signal
-- `value_type` (boolean/enum/numeric/date/percentage/evidence_backed — ADR 0066 §2.3); it is
-- nullable — NULL means the question was explicitly SKIPPED (an optional question given no
-- value), distinct from a real answer. This is what makes both Tier A routing and Tier B
-- analysis reproducible (CLAUDE.md §19).
--
-- Kept in lock-step with governance_store/schema.py (the schema parity test enforces it).

CREATE TABLE IF NOT EXISTS discovery_sessions (
    id                     text             PRIMARY KEY,
    tenant_id              text             NOT NULL,
    status                 text             NOT NULL,
    active_pack_ids        jsonb            NOT NULL DEFAULT '[]'::jsonb,
    pack_versions          jsonb            NOT NULL DEFAULT '{}'::jsonb,
    current_question_id    text,
    signals                jsonb            NOT NULL DEFAULT '{}'::jsonb,
    confidence_score       double precision NOT NULL DEFAULT 0,
    applicability          jsonb,
    created_at             double precision NOT NULL,
    updated_at             double precision NOT NULL,
    concluded_at           double precision
);

CREATE INDEX IF NOT EXISTS discovery_sessions_tenant_idx ON discovery_sessions (tenant_id);
CREATE INDEX IF NOT EXISTS discovery_sessions_tenant_status_idx
    ON discovery_sessions (tenant_id, status);

CREATE TABLE IF NOT EXISTS discovery_answers (
    id                     text             PRIMARY KEY,
    session_id             text             NOT NULL REFERENCES discovery_sessions(id),
    tenant_id              text             NOT NULL,
    sequence               integer          NOT NULL,
    question_id            text             NOT NULL,
    question_version       text             NOT NULL,
    raw_answer             jsonb,
    resolved_signal_key    text,
    resolved_signal_value  text,
    normalized_by          text             NOT NULL DEFAULT 'direct',
    llm_model_version      text,
    llm_confidence         double precision,
    created_at             double precision NOT NULL
);

CREATE INDEX IF NOT EXISTS discovery_answers_tenant_session_idx
    ON discovery_answers (tenant_id, session_id);
CREATE UNIQUE INDEX IF NOT EXISTS discovery_answers_session_sequence_idx
    ON discovery_answers (session_id, sequence);
