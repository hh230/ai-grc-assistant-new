"""Sector conclusion and the historical backfill, on a real Postgres (ADR 0068).

Tests 15, 16, 19, 22, 23 and 24 of the ADR's table. What is being defended here is not that the
feature works — that is the easy half — but that everything which existed before it is untouched:
a pack that declares nothing decides nothing, a backfill copies rather than recomputes, and a
translator editing option text is not a governance event.

The database is built from the governance-store migrations, so the constraints and triggers are
the ones a deployment gets rather than a convenient subset.
"""

from __future__ import annotations

import json
import os
import pathlib

import pytest

psycopg = pytest.importorskip("psycopg")

MIGRATIONS = (
    pathlib.Path(__file__).resolve().parents[4] / "packages" / "governance-store" / "migrations"
)
DSN_ENV_VAR = "GOVERNANCE_SCHEMA_TEST_DSN"
DEFAULT_DSN = "postgresql://postgres:postgres@localhost:5432/rasheed_adr68_flow_tests"
TENANT = "t_flow"
_DEFAULT = object()


@pytest.fixture(scope="module")
def dsn():
    return os.environ.get(DSN_ENV_VAR, DEFAULT_DSN)


@pytest.fixture(scope="module")
def conn(dsn):
    base, _, database = dsn.rpartition("/")
    try:
        with psycopg.connect(f"{base}/postgres", autocommit=True, connect_timeout=3) as setup:
            setup.execute(f'DROP DATABASE IF EXISTS "{database}"')
            setup.execute(f'CREATE DATABASE "{database}"')
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"no reachable PostgreSQL ({exc})")
    connection = psycopg.connect(dsn, autocommit=True)
    for migration in sorted(MIGRATIONS.glob("*.sql"), key=lambda p: p.name):
        connection.execute(migration.read_text(encoding="utf-8"))
    yield connection
    connection.close()


@pytest.fixture
def clean(conn):
    conn.execute("SET session_replication_role = replica")
    for table in (
        "sector_answers", "template_selections", "assessments", "governance_plan_items",
        "governance_plans", "session_applicability_versions", "discovery_answers",
        "discovery_sessions", "release_questions", "template_releases", "knowledge_templates",
        "industries",
    ):
        conn.execute(f"DELETE FROM {table}")
    conn.execute("SET session_replication_role = DEFAULT")
    return conn


# --- arrangement ---------------------------------------------------------------------------


def _stored_signals(plain: dict) -> dict:
    """The session row's `signals` shape: a Signal is a value AND its type, not a bare value."""
    def kind(v):
        if isinstance(v, bool):
            return "boolean"
        return "numeric" if isinstance(v, (int, float)) else "enum"

    return {k: {"value_type": kind(v), "value": v, "confidence": 1.0} for k, v in plain.items()}


def _session(
    conn, session_id="sess_1", *, signals=None, applicability=_DEFAULT, status="concluded",
    with_v1=True,
):
    if applicability is _DEFAULT:
        applicability = {"frameworks": [], "maturity": {}, "gaps": [], "plan_items": []}
    conn.execute(
        "INSERT INTO discovery_sessions (id, tenant_id, status, signals, applicability, "
        " pack_versions, confidence_score, created_at, updated_at, concluded_at) "
        "VALUES (%s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, 1, 0, 0, 0)",
        (session_id, TENANT, status,
         json.dumps(_stored_signals(
             signals or {"primary_activity": "technology", "employee_count": 200})),
         None if applicability is None else json.dumps(applicability),
         json.dumps({"pack:core": "1.0"})),
    )
    if with_v1 and applicability is not None and status == "concluded":
        # v1 as the discovery conclusion writes it (ADR 0068 §D5). The fixture seeds it because
        # production does: `sector_conclusion` deliberately does NOT create a missing v1, so a
        # fixture without one would be testing a state the product cannot reach.
        conn.execute(
            "INSERT INTO session_applicability_versions (id, tenant_id, session_id, version, "
            " source, applicability, answer_set_hash) "
            "VALUES (%s, %s, %s, 1, 'core_conclusion', %s::jsonb, 'h') ON CONFLICT DO NOTHING",
            (f"av_v1_{session_id}", TENANT, session_id, json.dumps(applicability)),
        )
    return session_id


