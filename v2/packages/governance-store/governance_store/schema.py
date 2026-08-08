"""Schema DDL for the Governance Store's five tables (ADR 0066).

Single source of truth for table shape, mirrored by the canonical migrations in `migrations/`
(kept in lock-step by the parity tests in `tests/test_schema.py`) — same discipline as
`mission_store/schema.py` (ADR 0043 §7). This slice ships schema + migrations only: there is no
domain aggregate yet to round-trip (that lands with the Discovery engine and Governance Planning
mission in later phases), so there is no codec/store module here yet, by design.

Every table is tenant-scoped (`tenant_id NOT NULL`) with tenant-first indexes (CLAUDE.md §20).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from governance_store.config import (
    TABLE_DISCOVERY_ANSWERS,
    TABLE_DISCOVERY_SESSIONS,
    TABLE_GOVERNANCE_PLAN_EVENTS,
    TABLE_GOVERNANCE_PLAN_ITEMS,
    TABLE_GOVERNANCE_PLANS,
    TABLE_ORGANIZATION_PROFILES,
)

if TYPE_CHECKING:  # import only for type checkers; the driver is never needed to import this module
    import psycopg

# ---------------------------------------------------------------------------------------------
# organization_profiles — one row per tenant; the org's current structural facts (ADR 0066 §1).
# `active_packs` is the composable set of Knowledge Packs currently applicable (ADR 0066 §2.1) —
# an organization is rarely one industry, so this is a set, never a single label.
# ---------------------------------------------------------------------------------------------
ORGANIZATION_PROFILES_COLUMNS_DDL = """\
    id                     text             PRIMARY KEY,
    tenant_id              text             NOT NULL UNIQUE,
    primary_pack_id        text,
    active_packs           jsonb            NOT NULL DEFAULT '[]'::jsonb,
    size_band              text,
    maturity_level         text,
    signals                jsonb            NOT NULL DEFAULT '{}'::jsonb,
    created_at             double precision NOT NULL,
    updated_at             double precision NOT NULL"""

# ---------------------------------------------------------------------------------------------
# discovery_sessions — one adaptive-interview run (ADR 0066 §2). `applicability` is written
# exactly once, atomically, by the Tier B one-shot analysis pass when status -> 'concluded'.
# `active_pack_ids` is the live, composable set of Knowledge Packs (ADR 0066 §2.1), recomputed
# every turn; `pack_versions` pins the exact version of every pack that contributed a question or
# rule, for reproducibility even after a pack file is later updated (CLAUDE.md §19).
# ---------------------------------------------------------------------------------------------
DISCOVERY_SESSIONS_COLUMNS_DDL = """\
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
    concluded_at           double precision"""

# ---------------------------------------------------------------------------------------------
# discovery_answers — append-only audit/replay log (never updated; re-answering a question
# inserts a new row at a later `sequence`, and the engine treats the latest per question_id as
# authoritative). This is what makes Tier A routing and Tier B analysis reproducible (CLAUDE.md
# §19). `raw_answer` is nullable: NULL means the question was explicitly SKIPPED (an optional
# question with no value given), distinct from a real JSON `null` answer value, which never
# occurs since every direct-entry value type requires a concrete value (`answer_resolution.py`).
# ---------------------------------------------------------------------------------------------
DISCOVERY_ANSWERS_COLUMNS_DDL = """\
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
    created_at             double precision NOT NULL"""

# ---------------------------------------------------------------------------------------------
# governance_plans — the output of the `generate_governance_plan` Mission (ADR 0066 §3). Immutable
# snapshots (§3.1): a new plan is always a new row; `version`/`previous_plan_id` give explicit
# lineage on top of `status` (active|superseded); `maturity_at_supersession` is stamped only when
# a newer plan replaces this one, capturing the live maturity this version actually reached.
# `maturity_baseline` is the full per-dimension rating dict (ADR 0066 §4), frozen at creation —
# never a single summary string.
# ---------------------------------------------------------------------------------------------
GOVERNANCE_PLANS_COLUMNS_DDL = """\
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
    updated_at               double precision NOT NULL"""

# ---------------------------------------------------------------------------------------------
# governance_plan_items — actionable, trackable records grouped by pillar and timeframe bucket.
# `timeframe_bucket`/`priority` are the OUTPUT of the deterministic, capacity-aware Scheduler
# (ADR 0066 §2.5) — never rule-declared constants. `effort_size`/`depends_on_item_ids` are kept
# for transparency into why the schedule looks the way it does. `source_signal_keys`/
# `source_framework_refs` carry the traceability CLAUDE.md §19 requires. `resolves_signal` (§5.3)
# is what a completion writes back through `effective_signals()`; `evidence_ids` (§5.4) is always
# optional, never a completion gate; `confidence` (§5.6) is computed once at creation.
# ---------------------------------------------------------------------------------------------
GOVERNANCE_PLAN_ITEMS_COLUMNS_DDL = """\
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
    updated_at             double precision NOT NULL"""

# ---------------------------------------------------------------------------------------------
# governance_plan_events — append-only audit log of status transitions (ADR 0066 §5.3/§5.5), the
# same discipline as `discovery_answers`: a record of what happened, never a mechanism anything
# else depends on to compute current state (current maturity is always recomputed fresh from
# `effective_signals()`, never read back from this log).
# ---------------------------------------------------------------------------------------------
GOVERNANCE_PLAN_EVENTS_COLUMNS_DDL = """\
    id                     text             PRIMARY KEY,
    sequence               bigint           GENERATED ALWAYS AS IDENTITY,
    plan_item_id           text             NOT NULL REFERENCES governance_plan_items(id),
    tenant_id              text             NOT NULL,
    event_type             text             NOT NULL,
    actor_id               text             NOT NULL DEFAULT '',
    created_at             double precision NOT NULL"""

_COLUMNS_DDL_BY_TABLE = {
    TABLE_ORGANIZATION_PROFILES: ORGANIZATION_PROFILES_COLUMNS_DDL,
    TABLE_DISCOVERY_SESSIONS: DISCOVERY_SESSIONS_COLUMNS_DDL,
    TABLE_DISCOVERY_ANSWERS: DISCOVERY_ANSWERS_COLUMNS_DDL,
    TABLE_GOVERNANCE_PLANS: GOVERNANCE_PLANS_COLUMNS_DDL,
    TABLE_GOVERNANCE_PLAN_ITEMS: GOVERNANCE_PLAN_ITEMS_COLUMNS_DDL,
    TABLE_GOVERNANCE_PLAN_EVENTS: GOVERNANCE_PLAN_EVENTS_COLUMNS_DDL,
}


def create_table_sql(table: str) -> str:
    return f"CREATE TABLE IF NOT EXISTS {table} (\n{_COLUMNS_DDL_BY_TABLE[table]}\n);"


def index_sql(table: str) -> list[str]:
    """Tenant-first indexes for each table's real access paths (CLAUDE.md §20)."""
    if table == TABLE_ORGANIZATION_PROFILES:
        # tenant_id is already UNIQUE (one profile per tenant), which Postgres backs with an
        # index automatically — no separate index needed.
        return []
    if table == TABLE_DISCOVERY_SESSIONS:
        return [
            f"CREATE INDEX IF NOT EXISTS {table}_tenant_idx ON {table} (tenant_id)",
            f"CREATE INDEX IF NOT EXISTS {table}_tenant_status_idx ON {table} (tenant_id, status)",
        ]
    if table == TABLE_DISCOVERY_ANSWERS:
        return [
            f"CREATE INDEX IF NOT EXISTS {table}_tenant_session_idx "
            f"ON {table} (tenant_id, session_id)",
            f"CREATE UNIQUE INDEX IF NOT EXISTS {table}_session_sequence_idx "
            f"ON {table} (session_id, sequence)",
        ]
    if table == TABLE_GOVERNANCE_PLANS:
        return [
            f"CREATE INDEX IF NOT EXISTS {table}_tenant_idx ON {table} (tenant_id)",
            f"CREATE INDEX IF NOT EXISTS {table}_tenant_status_idx ON {table} (tenant_id, status)",
        ]
    if table == TABLE_GOVERNANCE_PLAN_ITEMS:
        return [
            f"CREATE INDEX IF NOT EXISTS {table}_tenant_plan_idx ON {table} (tenant_id, plan_id)",
            f"CREATE INDEX IF NOT EXISTS {table}_tenant_plan_pillar_idx "
            f"ON {table} (tenant_id, plan_id, pillar)",
            f"CREATE INDEX IF NOT EXISTS {table}_tenant_plan_status_idx "
            f"ON {table} (tenant_id, plan_id, status)",
            # Cross-plan lookup: `effective_signals()` (ADR 0066 §5.3) needs every currently-`done`
            # item with a `resolves_signal` for a tenant, regardless of which plan version it
            # belongs to — not scoped by plan_id, so it needs its own index.
            f"CREATE INDEX IF NOT EXISTS {table}_tenant_status_idx ON {table} (tenant_id, status)",
        ]
    if table == TABLE_GOVERNANCE_PLAN_EVENTS:
        return [
            f"CREATE INDEX IF NOT EXISTS {table}_tenant_item_idx "
            f"ON {table} (tenant_id, plan_item_id)",
        ]
    raise ValueError(f"unknown table: {table}")


