"""Postgres adapter tests.

Two layers:
- **Driver-free** checks that always run: the module imports without psycopg, the DDL is well-
  formed, and the class is exposed. These guard the "loads without the driver" contract.
- **DB-gated** checks that run the *same* S4 acceptance (tenant isolation, collections + counts,
  kind filter, ordering, upsert) against a real throwaway table — and **auto-skip** when psycopg or
  a Postgres is absent, so the suite is green anywhere. The DSN is `DOCUMENT_READ_MODEL_TEST_DSN`.
"""

from __future__ import annotations

import os

import pytest
from document_read_model import (
    DocumentItem,
    PostgresDocumentReadModel,
    create_table_sql,
)
from pipeline_contracts import TenantContext

# --- driver-free -----------------------------------------------------------------------


def test_module_imports_without_driver() -> None:
    # Importing the class must not require psycopg (lazy load happens only on instantiation).
    assert PostgresDocumentReadModel is not None


def test_ddl_mentions_the_columns_and_indexes() -> None:
    ddl = create_table_sql("drm_test")
    assert "CREATE TABLE IF NOT EXISTS drm_test" in ddl
    for col in ("document_id", "tenant_id", "filename", "evidence_kind", "status", "size"):
        assert col in ddl
    assert "tenant_id, uploaded_at DESC" in ddl  # newest-first, tenant-first index
    assert "tenant_id, evidence_kind" in ddl  # collections grouping index


# --- DB-gated (auto-skip without Postgres) ---------------------------------------------


@pytest.fixture
def pg_read_model():  # type: ignore[no-untyped-def]
    dsn = os.environ.get("DOCUMENT_READ_MODEL_TEST_DSN")
    if not dsn:
        pytest.skip("no DOCUMENT_READ_MODEL_TEST_DSN — Postgres adapter integration skipped")
    try:
        import psycopg
    except ImportError:
        pytest.skip("psycopg not installed — Postgres adapter integration skipped")
    try:
        conn = psycopg.connect(dsn, autocommit=True)
    except Exception as exc:  # pragma: no cover - env dependent
        pytest.skip(f"Postgres not reachable: {exc}")
    table = "drm_test_s4"
    conn.execute(f"DROP TABLE IF EXISTS {table}")
    conn.execute(create_table_sql(table))
    yield PostgresDocumentReadModel(connection=conn, table=table)
    conn.execute(f"DROP TABLE IF EXISTS {table}")
    conn.close()


def _tenant(tenant_id: str) -> TenantContext:
    return TenantContext(tenant_id=tenant_id, principal_id="u", roles=(), region="ksa")


def _item(
    document_id: str,
    tenant_id: str,
    evidence_kind: str,
    uploaded_at: float,
    *,
    status: str = "ready",
    size: int = 1024,
) -> DocumentItem:
    return DocumentItem(
        document_id=document_id,
        tenant_id=tenant_id,
        filename=f"{document_id}.pdf",
        evidence_kind=evidence_kind,
        status=status,
        uploaded_at=uploaded_at,
        size=size,
    )


def test_pg_isolation_and_collections(pg_read_model) -> None:  # type: ignore[no-untyped-def]
    rm = pg_read_model
    rm.record(_item("d1", "T", "policy", 500.0))
    rm.record(_item("d2", "T", "policy", 400.0))
    rm.record(_item("d3", "T", "procedure", 300.0))
    rm.record(_item("d4", "T", "soc_report", 200.0))
    rm.record(_item("x1", "T2", "policy", 100.0))

    # tenant isolation + newest-first
    assert [d.document_id for d in rm.list_documents(_tenant("T"))] == ["d1", "d2", "d3", "d4"]
    assert [d.document_id for d in rm.list_documents(_tenant("T2"))] == ["x1"]

    # Evidence Collections: grouped by kind, counted, in product display order
    collections = [(c.evidence_kind, c.count) for c in rm.list_collections(_tenant("T"))]
    assert collections == [("policy", 2), ("procedure", 1), ("soc_report", 1)]

    # opening a collection filters to its kind, tenant-scoped
    assert [d.document_id for d in rm.list_documents(_tenant("T"), evidence_kind="policy")] == [
        "d1",
        "d2",
    ]

    # upsert (idempotent by document_id): a status advance replaces the row
    rm.record(_item("d1", "T", "policy", 500.0, status="ready", size=4096))
    assert len(rm.list_documents(_tenant("T"))) == 4
    got = rm.get("d1", _tenant("T"))
    assert got is not None and got.size == 4096

    # get is fail-closed across tenants
    assert rm.get("x1", _tenant("T")) is None
