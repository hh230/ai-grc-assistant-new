"""Versioned applicability against a real Postgres (ADR 0068) — tests 15-18 of the ADR's table.

The property under test is the uncomfortable one: **a decision, once recorded, survives everything
we do afterwards.** Not a newer knowledge pack, not a code deploy, not a restart, not a second
conclusion. Each of those is a real thing that happens to a running product, and each of them would
silently re-decide an old customer's plan if the read path recomputed instead of reading.

Skips cleanly when no database is reachable, like the other integration suites.
"""

from __future__ import annotations

import json
import os
import pathlib
import uuid

import pytest

psycopg = pytest.importorskip("psycopg")

MIGRATIONS = pathlib.Path(__file__).resolve().parents[1] / "migrations"
DSN_ENV_VAR = "GOVERNANCE_SCHEMA_TEST_DSN"
DEFAULT_DSN = "postgresql://postgres:postgres@localhost:5432/rasheed_adr68_tests"


def _admin_dsn(dsn: str) -> tuple[str, str]:
    base, _, database = dsn.rpartition("/")
    return f"{base}/postgres", database


@pytest.fixture(scope="module")
def dsn():
    return os.environ.get(DSN_ENV_VAR, DEFAULT_DSN)


@pytest.fixture(scope="module")
def conn(dsn):
    """A database built from the migrations themselves — including 0018, so the trigger and the
    constraints under test are the ones a deployment gets."""
    admin, database = _admin_dsn(dsn)
    try:
        with psycopg.connect(admin, autocommit=True, connect_timeout=3) as setup:
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
    conn.execute("DELETE FROM governance_plan_items")
    conn.execute("DELETE FROM governance_plans")
    conn.execute("ALTER TABLE session_applicability_versions DISABLE TRIGGER "
                 "session_applicability_versions_append_only_trg")
    conn.execute("DELETE FROM session_applicability_versions")
    conn.execute("ALTER TABLE session_applicability_versions ENABLE TRIGGER "
                 "session_applicability_versions_append_only_trg")
    conn.execute("DELETE FROM discovery_sessions")
    return conn


def _session(conn, session_id: str, tenant_id: str = "t") -> str:
    """A version now REQUIRES its session to exist (0021). The fixture creates one rather than
    fabricating an id — the foreign key is the point, so working around it here would hide it."""
    conn.execute(
        "INSERT INTO discovery_sessions (id, tenant_id, status, signals, confidence_score, "
        " created_at, updated_at) VALUES (%s, %s, 'concluded', '{}'::jsonb, 1, 0, 0) "
        "ON CONFLICT (id) DO NOTHING",
        (session_id, tenant_id),
    )
    return session_id


def _version(conn, **overrides):
    fields = {
        "id": f"av_{uuid.uuid4().hex[:12]}",
        "tenant_id": "t",
        "session_id": "sess_1",
        "version": 1,
        "source": "core_conclusion",
        "assessment_id": None,
        "applicability": json.dumps({"frameworks": [], "maturity": {}}),
        "answer_set_hash": "h",
    }
    fields.update(overrides)
    _session(conn, fields["session_id"], fields["tenant_id"])
    conn.execute(
        "INSERT INTO session_applicability_versions "
        "(id, tenant_id, session_id, version, source, assessment_id, applicability, "
        " answer_set_hash) VALUES (%(id)s, %(tenant_id)s, %(session_id)s, %(version)s, "
        "%(source)s, %(assessment_id)s, %(applicability)s::jsonb, %(answer_set_hash)s)",
        fields,
    )
    return fields["id"]


# --- 17: the past is not rewritable -------------------------------------------------------------


def test_a_recorded_version_can_never_be_updated(clean) -> None:
    version_id = _version(clean)
    with pytest.raises(psycopg.errors.RaiseException, match="immutable"):
        clean.execute(
            "UPDATE session_applicability_versions SET applicability = '{}'::jsonb WHERE id = %s",
            (version_id,),
        )


def test_a_recorded_version_can_never_be_deleted(clean) -> None:
    version_id = _version(clean)
    with pytest.raises(psycopg.errors.RaiseException, match="immutable"):
        clean.execute("DELETE FROM session_applicability_versions WHERE id = %s", (version_id,))


# --- 15: a second conclusion cannot produce a second version ------------------------------------


def test_one_assessment_can_only_ever_have_one_version(clean) -> None:
    """The structural guard behind "conclusion is one-way". `assessments_conclude_once` already
    refuses a re-conclusion; this refuses its RESULT, so a future caller that finds a way around
    the first guard still cannot record a second decision."""
    _version(clean, version=2, source="sector_conclusion", assessment_id="as_1")
    with pytest.raises(psycopg.errors.UniqueViolation):
        _version(clean, version=3, source="sector_conclusion", assessment_id="as_1")