def _release(conn, release_id="rel_1", *, questions=()):
    conn.execute("INSERT INTO industries (slug, canonical_name_ar) "
                 "VALUES ('technology', 'تقنية') ON CONFLICT DO NOTHING")
    conn.execute(
        "INSERT INTO knowledge_templates (id, industry_slug) VALUES ('tpl_1','technology') "
        "ON CONFLICT DO NOTHING")
    conn.execute(
        "INSERT INTO template_releases (id, template_id, version, status, expected_outputs, "
        " generated_by_model, prompt_version, generator_commit, created_by) "
        "VALUES (%s, 'tpl_1', 1, 'draft', '[]'::jsonb, 'm', 'p', 'c', 'tester') "
        "ON CONFLICT DO NOTHING",
        (release_id,),
    )
    for question in questions:
        conn.execute(
            "INSERT INTO release_questions (release_id, question_id, canonical_text_ar, type, "
            " options, required, category, importance, \"references\", why_we_ask, "
            " evidence_required, position, writes_signal, signal_value_map) "
            "VALUES (%s, %s, %s, %s, %s::jsonb, true, 'security', 'high', "
            "'[{\"framework\": \"PDPL\", \"clause\": \"art.1\"}]'::jsonb, "
            "'because it matters', '[]'::jsonb, 1, %s, %s::jsonb)",
            (release_id, question["question_id"], question.get("text", "نص"), question["type"],
             json.dumps(question.get("options") or ["a", "b"]),
             question.get("writes_signal"),
             None if question.get("signal_value_map") is None
             else json.dumps(question["signal_value_map"])),
        )
    return release_id


def _assessment(conn, session_id, assessment_id="as_1"):
    conn.execute(
        "INSERT INTO assessments (id, tenant_id, organization_id, source_session_id) "
        "VALUES (%s, %s, 'org_1', %s)", (assessment_id, TENANT, session_id))
    return assessment_id


def _answer(conn, assessment_id, release_id, question_id, value):
    conn.execute(
        "INSERT INTO sector_answers (assessment_id, release_id, question_id, tenant_id, answer) "
        "VALUES (%s, %s, %s, %s, %s::jsonb)",
        (assessment_id, release_id, question_id, TENANT, json.dumps(value)))


def _conclude(conn, assessment_id):
    # The conclusion timestamp comes from the DATABASE's clock, never a literal. An earlier version
    # hardcoded "2026-08-09T00:00:00Z" — in the future when it was written, in the past a few hours
    # later, at which point `assessments_ends_after_it_starts` correctly refused a conclusion that
    # preceded its own start. A test that depends on the wall clock passes until it doesn't.
    now = conn.execute("SELECT now()").fetchone()[0]

    from governance_discovery import DiscoveryEngine
    from governance_discovery.pack import load_bundled_packs
    from governance_store.store import PostgresGovernanceStore
    from grc_api.sector_conclusion import conclude_sector_assessment

    return conclude_sector_assessment(
        connection=conn, knowledge_store=None,
        governance_store=PostgresGovernanceStore(connection=conn),
        engine=DiscoveryEngine(load_bundled_packs()),
        assessment_id=assessment_id, tenant_id=TENANT, now=now,
    )


# --- 19/20: a pack that declares nothing decides nothing ------------------------------------


def test_a_sector_interview_that_declares_no_signal_records_no_version(clean) -> None:
    """Every shipped pack is in this state today, so this is the regression that protects them."""
    session = _session(clean)
    release = _release(clean, questions=[{"question_id": "q1", "type": "enum"}])
    assessment = _assessment(clean, session)
    _answer(clean, assessment, release, "q1", "a")

    result = _conclude(clean, assessment)

    assert result.recomputed is False
    assert result.claims_considered == 0
    # v1 (written by the discovery conclusion) stands alone: no SECOND version was recorded, which
    # is the property — a prose-only interview leaves the decision exactly where discovery left it.
    versions = clean.execute(
        "SELECT version, source FROM session_applicability_versions ORDER BY version"
    ).fetchall()
    assert versions == [(1, "core_conclusion")]
    assert clean.execute(
        "SELECT completed_at IS NOT NULL FROM assessments WHERE id = %s", (assessment,)
    ).fetchone()[0] is True


# --- 1: a declared answer fills a signal the interview never asked ---------------------------


