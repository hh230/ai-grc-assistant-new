"""`schema.py` is the single source of truth for the current table shape; the ordered migrations
under `migrations/` must reproduce it exactly (whitespace-insensitively). No database needed —
mirrors `mission_store/tests/test_schema.py`'s parity-test discipline (ADR 0043 §7)."""

from __future__ import annotations

from pathlib import Path

from governance_store.config import (
    TABLE_DISCOVERY_ANSWERS,
    TABLE_DISCOVERY_SESSIONS,
    TABLE_GOVERNANCE_PLAN_EVENTS,
    TABLE_GOVERNANCE_PLAN_ITEMS,
    TABLE_GOVERNANCE_PLANS,
    TABLE_ORGANIZATION_PROFILES,
)
from governance_store.schema import create_table_sql, index_sql

_MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"


def _norm(text: str) -> str:
    return " ".join(text.split())


def test_every_table_has_a_primary_key_and_tenant_id_column() -> None:
    for table in (
        TABLE_ORGANIZATION_PROFILES,
        TABLE_DISCOVERY_SESSIONS,
        TABLE_DISCOVERY_ANSWERS,
        TABLE_GOVERNANCE_PLANS,
        TABLE_GOVERNANCE_PLAN_ITEMS,
        TABLE_GOVERNANCE_PLAN_EVENTS,
    ):
        sql = create_table_sql(table)
        assert "PRIMARY KEY" in sql, f"{table}: missing primary key"
        assert "tenant_id" in sql, f"{table}: missing tenant_id (CLAUDE.md §20)"


def test_raw_answer_is_nullable_to_represent_a_skipped_question() -> None:
    sql = create_table_sql(TABLE_DISCOVERY_ANSWERS)
    for line in sql.splitlines():
        if line.strip().startswith("raw_answer"):
            assert "NOT NULL" not in line
            return
    raise AssertionError("raw_answer column not found")


def test_index_names_are_derived_from_the_table() -> None:
    statements = index_sql(TABLE_DISCOVERY_SESSIONS)
    assert any("discovery_sessions_tenant_idx" in s for s in statements)
    assert any("discovery_sessions_tenant_status_idx" in s for s in statements)


def test_discovery_answers_sequence_is_unique_per_session() -> None:
    statements = index_sql(TABLE_DISCOVERY_ANSWERS)
    assert any(
        "UNIQUE" in s and "(session_id, sequence)" in s for s in statements
    ), "re-answering must not silently collide on (session_id, sequence)"


def test_organization_profiles_0001_matches_schema() -> None:
    migration = _norm((_MIGRATIONS / "0001_organization_profiles.sql").read_text(encoding="utf-8"))
    assert _norm(create_table_sql(TABLE_ORGANIZATION_PROFILES).rstrip(";\n")) in migration


def test_discovery_0002_matches_schema() -> None:
    migration = _norm((_MIGRATIONS / "0002_discovery.sql").read_text(encoding="utf-8"))
    assert _norm(create_table_sql(TABLE_DISCOVERY_SESSIONS).rstrip(";\n")) in migration
    assert _norm(create_table_sql(TABLE_DISCOVERY_ANSWERS).rstrip(";\n")) in migration
    for statement in (*index_sql(TABLE_DISCOVERY_SESSIONS), *index_sql(TABLE_DISCOVERY_ANSWERS)):
        assert _norm(statement) in migration


def test_governance_plans_0003_matches_schema() -> None:
    migration = _norm((_MIGRATIONS / "0003_governance_plans.sql").read_text(encoding="utf-8"))
    assert _norm(create_table_sql(TABLE_GOVERNANCE_PLANS).rstrip(";\n")) in migration
    assert _norm(create_table_sql(TABLE_GOVERNANCE_PLAN_ITEMS).rstrip(";\n")) in migration
    assert _norm(create_table_sql(TABLE_GOVERNANCE_PLAN_EVENTS).rstrip(";\n")) in migration
    for statement in (
        *index_sql(TABLE_GOVERNANCE_PLANS),
        *index_sql(TABLE_GOVERNANCE_PLAN_ITEMS),
        *index_sql(TABLE_GOVERNANCE_PLAN_EVENTS),
    ):
        assert _norm(statement) in migration


def test_governance_plans_are_versioned_snapshots() -> None:
    """ADR 0066 §3.1: a plan row carries explicit lineage, never edited in place."""
    sql = create_table_sql(TABLE_GOVERNANCE_PLANS)
    for column in ("version", "previous_plan_id", "maturity_at_supersession"):
        assert column in sql, f"missing {column} (ADR 0066 §3.1)"


def test_governance_plan_items_support_resolves_signal_and_optional_evidence() -> None:
    sql = create_table_sql(TABLE_GOVERNANCE_PLAN_ITEMS)
    assert "resolves_signal" in sql
    assert "evidence_ids" in sql
    assert "confidence" in sql
    for line in sql.splitlines():
        if line.strip().startswith("evidence_ids"):
            assert "NOT NULL" in line and "DEFAULT" in line  # optional, but never absent/null
        if line.strip().startswith("resolves_signal"):
            assert "NOT NULL" not in line  # optional — not every item resolves a signal


def test_apply_schema_is_importable_without_psycopg_installed() -> None:
    # schema.py must import cleanly even when the `postgres` extra isn't installed — the driver
    # is only referenced under TYPE_CHECKING / inside the function body.
    import governance_store.schema  # noqa: F401
