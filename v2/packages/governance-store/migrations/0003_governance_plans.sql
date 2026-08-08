-- Rasheed V2 — Governance Store — governance_plans + governance_plan_items (ADR 0066 §3, §3.1).
-- Applied to the ISOLATED V2 database (default: rasheed_v2). Does not touch V1's `aigrc`.
--
-- governance_plans: the output of the `generate_governance_plan` Mission — IMMUTABLE SNAPSHOTS
-- (§3.1): a new plan is always a new row, never an update to an existing one. `version`/
-- `previous_plan_id` give explicit lineage on top of `status` (active|superseded);
-- `maturity_at_supersession` is stamped only when a newer plan replaces this one. `maturity_
-- baseline` is the full per-dimension rating dict (ADR 0066 §4), frozen at creation.
--
-- governance_plan_items: actionable, trackable records grouped by pillar and timeframe bucket.
-- `timeframe_bucket`/`priority` are the OUTPUT of the deterministic, capacity-aware Scheduler
-- (ADR 0066 §2.5) — never rule-declared constants; `effort_size`/`depends_on_item_ids` are kept
-- for transparency into why the schedule looks the way it does. `source_signal_keys`/
-- `source_framework_refs` carry the traceability CLAUDE.md §19 requires. `resolves_signal` (§5.3)
-- is what a completion writes back through `effective_signals()`; `evidence_ids` (§5.4) is always
-- optional, never a completion gate; `confidence` (§5.6) is computed once at creation.
--
-- governance_plan_events: append-only audit log of status transitions (§5.3/§5.5) — same
-- discipline as `discovery_answers`.
--
-- Kept in lock-step with governance_store/schema.py (the schema parity test enforces it).

CREATE TABLE IF NOT EXISTS governance_plans (
    id                       text             PRIMARY KEY,
    tenant_id                text             NOT NULL,
    source_session_id        text             REFERENCES discovery_sessions(id),
    source_mission_id        text             NOT NULL,
    status                   text             NOT NULL,
    version                  integer          NOT NULL DEFAULT 1,
    previous_plan_id         text             REFERENCES governance_plans(id),
    inferred_frameworks      jsonb            NOT NULL DEFAULT '[]'::jsonb,
    maturity_baseline        jsonb            NOT NULL,
    maturity_at_supersession jsonb,
    executive_summary        text,
    top_risks                jsonb            NOT NULL DEFAULT '[]'::jsonb,
    created_at               double precision NOT NULL,
    updated_at               double precision NOT NULL
);

CREATE INDEX IF NOT EXISTS governance_plans_tenant_idx ON governance_plans (tenant_id);
CREATE INDEX IF NOT EXISTS governance_plans_tenant_status_idx
    ON governance_plans (tenant_id, status);

CREATE TABLE IF NOT EXISTS governance_plan_items (
    id                     text             PRIMARY KEY,
    plan_id                text             NOT NULL REFERENCES governance_plans(id),
    tenant_id              text             NOT NULL,
    pillar                 text             NOT NULL,
    title                  text             NOT NULL,
    title_key              text             NOT NULL DEFAULT '',
    objective              text             NOT NULL,
    objective_key          text             NOT NULL DEFAULT '',
    expected_outcome       text             NOT NULL,
    rationale              text             NOT NULL,
    timeframe_bucket       text             NOT NULL,
    priority               text             NOT NULL,
    effort_size            text             NOT NULL DEFAULT 'medium',
    depends_on_item_ids    jsonb            NOT NULL DEFAULT '[]'::jsonb,
    status                 text             NOT NULL DEFAULT 'not_started',
    due_at                 double precision,
    completed_at           double precision,
    source_signal_keys     jsonb            NOT NULL DEFAULT '[]'::jsonb,
    source_framework_refs  jsonb            NOT NULL DEFAULT '[]'::jsonb,
    resolves_signal        jsonb,
    evidence_ids           jsonb            NOT NULL DEFAULT '[]'::jsonb,
    confidence             double precision,
    risk_if_skipped        text,
    revisit_at             double precision,
    created_at             double precision NOT NULL,
    updated_at             double precision NOT NULL
);

CREATE INDEX IF NOT EXISTS governance_plan_items_tenant_plan_idx
    ON governance_plan_items (tenant_id, plan_id);
CREATE INDEX IF NOT EXISTS governance_plan_items_tenant_plan_pillar_idx
    ON governance_plan_items (tenant_id, plan_id, pillar);
CREATE INDEX IF NOT EXISTS governance_plan_items_tenant_plan_status_idx
    ON governance_plan_items (tenant_id, plan_id, status);
CREATE INDEX IF NOT EXISTS governance_plan_items_tenant_status_idx
    ON governance_plan_items (tenant_id, status);

-- `sequence` is a race-free, monotonically increasing tie-breaker (Postgres IDENTITY, not an
-- app-computed MAX()+1) — `created_at` alone cannot deterministically order two events with the
-- same timestamp (ADR 0066 Phase 3 hardening).
CREATE TABLE IF NOT EXISTS governance_plan_events (
    id                     text             PRIMARY KEY,
    sequence               bigint           GENERATED ALWAYS AS IDENTITY,
    plan_item_id           text             NOT NULL REFERENCES governance_plan_items(id),
    tenant_id              text             NOT NULL,
    event_type             text             NOT NULL,
    actor_id               text             NOT NULL DEFAULT '',
    created_at             double precision NOT NULL
);

-- Additive for a database created before `sequence` existed — see `schema.py`'s `apply_schema`.
ALTER TABLE governance_plan_events ADD COLUMN IF NOT EXISTS sequence bigint GENERATED ALWAYS AS IDENTITY;

-- Likewise additive: the i18n keys behind a plan item's title and objective, kept ALONGSIDE the
-- rendered text rather than instead of it.
--
-- `plan.seed.establish_risk_register.title` is an i18n key — that is what it is and why the rule
-- engine emits one. The draft tool resolved it to English at write time and stored only the
-- result, so the one field that could have been bilingual for free arrived monolingual. A key
-- resolved at write time stops being a key.
--
-- The text columns stay, and stay authoritative: a plan drafted before this existed carries an
-- empty key and must keep rendering exactly as it does today, and a UI with no translation for a
-- key falls back to what was actually stored. Empty string rather than NULL — "this row has no
-- key" is a fact about the row, not something unknown about it.
--
-- These live HERE, beside the table they alter, rather than in a new migration file: the test
-- fixtures apply migrations 4-and-up for the knowledge schema alone, so a plans-schema ALTER in a
-- higher-numbered file runs against a database where `governance_plan_items` does not exist.
ALTER TABLE governance_plan_items ADD COLUMN IF NOT EXISTS title_key     text NOT NULL DEFAULT '';
ALTER TABLE governance_plan_items ADD COLUMN IF NOT EXISTS objective_key text NOT NULL DEFAULT '';

CREATE INDEX IF NOT EXISTS governance_plan_events_tenant_item_idx
    ON governance_plan_events (tenant_id, plan_item_id);