# ---------------------------------------------------------------------------------------------
# session_applicability_versions — the recorded analyses a plan is built from (ADR 0068). Mirrors
# migrations 0018/0020/0021 for the fixtures that build a schema without running the migration
# runner. Kept faithful INCLUDING the constraints: a fixture that accepts rows production refuses
# would let a test pass on a state the product cannot reach.
# ---------------------------------------------------------------------------------------------
APPLICABILITY_VERSIONS_DDL = """\
CREATE TABLE IF NOT EXISTS session_applicability_versions (
    id                   text        PRIMARY KEY,
    tenant_id            text        NOT NULL,
    session_id           text        NOT NULL,
    version              integer     NOT NULL,
    source               text        NOT NULL,
    assessment_id        text,
    applicability        jsonb       NOT NULL,
    resolved_signals     jsonb       NOT NULL DEFAULT '[]'::jsonb,
    conflicts            jsonb       NOT NULL DEFAULT '[]'::jsonb,
    answer_set_hash      text        NOT NULL,
    engine_pack_versions jsonb       NOT NULL DEFAULT '{}'::jsonb,
    computed_at          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT session_applicability_versions_source_ck
        CHECK (source IN ('core_conclusion', 'sector_conclusion', 'recomputation')),
    CONSTRAINT session_applicability_versions_assessment_ck
        CHECK ((source = 'sector_conclusion') = (assessment_id IS NOT NULL)),
    CONSTRAINT session_applicability_versions_v1_ck
        CHECK ((version = 1) = (source = 'core_conclusion')),
    CONSTRAINT session_applicability_versions_version_ck CHECK (version >= 1)
)"""


