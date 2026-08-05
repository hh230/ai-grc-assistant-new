"""The `.sql` migration and the Python DDL must describe the SAME table.

The schema is written twice: `pg/schema.py` applies it at runtime (split into table / filter
indexes / HNSW so a bulk import can build the ANN index after loading), and
`migrations/0001_knowledge_vectors.sql` is the canonical documented copy an operator provisions
from. `schema.py` says so in its own docstring.

They drifted. `scope_kind` and `organization_id` (ADR 0040 tenancy) were added to the Python DDL
and to every query the provider builds, but never to the `.sql`. The result was invisible in CI —
the pgvector tests skip without a database — and only surfaced against a real Postgres, as
`UndefinedColumn: column "scope_kind" does not exist`. Anyone provisioning from the committed
migration got a table the code could not query.

Duplication that drifts silently is worse than duplication that shouts, so this test shouts.
"""

from __future__ import annotations

import pathlib
import re

from retrieval_engine.pg import schema
from retrieval_engine.pg.config import TABLE

MIGRATION = (
    pathlib.Path(__file__).resolve().parents[1] / "migrations" / "0001_knowledge_vectors.sql"
)


def _columns(ddl: str) -> set[str]:
    """Column names from a `CREATE TABLE (...)` body, ignoring comments and constraints."""
    body = ddl.split(f"{TABLE} (", 1)[1].rsplit(");", 1)[0]
    found = set()
    for raw in body.splitlines():
        line = raw.split("--", 1)[0].strip()
        if not line:
            continue
        name = line.split()[0]
        if re.fullmatch(r"[a-z_]+", name):
            found.add(name)
    return found


def _indexes(ddl: str) -> set[str]:
    return set(re.findall(r"CREATE INDEX IF NOT EXISTS\s+(\w+)", ddl))


def test_the_migration_and_the_python_ddl_declare_the_same_columns():
    sql = MIGRATION.read_text(encoding="utf-8")
    from_sql, from_python = _columns(sql), _columns(schema._TABLE_DDL)

    assert from_python, "parsed no columns out of the Python DDL — the parser is broken"
    assert from_sql == from_python, (
        f"schema drift.\n  only in migration: {sorted(from_sql - from_python)}"
        f"\n  only in schema.py: {sorted(from_python - from_sql)}"
    )


def test_the_migration_and_the_python_ddl_declare_the_same_indexes():
    sql = MIGRATION.read_text(encoding="utf-8")
    python_ddl = "\n".join([*schema._FILTER_INDEXES, schema._HNSW_DDL])
    from_sql, from_python = _indexes(sql), _indexes(python_ddl)

    assert from_python, "parsed no indexes out of the Python DDL — the parser is broken"
    assert from_sql == from_python, (
        f"index drift.\n  only in migration: {sorted(from_sql - from_python)}"
        f"\n  only in schema.py: {sorted(from_python - from_sql)}"
    )


def test_every_column_the_provider_queries_actually_exists():
    """The specific failure that started this: a query column absent from both DDLs."""
    provider = (
        pathlib.Path(__file__).resolve().parents[1]
        / "retrieval_engine" / "providers" / "pgvector_provider.py"
    ).read_text(encoding="utf-8")
    declared = _columns(schema._TABLE_DDL)

    for column in ("scope_kind", "organization_id", "document_profile", "category", "language"):
        assert column in provider, f"{column} is no longer queried — update this test"
        assert column in declared, f"the provider queries {column!r}, but no DDL creates it"