def test_a_declared_answer_fills_an_absent_signal_and_records_a_version(clean) -> None:
    session = _session(clean, signals={"primary_activity": "technology", "employee_count": 200})
    release = _release(clean, questions=[{
        "question_id": "q_geo", "type": "enum", "options": ["ksa", "abroad"],
        "writes_signal": "data_geography",
        "signal_value_map": {"ksa": "ksa_only", "abroad": "international"}}])
    assessment = _assessment(clean, session)
    _answer(clean, assessment, release, "q_geo", "abroad")

    result = _conclude(clean, assessment)

    assert result.recomputed is True
    assert result.version == 2, 'v1 is the core conclusion; a sector version follows it'
    row = clean.execute(
        "SELECT source, resolved_signals FROM session_applicability_versions WHERE id = %s",
        (result.version_id,),
    ).fetchone()
    assert row[0] == "sector_conclusion"
    resolved = {r["signal_key"]: r for r in row[1]}
    assert resolved["data_geography"]["resolved_value"] == "international"
    assert resolved["data_geography"]["origin"] == "sector_answer"


# --- 13: an option declared null never becomes False -----------------------------------------


def test_an_option_declared_null_leaves_the_signal_alone(clean) -> None:
    session = _session(clean)
    release = _release(clean, questions=[{
        "question_id": "q_geo", "type": "enum", "options": ["ksa", "unknown"],
        "writes_signal": "data_geography",
        "signal_value_map": {"ksa": "ksa_only", "unknown": None}}])
    assessment = _assessment(clean, session)
    _answer(clean, assessment, release, "q_geo", "unknown")

    result = _conclude(clean, assessment)

    assert result.claims_considered == 0, "'we don't know' is not an answer to merge"
    assert result.recomputed is False


# --- 15: conclusion is one-way ---------------------------------------------------------------


def test_a_concluded_assessment_is_not_concluded_again(clean) -> None:
    from grc_api.sector_conclusion import AlreadyConcluded

    session = _session(clean)
    _release(clean, questions=[{"question_id": "q1", "type": "enum"}])
    assessment = _assessment(clean, session)
    _conclude(clean, assessment)

    with pytest.raises(AlreadyConcluded):
        _conclude(clean, assessment)


# --- 24: text has no authority ----------------------------------------------------------------


def test_rewording_and_translating_an_option_changes_neither_the_value_nor_the_decision(
    clean,
) -> None:
    """The map is keyed by option_id precisely so that this is true. If it were keyed by text, a
    translator would be a governance actor."""
    outcomes = []
    for _run, text in enumerate(("داخل المملكة حصراً", "Data stays in the Kingdom", "")):
        clean.execute("SET session_replication_role = replica")
        for table in ("sector_answers", "assessments", "release_questions", "template_releases",
                      "session_applicability_versions", "discovery_sessions"):
            clean.execute(f"DELETE FROM {table}")
        clean.execute("SET session_replication_role = DEFAULT")

        # Same ids everywhere, so the ONLY thing that differs between runs is the wording. (An
        # earlier version varied the release id too, and the provenance record faithfully reported
        # the difference — correct behaviour, useless test.)
        session = _session(clean, "sess_same")
        release = _release(clean, "rel_same", questions=[{
            "question_id": "q_geo", "type": "enum", "text": text, "options": ["ksa", "abroad"],
            "writes_signal": "data_geography",
            "signal_value_map": {"ksa": "ksa_only", "abroad": "international"}}])
        assessment = _assessment(clean, session, "as_same")
        _answer(clean, assessment, release, "q_geo", "abroad")

        result = _conclude(clean, assessment)
        row = clean.execute(
            "SELECT applicability, resolved_signals FROM session_applicability_versions "
            "WHERE id = %s", (result.version_id,)).fetchone()
        outcomes.append((json.dumps(row[0], sort_keys=True),
                         json.dumps(row[1], sort_keys=True)))

    assert len(set(outcomes)) == 1, "the decision moved when only the wording changed"


# --- 22 & 23: the historical backfill ----------------------------------------------------------


def test_the_backfill_copies_the_stored_decision_and_changes_nothing(clean) -> None:
    from grc_api.backfill_applicability import backfill

    stored = {"frameworks": [{"framework_id": "framework:iso_27001"}], "maturity": {"a": 1},
              "plan_items": [{"id": "seed:x"}]}
    _session(clean, "sess_old", applicability=stored, with_v1=False)
    clean.execute(
        "INSERT INTO governance_plans (id, tenant_id, version, status, source_session_id, "
        " source_mission_id, inferred_frameworks, maturity_baseline, top_risks, "
        " executive_summary, created_at, updated_at) "
        "VALUES ('plan_old', %s, 1, 'active', 'sess_old', 'mis_1', '[]'::jsonb, '{}'::jsonb, "
        "'[]'::jsonb, '', 0, 0)", (TENANT,))

    report = backfill(clean)

    assert report.sessions_eligible == 1 and report.versions_written == 1
    row = clean.execute(
        "SELECT applicability, source, version FROM session_applicability_versions"
    ).fetchone()
    assert row[0] == stored, "the stored decision must arrive byte-for-byte"
    assert (row[1], row[2]) == ("core_conclusion", 1)
    assert clean.execute(
        "SELECT source_applicability_id IS NOT NULL FROM governance_plans WHERE id = 'plan_old'"
    ).fetchone()[0] is True
    assert report.plans_linked == 1


