"""Unit tests for DSN normalization — no database required."""

from __future__ import annotations

from grc_persistence_web import normalize_dsn


def test_normalize_strips_asyncpg_driver_suffix() -> None:
    assert (
        normalize_dsn("postgresql+asyncpg://u:p@localhost:5432/db")
        == "postgresql://u:p@localhost:5432/db"
    )


def test_normalize_strips_psycopg_driver_suffix() -> None:
    assert (
        normalize_dsn("postgres+psycopg2://u:p@localhost:5432/db")
        == "postgres://u:p@localhost:5432/db"
    )


def test_normalize_is_a_no_op_for_plain_scheme() -> None:
    plain = "postgresql://u:p@localhost:5432/db"
    assert normalize_dsn(plain) == plain


def test_normalize_drops_prisma_style_schema_param() -> None:
    # Matches the repo's actual dev DATABASE_URL: asyncpg rejects "?schema=" outright
    # (UndefinedObjectError: unrecognized configuration parameter "schema").
    normalized = normalize_dsn("postgresql://postgres:postgres@localhost:5432/aigrc?schema=public")
    assert normalized == "postgresql://postgres:postgres@localhost:5432/aigrc"


def test_normalize_keeps_other_query_params() -> None:
    normalized = normalize_dsn(
        "postgresql+asyncpg://u:p@localhost:5432/db?schema=public&sslmode=require"
    )
    assert normalized == "postgresql://u:p@localhost:5432/db?sslmode=require"
