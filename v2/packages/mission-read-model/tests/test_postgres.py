"""Postgres adapter tests.

Two layers:
- **Driver-free** checks that always run: the module imports without psycopg, the DDL is
  well-formed, and the class is exposed. These guard the "loads without the driver" contract.
- **DB-gated** checks that run the *same* S1 acceptance (tenant isolation, filters, search,
  paging, upsert) against a real throwaway table — and **auto-skip** when psycopg or a Postgres
  is absent, so the suite is green anywhere. The DSN comes from `MISSION_READ_MODEL_TEST_DSN`.
"""

from __future__ import annotations

import os

import pytest
from mission_read_model import (
    MissionListItem,
    PostgresMissionListReadModel,
    create_table_sql,
)
from pipeline_contracts import TenantContext

# --- driver-free -----------------------------------------------------------------------


def test_module_imports_without_driver() -> None:
    # Importing the class must not require psycopg (lazy load happens only on instantiation).
    assert PostgresMissionListReadModel is not None


def test_ddl_mentions_the_columns_and_tenant_index() -> None:
    ddl = create_table_sql("mrm_test")
    assert "CREATE TABLE IF NOT EXISTS mrm_test" in ddl
    for col in ("mission_id", "tenant_id", "mission_type", "title", "status"):
        assert col in ddl
    assert "tenant_id, updated_at DESC" in ddl  # newest-first, tenant-first index


# --- DB-gated (auto-skip without Postgres) ---------------------------------------------


@pytest.fixture
def pg_read_model():  # type: ignore[no-untyped-def]
    dsn = os.environ.get("MISSION_READ_MODEL_TEST_DSN")
    if not dsn:
        pytest.skip("no MISSION_READ_MODEL_TEST_DSN — Postgres adapter integration skipped")
    try:
        import psycopg
    except ImportError:
        pytest.skip("psycopg not installed — Postgres adapter integration skipped")
    try:
        conn = psycopg.connect(dsn, autocommit=True)
    except Exception as exc:  # pragma: no cover - env dependent
        pytest.skip(f"Postgres not reachable: {exc}")
    table = "mrm_test_s1"
    conn.execute(f"DROP TABLE IF EXISTS {table}")
    conn.execute(create_table_sql(table))
    yield PostgresMissionListReadModel(connection=conn, table=table)
    conn.execute(f"DROP TABLE IF EXISTS {table}")
    conn.close()


def _tenant(tenant_id: str) -> TenantContext:
    return TenantContext(tenant_id=tenant_id, principal_id="u", roles=(), region="ksa")


def _ids(page) -> list[str]:  # type: ignore[no-untyped-def]
    return [item.mission_id for item in page.items]


def test_pg_isolation_filters_and_paging(pg_read_model) -> None:  # type: ignore[no-untyped-def]
    rm = pg_read_model
    rm.record(MissionListItem("m1", "T", "gap_assessment", "Tech", "executing", 100.0, 300.0))
    rm.record(MissionListItem("m2", "T", "risk_assessment", "DB", "completed", 100.0, 200.0))
    rm.record(MissionListItem("m3", "T", "vendor_review", "Acme", "executing", 100.0, 100.0))
    rm.record(MissionListItem("x1", "T2", "gap_assessment", "Org", "executing", 100.0, 100.0))

    # tenant isolation + newest-first
    assert _ids(rm.list_missions(_tenant("T"))) == ["m1", "m2", "m3"]
    assert rm.list_missions(_tenant("T")).total == 3
    assert _ids(rm.list_missions(_tenant("T2"))) == ["x1"]

    # filters + case-insensitive search
    assert _ids(rm.list_missions(_tenant("T"), status="completed")) == ["m2"]
    assert _ids(rm.list_missions(_tenant("T"), query="acme")) == ["m3"]

    # paging
    p1 = rm.list_missions(_tenant("T"), page=1, page_size=2)
    assert _ids(p1) == ["m1", "m2"] and p1.has_next is True

    # upsert (idempotent by mission_id)
    rm.record(MissionListItem("m1", "T", "gap_assessment", "Tech", "completed", 100.0, 400.0))
    assert rm.list_missions(_tenant("T")).total == 3
