"""S1 acceptance at the HTTP edge: GET /v1/missions — fail-closed auth, tenant isolation, filters,
search, paging, and the uniform error envelope."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import AUTH_A, AUTH_B


def test_health_is_open(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


# --- fail-closed auth -------------------------------------------------------------------


def test_missing_token_is_401(client: TestClient) -> None:
    resp = client.get("/v1/missions")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"


def test_invalid_token_is_401(client: TestClient) -> None:
    resp = client.get("/v1/missions", headers={"Authorization": "Bearer nope"})
    assert resp.status_code == 401


# --- tenant isolation (end-to-end, via distinct tokens) ---------------------------------


def test_lists_only_the_callers_tenant(client: TestClient) -> None:
    body = client.get("/v1/missions", headers=AUTH_A).json()
    assert body["total"] == 3
    assert {row["id"] for row in body["items"]} == {"m1", "m2", "m3"}


def test_other_tenant_sees_its_own_only(client: TestClient) -> None:
    body = client.get("/v1/missions", headers=AUTH_B).json()
    assert {row["id"] for row in body["items"]} == {"x1", "x2"}
    # and A's missions never appear for B
    assert all(row["id"] not in {"m1", "m2", "m3"} for row in body["items"])


# --- representation hides implementation ------------------------------------------------


def test_row_shape_is_type_scope_status(client: TestClient) -> None:
    row = client.get("/v1/missions", headers=AUTH_A).json()["items"][0]
    assert set(row) == {"id", "type", "scope", "status", "created_at", "updated_at"}
    assert row["id"] == "m1" and row["type"] == "gap_assessment" and row["scope"] == "Technological"


# --- filters, search, paging ------------------------------------------------------------


def test_filter_by_status(client: TestClient) -> None:
    body = client.get("/v1/missions?status=completed", headers=AUTH_A).json()
    assert [row["id"] for row in body["items"]] == ["m2"]


def test_filter_by_type(client: TestClient) -> None:
    body = client.get("/v1/missions?type=vendor_review", headers=AUTH_A).json()
    assert [row["id"] for row in body["items"]] == ["m3"]


def test_search_by_scope(client: TestClient) -> None:
    body = client.get("/v1/missions?q=acme", headers=AUTH_A).json()
    assert [row["id"] for row in body["items"]] == ["m3"]


def test_pagination(client: TestClient) -> None:
    p1 = client.get("/v1/missions?page=1&page_size=2", headers=AUTH_A).json()
    assert [row["id"] for row in p1["items"]] == ["m1", "m2"]
    assert p1["total"] == 3 and p1["has_next"] is True
    p2 = client.get("/v1/missions?page=2&page_size=2", headers=AUTH_A).json()
    assert [row["id"] for row in p2["items"]] == ["m3"]
    assert p2["has_next"] is False


def test_bad_page_is_validation_error(client: TestClient) -> None:
    resp = client.get("/v1/missions?page=0", headers=AUTH_A)
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "validation_error"
