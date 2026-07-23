"""DB-gated fixtures for the Mission Integration end-to-end suite.

Every scenario here drives the *real* path against a *real* PostgreSQL — that is the whole point of
an integration phase. The suite connects to `MISSION_STORE_DSN` (default: the isolated `rasheed_v2`
dev DB) and **skips cleanly** when no database is reachable, exactly like the frozen store's own
integration suites, so CI without a database stays green.

Each test stands the missions + outbox schema up on throwaway `*_it_*` tables (via the frozen
`apply_schema` / `apply_outbox_schema`) and drops them after, so nothing pollutes the canonical
tables. The `runtime` fixture binds a `MissionRuntime` to those throwaway tables; the `observer`
fixture is a separate autocommit connection for low-level, out-of-band assertions on the raw rows.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import psycopg  # a hard dev dependency of this DB-integration package (always installed for tests)
import pytest
from mission_integration import MissionRuntime
from mission_store.config import dsn as default_dsn
from mission_store.outbox_schema import apply_outbox_schema
from mission_store.schema import apply_schema
from pipeline_contracts import TenantContext


def _connect(*, autocommit: bool = False) -> psycopg.Connection:
    try:
        return psycopg.connect(default_dsn(), connect_timeout=3, autocommit=autocommit)
    except Exception as exc:  # noqa: BLE001 - any connect failure means "no DB": skip, do not error
        pytest.skip(f"no reachable PostgreSQL ({exc})")


@pytest.fixture
def observer() -> Iterator[psycopg.Connection]:
    """A separate autocommit connection for out-of-band assertions on the raw missions/outbox rows
    (never the connection under test)."""
    conn = _connect(autocommit=True)
    yield conn
    conn.close()


@pytest.fixture
def tables(observer: psycopg.Connection) -> Iterator[tuple[str, str]]:
    suffix = uuid.uuid4().hex[:8]
    missions_table = f"missions_it_{suffix}"
    outbox_table = f"outbox_it_{suffix}"
    apply_schema(observer, missions_table)
    apply_outbox_schema(observer, outbox_table)
    yield missions_table, outbox_table
    observer.execute(f"DROP TABLE IF EXISTS {missions_table}")
    observer.execute(f"DROP TABLE IF EXISTS {outbox_table}")


@pytest.fixture
def runtime(tables: tuple[str, str]) -> MissionRuntime:
    missions_table, outbox_table = tables
    return MissionRuntime(missions_table=missions_table, outbox_table=outbox_table)


@pytest.fixture
def tenant() -> TenantContext:
    return TenantContext(
        tenant_id="org_acme", principal_id="u_owner", roles=("owner", "admin"), region="ksa"
    )


@pytest.fixture
def other_tenant() -> TenantContext:
    return TenantContext(tenant_id="org_globex", principal_id="u_intruder")
