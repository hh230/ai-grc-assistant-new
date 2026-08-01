"""Durability — work does not vanish because the process did.

The baseline of the Production Composition suite. Each test creates something through one app
instance and reads it back through a **different** app instance over the same database: two
processes, one truth. Against the Development Composition every one of these fails, because a
dictionary dies with its process.

These are expected to **pass on arrival** — `create_app` already accepts injected adapters, so what
they prove is that the durable adapters work *through the host*, end to end over HTTP. That is the
measurable baseline the rest of Wave 1 is judged against.
"""

from __future__ import annotations

from collections.abc import Callable

import psycopg
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.production.conftest import AUTH_A, AUTH_B, Tables, create_mission


def test_a_created_mission_survives_a_new_app_instance(
    build_app: Callable[..., FastAPI],
) -> None:
    first = TestClient(build_app())
    mission_id = create_mission(first)

    # A second app over the same tables — this suite's stand-in for a restart.
    second = TestClient(build_app())
    found = second.get(f"/v1/missions/{mission_id}", headers=AUTH_A)

    assert found.status_code == 200, found.text
    assert found.json()["id"] == mission_id


def test_the_mission_list_survives_a_new_app_instance(
    build_app: Callable[..., FastAPI],
) -> None:
    first = TestClient(build_app())
    create_mission(first, scope="Organizational controls")
    create_mission(first, mission_type="risk_assessment", scope="Customer database")

    second = TestClient(build_app())
    listed = second.get("/v1/missions", headers=AUTH_A)

    assert listed.status_code == 200, listed.text
    scopes = {item["scope"] for item in listed.json()["items"]}
    assert scopes == {"Organizational controls", "Customer database"}


def test_uploaded_evidence_survives_a_new_app_instance(
    build_app: Callable[..., FastAPI],
) -> None:
    first = TestClient(build_app())
    upload = first.post(
        "/v1/documents",
        data={"evidence_kind": "policy"},
        files={"file": ("access-control-policy.md", b"Least privilege applies.", "text/markdown")},
        headers=AUTH_A,
    )
    assert upload.status_code == 201, upload.text

    second = TestClient(build_app())
    listed = second.get("/v1/documents", headers=AUTH_A)

    assert listed.status_code == 200, listed.text
    assert [doc["filename"] for doc in listed.json()["items"]] == ["access-control-policy.md"]


def test_tenant_isolation_holds_when_sql_is_what_enforces_it(
    build_app: Callable[..., FastAPI],
) -> None:
    """Isolation was previously guaranteed by a `{tenant: {id: mission}}` dictionary. Here it is a
    `WHERE tenant_id = %s`. The guarantee must be identical: absent, not forbidden — B is never told
    that A's mission exists."""
    app = TestClient(build_app())
    mission_id = create_mission(app, headers=AUTH_A)

    assert app.get(f"/v1/missions/{mission_id}", headers=AUTH_B).status_code == 404
    assert app.get("/v1/missions", headers=AUTH_B).json()["items"] == []


def test_the_durable_rows_carry_their_tenant(
    client: TestClient,
    observer: psycopg.Connection,
    tables: Tables,
) -> None:
    """Out-of-band: the row itself is stamped, so isolation does not depend on the query alone."""
    mission_id = create_mission(client, headers=AUTH_A)

    row = observer.execute(
        f"SELECT tenant_id FROM {tables.missions} WHERE id = %s",  # noqa: S608 - test-owned table
        (mission_id,),
    ).fetchone()

    assert row is not None, "the mission was not written to PostgreSQL at all"
    assert row[0] == "tenant-a"
