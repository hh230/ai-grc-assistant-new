"""The import path carrying a signal declaration, end to end, against a real Postgres (ADR 0068
Phase 2, step 2 — before any release is created).

Phase 1 built the channel and left it empty; the repository's INSERT did not carry the two
columns, which made "no model can declare a signal" structurally true and "no human can either"
equally true. This is the step that opens it for humans only.

The pilot subject is `technology / it_policies` — the ONE question of 142 whose five options
correspond, one to one, to an engine signal's vocabulary (`policy_state`'s maturity ladder). It is
used here as authored: no wording changes, no new question, no new signal, no new rule.
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
DEFAULT_DSN = "postgresql://postgres:postgres@localhost:5432/rasheed_adr68_import_tests"

# The declaration under test: it_policies' five options, in the order the pack authored them,
# against policy_state's ladder. Written out rather than computed, so a reviewer reads the mapping
# instead of trusting a zip().
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
    for table in ("release_questions", "template_releases", "knowledge_templates", "industries"):
        conn.execute(f"DELETE FROM {table}")
    conn.execute("SET session_replication_role = DEFAULT")
    return conn


def _store(conn):
    from governance_store.knowledge_store import PostgresKnowledgeStore

    return PostgresKnowledgeStore(connection=conn)


def _question(**overrides):
    """A minimally valid authored question; overrides carry the declaration under test."""
    question = {
        "question_id": "it_policies",
        "canonical_text_ar": "هل توجد سياسات مؤسسية معتمدة ومطبقة؟",
        "type": "enum",
        "options": [
            {"option_id": "reviewed", "text_ar": "سياسات معتمدة ومطبقة ومراجعة دورياً"},
            {"option_id": "approved_not_reviewed", "text_ar": "سياسات معتمدة لكن دون مراجعة دورية"},
            {"option_id": "draft_unapproved", "text_ar": "مسودات غير معتمدة"},
            {"option_id": "verbal_only", "text_ar": "ممارسات شفهية غير موثقة"},
            {"option_id": "none", "text_ar": "لا توجد سياسات"},
        ],
        "required": True,
        "category": "records",
        "importance": "high",
        "references": [{"framework": "ISO 27001", "clause": "5.2"}],
        "why_we_ask": "Approved policies are the documentary basis of any governance programme.",
        "evidence_required": ["Signed policy set"],
    }
    question.update(overrides)
    return question


def _template(conn, slug="technology"):
    conn.execute("INSERT INTO industries (slug, canonical_name_ar) VALUES (%s, 'تقنية') "
                 "ON CONFLICT DO NOTHING", (slug,))
    conn.execute("INSERT INTO knowledge_templates (id, industry_slug) VALUES ('tpl_it', %s) "
                 "ON CONFLICT DO NOTHING", (slug,))
    return "tpl_it"


def _create(conn, questions):
    return _store(conn).create_release(
        release_id=(
            f"rel_{len(questions)}_"
            f"{abs(hash(json.dumps(questions, sort_keys=True))) % 10**8}"
        ),
        template_id=_template(conn),
        questions=questions,
        expected_outputs=[],
        generated_by_model="authored",
        prompt_version="authored:technology",
        generator_commit="test",
        created_by="tester",
    )


# --- a valid declaration survives the whole way to the row ---------------------------------------


def test_a_valid_declaration_is_stored_whole(clean) -> None:
    _create(clean, [_question(writes_signal="policy_state", signal_value_map=IT_POLICIES_MAP)])

    row = clean.execute(
        "SELECT writes_signal, signal_value_map FROM release_questions "
        "WHERE question_id='it_policies'"
    ).fetchone()
    assert row[0] == "policy_state"
    assert row[1] == IT_POLICIES_MAP, "the map must arrive byte-for-byte, not re-derived"


def test_a_question_without_a_declaration_stores_two_nulls(clean) -> None:
    """Every shipped pack is in this state, and must stay writable exactly as before."""
    _create(clean, [_question()])

    row = clean.execute(
        "SELECT writes_signal, signal_value_map FROM release_questions "
        "WHERE question_id='it_policies'"
    ).fetchone()
    assert row == (None, None)


def test_the_declaration_round_trips_through_the_read_path(clean) -> None:
    """What the resolver will later consult is what was written — read back through the store's
    own list, not through a hand-written query."""
    _create(clean, [_question(writes_signal="policy_state", signal_value_map=IT_POLICIES_MAP)])

    releases = _store(clean).list_releases(with_questions=True)
    question = releases[0]["questions"][0]
    assert question["writes_signal"] == "policy_state"
    assert question["signal_value_map"] == IT_POLICIES_MAP


# --- an invalid declaration never reaches the database -------------------------------------------


@pytest.mark.parametrize(
    "bad,because",
    [
        ({"writes_signal": "subject_to_nca", "signal_value_map": {"none": True}}, "derived signal"),
        ({"writes_signal": "held_licenses", "signal_value_map": {"none": "none"}}, "orphan signal"),
        ({"writes_signal": "invented", "signal_value_map": {"none": "x"}}, "unknown signal"),
        ({"writes_signal": "policy_state", "signal_value_map": {"none": "absent"}},
         "incomplete map"),
        ({"writes_signal": "policy_state", "signal_value_map": dict(IT_POLICIES_MAP, none="mars")},
         "value outside the vocabulary"),
        ({"signal_value_map": IT_POLICIES_MAP}, "a map with no declaration"),
    ],
)
def test_an_invalid_declaration_is_refused_at_the_file_boundary(bad, because, tmp_path) -> None:
    """Refused as a FILE, before any write — which is why `load_pack` is the gate and the
    repository is not. The repository carries the columns and interprets neither."""
    from grc_api.knowledge_seed import AuthoredPackRejected, _validate_declarations

    with pytest.raises(AuthoredPackRejected) as raised:
        _validate_declarations([_question(**bad)], "technology.ar.json")
    assert "signal declaration" in str(raised.value), because


def test_nothing_reaches_the_database_when_the_file_is_rejected(clean) -> None:
    from grc_api.knowledge_seed import AuthoredPackRejected, _validate_declarations

    questions = [_question(writes_signal="subject_to_nca", signal_value_map={"none": True})]
    with pytest.raises(AuthoredPackRejected):
        _validate_declarations(questions, "technology.ar.json")
    assert clean.execute("SELECT count(*) FROM release_questions").fetchone()[0] == 0


# --- text has no authority on this path ----------------------------------------------------------


def test_rewording_every_option_changes_nothing_that_was_stored(clean) -> None:
    """The map is keyed by option_id. Two releases whose option TEXT differs entirely, with the
    same ids and the same map, store the same declaration."""
    original = _question(writes_signal="policy_state", signal_value_map=IT_POLICIES_MAP)
    reworded = _question(
        writes_signal="policy_state",
        signal_value_map=IT_POLICIES_MAP,
        options=[
            {"option_id": o["option_id"], "text_ar": f"REWORDED {i}"}
            for i, o in enumerate(original["options"])
        ],
    )
    _create(clean, [original])
    _create(clean, [reworded])

    stored = clean.execute(
        "SELECT signal_value_map FROM release_questions WHERE question_id='it_policies'"
    ).fetchall()
    assert len(stored) == 2
    assert stored[0][0] == stored[1][0], "the wording moved; the declaration did not"


# --- the released packs are untouched ------------------------------------------------------------


def test_shipped_declarations_are_exactly_the_four_we_decided() -> None:
    """FOUR questions declare a signal, and this is what pins which four.

    The guard has been rewritten twice, and each rewrite was a decision rather than a maintenance
    chore. It first asserted that nothing declared anything — true while the channel was empty. The
    pilot ended that for `technology / it_policies`, and the second wave adds three more: one per
    pack, each reviewed against the rules that read its signal before it was written down.

    So the assertion stays an exact map, never a count. A count catches a question that gained a
    declaration by accident but not one that lost the declaration it was supposed to keep, and both
    are ways a decision quietly changes. Editing this map is how a fifth declaration gets decided.
    """
    from grc_api.knowledge_seed import available_packs, load_pack

    declared = {
        slug: [q["question_id"] for q in load_pack(slug)["questions"] if q.get("writes_signal")]
        for slug in available_packs()
    }
    assert declared == {
        "technology": ["it_policies"],
        "financial_services": ["fs_compliance_monitoring"],
        "legal_services": ["lg_risk_register"],
        "marketing_advertising": ["mk_policy_documentation"],
        # Listed with an empty list rather than omitted: a new sector pack has to be named here
        # before the suite goes green, so authoring one is never how a declaration slips in.
        "construction": [], "consulting": [], "education": [], "healthcare": [],
        "manufacturing": [], "real_estate": [], "retail": [],
    }, declared