def test_the_backfill_never_runs_the_engine(clean, monkeypatch) -> None:
    """Proved by making the engine impossible to call: if the backfill needed it, it would raise
    rather than quietly re-decide a year-old plan with today's rules."""
    import governance_discovery.analysis as analysis
    import governance_discovery.derivation as derivation
    from grc_api.backfill_applicability import backfill

    def refuse(*args, **kwargs):  # pragma: no cover - the point is that it never runs
        raise AssertionError("the backfill recomputed a decision instead of copying it")

    monkeypatch.setattr(analysis, "analyze", refuse)
    monkeypatch.setattr(derivation, "apply_derivations", refuse)

    _session(clean, "sess_a", applicability={"frameworks": [], "maturity": {}}, with_v1=False)
    _session(clean, "sess_b", applicability={"frameworks": [], "maturity": {}}, with_v1=False)
    report = backfill(clean)
    assert report.versions_written == 2


def test_a_session_with_no_stored_applicability_gets_no_invented_version(clean) -> None:
    """"Not recorded" is a fact about the past. Filling it in would be a lie with a timestamp."""
    from grc_api.backfill_applicability import backfill

    _session(clean, "sess_blank", applicability=None, with_v1=False)
    report = backfill(clean)

    assert report.sessions_without_applicability == 1
    assert report.versions_written == 0
    assert clean.execute("SELECT count(*) FROM session_applicability_versions").fetchone()[0] == 0


def test_running_the_backfill_twice_writes_nothing_the_second_time(clean) -> None:
    from grc_api.backfill_applicability import backfill

    _session(clean, "sess_twice", applicability={"frameworks": [], "maturity": {}}, with_v1=False)
    first = backfill(clean)
    second = backfill(clean)

    assert first.versions_written == 1
    assert second.versions_written == 0 and second.versions_already_present == 1
    assert clean.execute("SELECT count(*) FROM session_applicability_versions").fetchone()[0] == 1


# --- the backfill creates nothing orphaned (ADR 0068, integrity) --------------------------------


def test_the_backfill_leaves_no_orphan_version_and_no_dangling_plan(clean) -> None:
    """Lives here rather than beside the other integrity tests because it needs `grc_api`, which
    the governance-store package cannot import."""
    from grc_api.backfill_applicability import backfill

    for index in range(3):
        _session(clean, f"sess_bf_{index}", applicability={"frameworks": [], "maturity": {}},
                 with_v1=False)
    clean.execute(
        "INSERT INTO governance_plans (id, tenant_id, version, status, source_session_id, "
        " source_mission_id, inferred_frameworks, maturity_baseline, top_risks, "
        " executive_summary, created_at, updated_at) "
        "VALUES ('plan_bf', %s, 1, 'active', 'sess_bf_0', 'mis_1', '[]'::jsonb, '{}'::jsonb, "
        "'[]'::jsonb, '', 0, 0)", (TENANT,))

    report = backfill(clean)
    assert report.versions_written == 3

    orphans = clean.execute(
        "SELECT count(*) FROM session_applicability_versions v WHERE NOT EXISTS "
        "(SELECT 1 FROM discovery_sessions s WHERE s.id = v.session_id "
        " AND s.tenant_id = v.tenant_id)").fetchone()[0]
    dangling = clean.execute(
        "SELECT count(*) FROM governance_plans p WHERE p.source_applicability_id IS NOT NULL "
        "AND NOT EXISTS (SELECT 1 FROM session_applicability_versions v "
        "                WHERE v.id = p.source_applicability_id AND v.tenant_id = p.tenant_id)"
    ).fetchone()[0]
    assert (orphans, dangling) == (0, 0)

    # And the plan it linked points at ITS OWN session's version, not any other.
    linked = clean.execute(
        "SELECT v.session_id FROM governance_plans p JOIN session_applicability_versions v "
        "  ON v.id = p.source_applicability_id WHERE p.id = 'plan_bf'").fetchone()
    assert linked[0] == "sess_bf_0"
