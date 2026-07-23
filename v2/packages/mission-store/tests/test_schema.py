"""The schema module is the single source of truth for the *current* table shape; the ordered
migrations must reproduce it. `schema.py` renders the full current table (used for fresh/throwaway
setup); production applies the migrations in order — `0001_missions.sql` creates the base table and
`0003_approval.sql` adds the `approval` column (ADR 0044, Slice 1). No database needed."""

from __future__ import annotations

from pathlib import Path

from mission_store.codec import COLUMNS
from mission_store.schema import create_table_sql, index_sql

_MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"
_BASE = _MIGRATIONS / "0001_missions.sql"
_APPROVAL = _MIGRATIONS / "0003_approval.sql"

# Store-managed columns present in the table but not owned by the codec (ADR 0043 §7).
_STORE_COLUMNS = ("revision", "stored_at", "row_updated_at")


def _norm(text: str) -> str:
    return " ".join(text.split())


def _without_approval(sql: str) -> str:
    """The current create-table SQL with the later-added `approval` column line removed: the frozen
    base table that `0001` declares. Lets us assert base parity without a second DDL render."""
    return "\n".join(
        line for line in sql.splitlines() if not line.strip().startswith("approval ")
    )


def test_create_table_sql_declares_every_codec_and_store_column() -> None:
    sql = create_table_sql("missions")
    for column in (*COLUMNS, *_STORE_COLUMNS):
        assert f" {column} " in sql or f"\n    {column} " in sql, f"missing column: {column}"


def test_index_names_are_derived_from_the_table() -> None:
    statements = index_sql("missions_it_abc")
    assert any("missions_it_abc_tenant_idx" in s for s in statements)
    assert any("missions_it_abc_idem_idx" in s for s in statements)
    # the idempotency index is a PARTIAL unique index (per tenant, non-empty key only)
    assert any("UNIQUE" in s and "idempotency_key <> ''" in s for s in statements)


def test_base_table_and_indexes_match_0001() -> None:
    """The frozen base migration `0001` must carry exactly what `schema.py` renders for every column
    EXCEPT the later-added `approval` (same columns, types, constraints, indexes). Compared
    whitespace-insensitively, so only substantive drift fails."""
    migration = _norm(_BASE.read_text(encoding="utf-8"))
    assert _norm(_without_approval(create_table_sql("missions")).rstrip(";\n")) in migration
    for statement in index_sql("missions"):
        assert _norm(statement) in migration


def test_approval_column_added_additively_by_0003() -> None:
    """`approval` is added by `0003` as a nullable JSONB column via an idempotent, additive ALTER —
    never by editing the frozen `0001`, and never as a non-null/defaulted column (which would break
    existing rows)."""
    migration = _norm(_APPROVAL.read_text(encoding="utf-8")).lower()
    assert "alter table missions add column if not exists approval jsonb" in migration
    # schema.py declares it too, so fresh/throwaway tables get it without running 0003.
    assert " approval " in create_table_sql("missions")
