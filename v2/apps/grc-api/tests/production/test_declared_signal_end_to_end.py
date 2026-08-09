"""The pilot, proved on the thing that matters: does a declared sector answer change a DECISION?

`technology / it_policies` is the one question of 142 whose five options correspond, one to one, to
an engine signal's vocabulary — `policy_state`'s maturity ladder. Nothing about it was rewritten
for this: the wording, the order and the meanings are as a reviewer approved them, and all that was
added is a stable id per option and the map from those ids to values the engine already knows.

Each test drives the real path — release with a declaration, assessment, answer, sector conclusion,
applicability version — and asserts what came out the far end, never an intermediate call.

The property under all of them: a decision moves ONLY when a declared signal reaches a rule that
already existed. `signal_value_map` cannot invent a rule, a value, or an outcome; the last test
here says so by trying.
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
DEFAULT_DSN = "postgresql://postgres:postgres@localhost:5432/rasheed_adr68_pilot_tests"
TENANT = "t_pilot"

# The declaration exactly as `technology.ar.json` now carries it.
IT_POLICIES_MAP = {
    "reviewed": "reviewed_periodically",
    "approved_not_reviewed": "approved",
    "draft_unapproved": "documented_unapproved",
    "verbal_only": "verbal",
    "none": "absent",
}


@pytest.fixture(scope="module")
def conn():
    dsn = os.environ.get(DSN_ENV_VAR, DEFAULT_DSN)
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
    for table in ("sector_answers", "template_selections", "assessments",
                  "session_applicability_versions", "discovery_answers", "discovery_sessions",
                  "release_questions", "template_releases", "knowledge_templates", "industries"):
        conn.execute(f"DELETE FROM {table}")
    conn.execute("SET session_replication_role = DEFAULT")
    return conn


# --- arrangement: a release that carries the real declaration -----------------------------------


def _release(conn, *, declare=True, release_id="rel_pilot"):
    conn.execute("INSERT INTO industries (slug, canonical_name_ar) VALUES ('technology','تقنية') "
                 "ON CONFLICT DO NOTHING")
    conn.execute("INSERT INTO knowledge_templates (id, industry_slug) VALUES ('tpl','technology') "
                 "ON CONFLICT DO NOTHING")
    conn.execute(
        "INSERT INTO template_releases (id, template_id, version, status, expected_outputs, "
        " generated_by_model, prompt_version, generator_commit, created_by) VALUES "
        "(%s, 'tpl', %s, 'draft', '[]'::jsonb, 'authored', 'authored:technology', 'c', 'tester')",
        (release_id, abs(hash(release_id)) % 1000 + 1),
    )
    conn.execute(
        'INSERT INTO release_questions (release_id, question_id, canonical_text_ar, type, options, '
        ' required, category, importance, "references", why_we_ask, evidence_required, position, '
        ' writes_signal, signal_value_map) VALUES (%s, %s, %s, %s, %s::jsonb, true, %s, %s, '
        "%s::jsonb, %s, '[]'::jsonb, 1, %s, %s::jsonb)",
        (release_id, "it_policies", "هل توجد سياسات مؤسسية معتمدة ومطبقة؟", "enum",
         json.dumps([{"option_id": k, "text_ar": f"option {k}"} for k in IT_POLICIES_MAP]),
         "records", "high",
         json.dumps([{"framework": "ISO 27001", "clause": "5.2"}]),
         "Approved policies are the documentary basis of any governance programme.",
         "policy_state" if declare else None,
         json.dumps(IT_POLICIES_MAP) if declare else None),
    )
    return release_id


def _stored(signals: dict) -> str:
    def kind(v):
        if isinstance(v, bool):
            return "boolean"
        return "numeric" if isinstance(v, (int, float)) else "enum"
    return json.dumps({k: {"value_type": kind(v), "value": v, "confidence": 1.0}
                       for k, v in signals.items()})


def _session(conn, session_id, core_signals):
    """A concluded session and its v1, as the discovery conclusion writes them."""
    from governance_discovery import DiscoveryEngine
    from governance_discovery.analysis import analyze
    from governance_discovery.pack import load_bundled_packs
    from governance_discovery.signal import Signal, SignalSet, ValueType
    from governance_store.codec import applicability_to_dict

    signals = SignalSet()
    for key, value in core_signals.items():
        vt = (ValueType.BOOLEAN if isinstance(value, bool)
              else ValueType.NUMERIC if isinstance(value, (int, float)) else ValueType.ENUM)
        signals = signals.with_signal(Signal(key=key, value_type=vt, value=value))
    applicability = analyze(signals, DiscoveryEngine(load_bundled_packs()))

    conn.execute(
        "INSERT INTO discovery_sessions (id, tenant_id, status, signals, applicability, "
        " pack_versions, confidence_score, created_at, updated_at, concluded_at) "
        "VALUES (%s, %s, 'concluded', %s::jsonb, %s::jsonb, %s::jsonb, 1, 0, 0, 0)",
        (session_id, TENANT, _stored(core_signals),
         json.dumps(applicability_to_dict(applicability)), json.dumps({"pack:core": "1.0"})),
    )
    conn.execute(
        "INSERT INTO session_applicability_versions (id, tenant_id, session_id, version, "
        " source, applicability, answer_set_hash) "
        "VALUES (%s, %s, %s, 1, 'core_conclusion', %s::jsonb, 'h')",
        (f"av_v1_{session_id}", TENANT, session_id,
         json.dumps(applicability_to_dict(applicability))),
    )
    return session_id, applicability


def _answer_and_conclude(conn, session_id, release_id, option_id, assessment_id="as_pilot"):
    from governance_discovery import DiscoveryEngine
    from governance_discovery.pack import load_bundled_packs
    from governance_store.store import PostgresGovernanceStore
    from grc_api.sector_conclusion import conclude_sector_assessment

    conn.execute("INSERT INTO assessments (id, tenant_id, organization_id, source_session_id) "
                 "VALUES (%s, %s, 'org', %s)", (assessment_id, TENANT, session_id))
    if option_id is not None:
        conn.execute(
            "INSERT INTO sector_answers (assessment_id, release_id, question_id, tenant_id, "
            " answer) "
            "VALUES (%s, %s, 'it_policies', %s, %s::jsonb)",
            (assessment_id, release_id, TENANT, json.dumps(option_id)))
    return conclude_sector_assessment(
        connection=conn, knowledge_store=None,
        governance_store=PostgresGovernanceStore(connection=conn),
        engine=DiscoveryEngine(load_bundled_packs()),
        assessment_id=assessment_id, tenant_id=TENANT,
        now=conn.execute("SELECT now()").fetchone()[0],
    )


def _versions(conn, session_id):
    return conn.execute(
        "SELECT version, source, applicability, resolved_signals FROM "
        "session_applicability_versions WHERE session_id=%s ORDER BY version", (session_id,)
    ).fetchall()


# --- ABSENT: the case the whole feature exists for ------------------------------------------------


def test_ABSENT_the_declared_answer_fills_a_signal_the_interview_never_asked(clean) -> None:
    """The core interview never asked about policies. The sector answer does, it is declared, and a
    rule that already existed acts on it."""
    release = _release(clean)
    session, _ = _session(clean, "sess_absent",
                          {"primary_activity": "technology", "employee_count": 40})

    result = _answer_and_conclude(clean, session, release, "none")   # -> policy_state = absent

    assert result.recomputed is True
    versions = _versions(clean, session)
    assert [(v[0], v[1]) for v in versions] == [(1, "core_conclusion"), (2, "sector_conclusion")]

    resolved = {r["signal_key"]: r for r in versions[1][3]}
    assert resolved["policy_state"]["resolved_value"] == "absent"
    assert resolved["policy_state"]["origin"] == "sector_answer"
    assert resolved["policy_state"]["outcome"] == "absent_filled"

    # And the DECISION moved, through `r:policy_weak_seeds_drafting` — a rule written long before
    # this pilot and untouched by it. The shape of the move is the point: knowing nothing about
    # policies, the engine could only recommend its fallback ("confirm the basics with an
    # advisor"); told they are absent, it recommends the actual work.
    v1_seeds = {i["id"] for i in versions[0][2]["plan_items"]}
    v2_seeds = {i["id"] for i in versions[1][2]["plan_items"]}
    assert v1_seeds == {"seed:confirm_basics_with_advisor"}
    assert v2_seeds == {"seed:draft_foundational_policies"}
    assert v1_seeds != v2_seeds, "a declared answer must reach the plan, not just the audit record"


# --- AGREE / DISAGREE ----------------------------------------------------------------------------


def test_AGREE_the_same_value_changes_nothing_and_the_core_stays_the_source(clean) -> None:
    release = _release(clean)
    session, _ = _session(clean, "sess_agree",
                          {"primary_activity": "technology", "employee_count": 40,
                           "policy_state": "approved"})

    _answer_and_conclude(clean, session, release, "approved_not_reviewed")   # same value

    versions = _versions(clean, session)
    assert versions[0][2] == versions[1][2], "agreement must not move a single decision"
    resolved = {r["signal_key"]: r for r in versions[1][3]}
    assert resolved["policy_state"]["outcome"] == "corroborated"
    assert resolved["policy_state"]["origin"] == "core_answer", "agreement must not re-author it"
    assert versions[1][2] is not None


def test_DISAGREE_the_core_value_stands_and_the_conflict_is_recorded(clean) -> None:
    release = _release(clean)
    session, _ = _session(clean, "sess_disagree",
                          {"primary_activity": "technology", "employee_count": 40,
                           "policy_state": "approved"})

    _answer_and_conclude(clean, session, release, "none")   # sector says absent, core says approved

    versions = _versions(clean, session)
    assert versions[0][2] == versions[1][2], "the plan must be what it would have been without this"
    resolved = {r["signal_key"]: r for r in versions[1][3]}
    assert resolved["policy_state"]["resolved_value"] == "approved"
    assert resolved["policy_state"]["outcome"] == "conflict_core_stands"
    conflicts = clean.execute(
        "SELECT conflicts FROM session_applicability_versions WHERE session_id=%s AND version=2",
        (session,)).fetchone()[0]
    assert [c["signal_key"] for c in conflicts] == ["policy_state"]


# --- the boundaries -------------------------------------------------------------------------------


def test_an_option_outside_the_declared_map_contributes_nothing(clean) -> None:
    """An answer whose option_id the map does not name. Not an error, not a False — nothing."""
    release = _release(clean)
    session, _ = _session(clean, "sess_unknown_opt",
                          {"primary_activity": "technology", "employee_count": 40})

    result = _answer_and_conclude(clean, session, release, "an_option_that_was_never_declared")

    assert result.claims_considered == 0
    assert [v[0] for v in _versions(clean, session)] == [1], "no v2 — nothing was claimed"


def test_the_same_question_WITHOUT_a_declaration_changes_nothing(clean) -> None:
    """The control. Same question, same answer, declaration removed — and the decision does not
    move. This is what makes the ABSENT case above attributable to the declaration."""
    release = _release(clean, declare=False, release_id="rel_undeclared")
    session, _ = _session(clean, "sess_undeclared",
                          {"primary_activity": "technology", "employee_count": 40})

    result = _answer_and_conclude(clean, session, release, "none")

    assert result.recomputed is False
    assert [v[0] for v in _versions(clean, session)] == [1]


def test_a_map_cannot_invent_a_value_a_rule_a_decision(clean) -> None:
    """`signal_value_map` binds an option to a value the ENGINE already defines. It cannot mint a
    sixth ladder state, and the validator refuses the attempt before anything is stored — so no
    rule can ever be reached by a value no rule was written for."""
    from grc_api.signal_declarations import validate_declaration

    invented = {
        "question_id": "it_policies", "type": "enum", "writes_signal": "policy_state",
        "options": [{"option_id": k} for k in IT_POLICIES_MAP],
        "signal_value_map": dict(IT_POLICIES_MAP, none="excellent"),
    }
    errors = validate_declaration(invented)
    assert errors and "not one of" in errors[0].message

    # And the engine's vocabulary is the source of that refusal, not a list kept beside it.
    from governance_discovery.pack import load_bundled_packs
    from governance_discovery.signal import DEFAULT_MATURITY_SCALE
    core = next(q for p in load_bundled_packs().values() for q in p.questions
                if q.writes_signal == "policy_state")
    assert set(IT_POLICIES_MAP.values()) == set(core.options or DEFAULT_MATURITY_SCALE)