def apply_applicability_versions(conn: psycopg.Connection) -> None:
    """The table, its keys, its append-only trigger and its two tenant-safe foreign keys."""
    conn.execute(APPLICABILITY_VERSIONS_DDL)
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS session_applicability_versions_session_version_uq "
        "ON session_applicability_versions (tenant_id, session_id, version)"
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS session_applicability_versions_assessment_uq "
        "ON session_applicability_versions (tenant_id, assessment_id) "
        "WHERE assessment_id IS NOT NULL"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS session_applicability_versions_latest_idx "
        "ON session_applicability_versions (tenant_id, session_id, version DESC)"
    )
    conn.execute(
        """CREATE OR REPLACE FUNCTION applicability_versions_are_append_only() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION
        'applicability version % is immutable (ADR 0068): a recorded decision is never rewritten '
        '— record a new version instead', COALESCE(OLD.id, NEW.id);
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql"""
    )
    conn.execute(
        "DROP TRIGGER IF EXISTS session_applicability_versions_append_only_trg "
        "ON session_applicability_versions"
    )
    conn.execute(
        "CREATE TRIGGER session_applicability_versions_append_only_trg "
        "BEFORE UPDATE OR DELETE ON session_applicability_versions "
        "FOR EACH ROW EXECUTE FUNCTION applicability_versions_are_append_only()"
    )
    conn.execute(
        f"ALTER TABLE {TABLE_GOVERNANCE_PLANS} "
        "ADD COLUMN IF NOT EXISTS source_applicability_id text"
    )
    for statement in (
        f"ALTER TABLE {TABLE_DISCOVERY_SESSIONS} ADD CONSTRAINT discovery_sessions_id_tenant_key "
        "UNIQUE (id, tenant_id)",
        "ALTER TABLE session_applicability_versions "
        "ADD CONSTRAINT applicability_versions_id_tenant_key UNIQUE (id, tenant_id)",
        "ALTER TABLE session_applicability_versions "
        "ADD CONSTRAINT applicability_versions_session_tenant_fk "
        f"FOREIGN KEY (session_id, tenant_id) REFERENCES {TABLE_DISCOVERY_SESSIONS} "
        "(id, tenant_id)",
        f"ALTER TABLE {TABLE_GOVERNANCE_PLANS} "
        "ADD CONSTRAINT governance_plans_applicability_tenant_fk "
        "FOREIGN KEY (source_applicability_id, tenant_id) "
        "REFERENCES session_applicability_versions (id, tenant_id)",
    ):
        conn.execute(
            f"DO $$ BEGIN {statement}; EXCEPTION WHEN duplicate_table THEN NULL; "
            "WHEN duplicate_object THEN NULL; END $$"
        )