def test_two_versions_cannot_share_a_number_within_a_session(clean) -> None:
    _version(clean)
    with pytest.raises(psycopg.errors.UniqueViolation):
        _version(clean)


# --- the shape invariants, stated in the schema rather than in prose -----------------------------


def test_version_one_is_always_the_core_conclusion(clean) -> None:
    with pytest.raises(psycopg.errors.CheckViolation):
        _version(clean, version=1, source="sector_conclusion", assessment_id="as_x")
    with pytest.raises(psycopg.errors.CheckViolation):
        _version(clean, version=2, source="core_conclusion")


def test_a_sector_version_must_name_its_assessment(clean) -> None:
    with pytest.raises(psycopg.errors.CheckViolation):
        _version(clean, version=2, source="sector_conclusion", assessment_id=None)


def test_a_core_version_must_not_claim_an_assessment(clean) -> None:
    with pytest.raises(psycopg.errors.CheckViolation):
        _version(clean, version=1, source="core_conclusion", assessment_id="as_x")


def test_an_unknown_source_is_refused(clean) -> None:
    with pytest.raises(psycopg.errors.CheckViolation):
        _version(clean, source="whatever_the_caller_felt_like")


# --- 18: neither a new pack, nor new code, nor a restart may move a recorded decision -------------


def test_the_stored_decision_survives_a_pack_bump_a_code_change_and_a_restart(clean, dsn) -> None:
    """The read path must READ. If it recomputed, every one of these would silently re-decide an
    old plan — and nothing in the product would report that it had happened.

    A restart is simulated the only way it can be in-process and still mean something: the store
    object and its connection are thrown away and rebuilt from the DSN, so no cached engine, pack
    or connection survives between the write and the read.
    """
    from governance_discovery import DiscoveryEngine
    from governance_discovery.analysis import analyze
    from governance_discovery.pack import load_bundled_packs
    from governance_discovery.signal import Signal, SignalSet, ValueType
    from governance_store.codec import applicability_to_dict
    from governance_store.store import PostgresGovernanceStore

    signals = SignalSet().with_signal(
        Signal(key="primary_activity", value_type=ValueType.ENUM, value="technology")
    ).with_signal(
        Signal(key="employee_count", value_type=ValueType.NUMERIC, value=200)
    )
    engine_before = DiscoveryEngine(load_bundled_packs())
    recorded = applicability_to_dict(analyze(signals, engine_before))

    _session(clean, "sess_frozen")
    store = PostgresGovernanceStore(connection=clean)
    version_id = f"av_{uuid.uuid4().hex[:12]}"
    store.record_applicability_version(
        version_id=version_id, tenant_id="t", session_id="sess_frozen", version=1,
        source="core_conclusion", applicability=recorded, resolved_signals=[], conflicts=[],
        answer_set_hash="h", engine_pack_versions={"pack:core": "1.0"},
    )

    # (a) a knowledge pack changes — a new rule that WOULD add a plan item, and a bumped version
    packs = load_bundled_packs()
    core = packs["pack:core"]
    mutated_rules = core.rules + (_extra_rule(),)
    packs["pack:core"] = _replace_pack(core, rules=mutated_rules, version="99.0")
    engine_after = DiscoveryEngine(packs)
    would_be = applicability_to_dict(analyze(signals, engine_after))
    assert would_be != recorded, "the mutation must actually change what a recompute would say"

    # (b) + (c) a fresh store over a fresh connection — nothing cached survives
    fresh_connection = psycopg.connect(dsn, autocommit=True)
    try:
        fresh_store = PostgresGovernanceStore(connection=fresh_connection)
        read_back = fresh_store.latest_applicability_version("sess_frozen", "t")
    finally:
        fresh_connection.close()

    assert read_back["applicability"] == recorded
    assert read_back["applicability"] != would_be
    assert read_back["engine_pack_versions"] == {"pack:core": "1.0"}, (
        "the version records the packs that RULED, not the packs installed today"
    )


def _extra_rule():
    from governance_discovery.pack import Effect, PlanSeed, Rule

    return Rule(
        id="rule:test_only_extra",
        version="1.0",
        predicate={"signal": "primary_activity", "op": "eq", "value": "technology"},
        effect=Effect(
            plan_seed=PlanSeed(
                id="seed:test_only",
                pillar="security",
                title_key="plan.seed.test_only.title",
                rationale_key="plan.seed.test_only.rationale",
                urgency="high",
                effort_size="small",
            )
        ),
    )


def _replace_pack(pack, **changes):
    import dataclasses

    return dataclasses.replace(pack, **changes)
