"""DB-gated fixtures for the Production Composition suite (see README.md).

These compose the **real** API host over the **durable** adapters — `PostgresMissionStore`, both
`Postgres*ReadModel`s — and hand back a `TestClient`. Nothing here reaches into the host's
internals: the app is built through `create_app`'s existing composition parameters, so this suite
constrains behaviour, not design.

Two rules borrowed from the frozen packages' own integration suites:

- **Skip, never fail, without a database.** A CI without PostgreSQL stays green.
- **Throwaway tables.** Every test stands up its own `*_pc_<suffix>` tables and drops them, so the
  canonical `missions` / `outbox` tables are never touched.

The `observer` connection is deliberately *separate* from the app's: it is how a test asks what
another session can see, which is the only honest way to assert a transaction boundary.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterator
from typing import Any

import psycopg  # dev-only dependency of this app; always installed for tests
import pytest
from document_read_model import create_table_sql as document_table_sql
from fastapi import FastAPI
from fastapi.testclient import TestClient
from grc_api.app import create_app
from grc_api.composition import Storage, Tables
from mission_read_model import create_table_sql as mission_table_sql
from mission_store.config import dsn as default_dsn
from mission_store.outbox_schema import apply_outbox_schema
from mission_store.schema import apply_schema

# The seeded development credentials the host resolves today. When Wave 1 replaces the identity
# provider these become whatever the real provider issues — the tests care about *a tenant A* and
# *a tenant B*, not about how the credential is minted.
AUTH_A = {"Authorization": "Bearer dev-tenant-a"}
AUTH_APPROVER_A = {"Authorization": "Bearer dev-approver-a"}
AUTH_B = {"Authorization": "Bearer dev-tenant-b"}


def connect(*, autocommit: bool = False) -> psycopg.Connection:
    """Open a connection, or skip the test. Any connect failure means "no database here" — that is
    an environment fact, never a test failure."""
    try:
        return psycopg.connect(default_dsn(), connect_timeout=3, autocommit=autocommit)
    except Exception as exc:  # noqa: BLE001 - any failure to connect means "no DB": skip
        pytest.skip(f"no reachable PostgreSQL ({exc})")


@pytest.fixture
def observer() -> Iterator[psycopg.Connection]:
    """A separate autocommit session, used only for out-of-band assertions on raw rows. It is never
    the connection under test — that separation is what makes a visibility assertion meaningful."""
    conn = connect(autocommit=True)
    yield conn
    conn.close()


@pytest.fixture
def tables(observer: psycopg.Connection) -> Iterator[Tables]:
    suffix = uuid.uuid4().hex[:8]
    created = Tables(
        missions=f"missions_pc_{suffix}",
        outbox=f"outbox_pc_{suffix}",
        missions_view=f"mrm_pc_{suffix}",
        documents_view=f"drm_pc_{suffix}",
    )
    apply_schema(observer, created.missions)
    apply_outbox_schema(observer, created.outbox)
    observer.execute(mission_table_sql(created.missions_view))
    observer.execute(document_table_sql(created.documents_view))
    yield created
    for table in (
        created.missions,
        created.outbox,
        created.missions_view,
        created.documents_view,
    ):
        observer.execute(f"DROP TABLE IF EXISTS {table}")


@pytest.fixture
def build_app(tables: Tables) -> Callable[..., FastAPI]:
    """Build the API over the **durable** composition, pointed at this test's throwaway tables.

    Note what it no longer does: it does not hand the host a pre-built store. It cannot — ADR 0055
    left no store to hand over. The host composes its own reader and its own per-command scope, and
    the test only says *where* to write. That is the difference between observing the real
    composition and observing a substitute for it.

    `executor` is overridable so a test can watch execution from inside; everything else is the
    composition a deployment gets.
    """

    def _build(*, executor: Any | None = None, read_model: Any | None = None) -> FastAPI:
        return create_app(
            storage=Storage.DURABLE,
            tables=tables,
            executor=executor,
            read_model=read_model,
        )

    return _build


@pytest.fixture
def client(build_app: Callable[..., FastAPI]) -> TestClient:
    """The durable API — the same host every other suite exercises, over PostgreSQL instead of
    dictionaries."""
    return TestClient(build_app())


def create_mission(
    client: TestClient,
    *,
    mission_type: str = "gap_assessment",
    scope: str = "Technological controls",
    headers: dict[str, str] | None = None,
) -> str:
    """Create a mission through the API and return its id — the arrangement half of most tests."""
    response = client.post(
        "/v1/missions",
        json={"type": mission_type, "scope": scope, "document_ids": []},
        headers={**(headers or AUTH_A), "Idempotency-Key": uuid.uuid4().hex},
    )
    assert response.status_code == 201, response.text
    mission_id: str = response.json()["mission"]["id"]
    return mission_id