def apply_schema(conn: psycopg.Connection) -> None:
    """Create every table and index if absent. Convenient for tests/first-run setup; production
    applies the canonical migrations in `migrations/`. Idempotent (`IF NOT EXISTS`). Tables are
    created in FK-dependency order."""
    for table in (
        TABLE_ORGANIZATION_PROFILES,
        TABLE_DISCOVERY_SESSIONS,
        TABLE_DISCOVERY_ANSWERS,
        TABLE_GOVERNANCE_PLANS,
        TABLE_GOVERNANCE_PLAN_ITEMS,
        TABLE_GOVERNANCE_PLAN_EVENTS,
    ):
        conn.execute(create_table_sql(table))
        for ddl in index_sql(table):
            conn.execute(ddl)
    # `sequence` is already part of `GOVERNANCE_PLAN_EVENTS_COLUMNS_DDL` for a brand-new database,
    # but `CREATE TABLE IF NOT EXISTS` above is a no-op against a table created before that column
    # existed — so an already-running deployment needs this additive, idempotent ALTER to actually
    # gain it (ADR 0066 Phase 3 hardening — deterministic event ordering).
    conn.execute(
        f"ALTER TABLE {TABLE_GOVERNANCE_PLAN_EVENTS} "
        "ADD COLUMN IF NOT EXISTS sequence bigint GENERATED ALWAYS AS IDENTITY"
    )
    # The i18n keys behind a plan item's title and objective, kept ALONGSIDE the rendered text
    # rather than instead of it.
    #
    # `plan.seed.establish_risk_register.title` is an i18n key — that is what it is and why it
    # exists. The draft tool used to resolve it to English at write time and store only the result,
    # which meant the one field that could have been bilingual for free arrived monolingual. A key
    # resolved at write time stops being a key.
    #
    # The text column stays and stays authoritative: a plan drafted before this column existed has
    # an empty key and must keep rendering, and a UI with no translation for a key must be able to
    # fall back to what was actually stored. Empty string, not NULL — "no key" is a fact about the
    # row, not an unknown.
    apply_applicability_versions(conn)
    for column in ("title_key", "objective_key"):
        conn.execute(
            f"ALTER TABLE {TABLE_GOVERNANCE_PLAN_ITEMS} "
            f"ADD COLUMN IF NOT EXISTS {column} text NOT NULL DEFAULT ''"
        )
    conn.commit()
