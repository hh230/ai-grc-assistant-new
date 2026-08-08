"""Referential integrity for ADR 0068's two new references, against a real Postgres.

Every case here was ACCEPTED before 0021 existed — review found them by doing them, not by reading
the migration. An orphan version and a plan citing a version id that never existed both inserted
silently, which is the state an unenforced reference always ends in.

The references are COMPOSITE `(id, tenant_id)`, following `sector_answers` (0015): a simple key on
the id alone would let tenant A cite tenant B's row and leave isolation depending on every query
remembering to filter.
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
DEFAULT_DSN = "postgresql://postgres:postgres@localhost:5432/rasheed_adr68_integrity_tests"


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
    for table in (
        "governance_plan_items", "governance_plans", "session_applicability_versions",
        "discovery_answers", "discovery_sessions",
    ):
        conn.execute(f"DELETE FROM {table}")
    conn.execute("SET session_replication_role = DEFAULT")
    return conn


def _session(conn, session_id="sess_1", tenant="t"):
    conn.execute(
        "INSERT INTO discovery_sessions (id, tenant_id, status, signals, confidence_score, "
        " created_at, updated_at) VALUES (%s, %s, 'concluded', '{}'::jsonb, 1, 0, 0)",
        (session_id, tenant),
    )
    return session_id


def _version(conn, session_id, tenant="t", version_id=None, version=1):
    version_id = version_id or f"av_{uuid.uuid4().hex[:12]}"
    conn.execute(
        "INSERT INTO session_applicability_versions (id, tenant_id, session_id, version, source, "
        " applicability, answer_set_hash) VALUES (%s, %s, %s, %s, 'core_conclusion', "
        "'{}'::jsonb, 'h')",
        (version_id, tenant, session_id, version),
    )
    return version_id


def _plan(conn, tenant="t", plan_id="plan_1", session_id=None, applicability_id=None):
    conn.execute(
        "INSERT INTO governance_plans (id, tenant_id, version, status, source_session_id, "
        " source_mission_id, inferred_frameworks, maturity_baseline, top_risks, "
        " executive_summary, created_at, updated_at, source_applicability_id) "
        "VALUES (%s, %s, 1, 'active', %s, 'mis_1', '[]'::jsonb, '{}'::jsonb, '[]'::jsonb, '', "
        "0, 0, %s)",
        (plan_id, tenant, session_id, applicability_id),
    )
    return plan_id


# --- an orphan version is refused ---------------------------------------------------------------


def test_a_version_for_a_session_that_does_not_exist_is_refused(clean) -> None:
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        _version(clean, "sess_that_never_existed")


def test_a_version_cannot_reach_into_another_tenants_session(clean) -> None:
    """The composite key's whole purpose: the id resolves, the tenant does not."""
    _session(clean, "sess_a", tenant="tenant_a")
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        _version(clean, "sess_a", tenant="tenant_b")


def test_a_version_for_a_real_session_in_the_same_tenant_is_accepted(clean) -> None:
    _session(clean, "sess_ok", tenant="tenant_a")
    assert _version(clean, "sess_ok", tenant="tenant_a")


# --- a plan cannot cite an analysis that does not exist ------------------------------------------


def test_a_plan_citing_a_version_that_does_not_exist_is_refused(clean) -> None:
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        _plan(clean, applicability_id="av_invented")


def test_a_plan_cannot_cite_another_tenants_version(clean) -> None:
    _session(clean, "sess_a", tenant="tenant_a")
    version_id = _version(clean, "sess_a", tenant="tenant_a")
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        _plan(clean, tenant="tenant_b", applicability_id=version_id)


def test_a_plan_with_no_recorded_version_still_inserts(clean) -> None:
    """Nullable on purpose: a plan drafted before this table exists has no version to point at, and
    inventing one would be a lie with a timestamp. MATCH SIMPLE lets the composite key pass when
    either column is NULL."""
    assert _plan(clean, applicability_id=None)


# --- deleting a referenced row is refused --------------------------------------------------------


def test_a_session_with_a_version_cannot_be_deleted(clean) -> None:
    _session(clean, "sess_ref")
    _version(clean, "sess_ref")
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        clean.execute("DELETE FROM discovery_sessions WHERE id = 'sess_ref'")


def test_a_version_a_plan_cites_cannot_be_deleted(clean) -> None:
    """Two independent refusals now stand in front of this row: the append-only trigger from 0018
    and the foreign key from 0021. The trigger fires first; the key would hold even without it."""
    _session(clean, "sess_ref")
    version_id = _version(clean, "sess_ref")
    _plan(clean, applicability_id=version_id)
    with pytest.raises((psycopg.errors.RaiseException, psycopg.errors.ForeignKeyViolation)):
        clean.execute("DELETE FROM session_applicability_versions WHERE id = %s", (version_id,))
