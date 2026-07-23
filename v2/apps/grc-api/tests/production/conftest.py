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
from dataclasses import dataclass
from typing import Any

import psycopg  # dev-only dependency of this app; always installed for tests
import pytest
from document_read_model import PostgresDocumentReadModel
from document_read_model import create_table_sql as document_table_sql
from fastapi import FastAPI
from fastapi.testclient import TestClient
from grc_api.app import create_app
from mission_engine import MissionEngine
from mission_read_model import PostgresMissionListReadModel
from mission_read_model import create_table_sql as mission_table_sql
from mission_store import PostgresMissionStore
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


@dataclass(frozen=True)
class Tables:
    """The four throwaway tables one test runs against — the whole durable surface the product
    touches: the Core's missions + outbox, and the two product read models (ADR 0053)."""

    missions: str
    outbox: str
    missions_read_model: str
    documents_read_model: str


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
        missions_read_model=f"mrm_pc_{suffix}",
        documents_read_model=f"drm_pc_{suffix}",
    )
    apply_schema(observer, created.missions)
    apply_outbox_schema(observer, created.outbox)
    observer.execute(mission_table_sql(created.missions_read_model))
    observer.execute(document_table_sql(created.documents_read_model))
    yield created
    for table in (
        created.missions,
        created.outbox,
        created.missions_read_model,
        created.documents_read_model,
    ):
        observer.execute(f"DROP TABLE IF EXISTS {table}")


@pytest.fixture
def build_app(tables: Tables) -> Iterator[Callable[..., FastAPI]]:
    """Build the API over the durable adapters. **Each call opens its own connection**, so calling
    it twice models two processes over one database — which is how the durability tests stand in for
    a restart without actually restarting anything.

    `executor` and `read_model` are overridable so a test can inject a probe or a deliberate
    failure; everything else is the composition a deployment would use. An injected executor is
    wrapped in an engine over *this* app's store, exactly as the host does it — a test never hands
    in an engine bound to some other store.
    """
    connections: list[psycopg.Connection] = []

    def _build(*, executor: Any | None = None, read_model: Any | None = None) -> FastAPI:
        conn = connect(autocommit=True)
        connections.append(conn)
        store = PostgresMissionStore(connection=conn, table=tables.missions)
        missions_view = (
            read_model
            if read_model is not None
            else PostgresMissionListReadModel(
                connection=conn, table=tables.missions_read_model
            )
        )
        documents_view = PostgresDocumentReadModel(
            connection=conn, table=tables.documents_read_model
        )
        return create_app(
            read_model=missions_view,
            mission_store=store,
            mission_engine=MissionEngine(store, executor) if executor is not None else None,
            document_read_model=documents_view,
        )

    yield _build
    for connection in connections:
        connection.close()


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
