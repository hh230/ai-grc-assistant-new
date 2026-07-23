"""HTTP acceptance for Knowledge — `GET`/`POST /v1/documents` (Slice S4).

Proves the Execution Contract end-to-end over real routes: a Practitioner uploads evidence choosing
its kind; it is ingested and projected; the tenant lists its own evidence with kinds + ingestion
status; an unknown kind is rejected; an empty upload is honestly `failed`; and one tenant never sees
another's documents (fail-closed). Grouping into Evidence Collections is the client's job — the API
returns the flat, tenant-scoped document list.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from grc_api.app import create_app

AUTH_A = {"Authorization": "Bearer dev-tenant-a"}
AUTH_B = {"Authorization": "Bearer dev-tenant-b"}


def _client() -> TestClient:
    # A fresh app: empty document read model + knowledge base, seeded dev identities.
    return TestClient(create_app())


def _upload(
    client: TestClient,
    *,
    filename: str,
    kind: str,
    body: bytes,
    auth: dict[str, str] = AUTH_A,
):  # type: ignore[no-untyped-def]
    return client.post(
        "/v1/documents",
        data={"evidence_kind": kind},
        files={"file": (filename, body, "text/plain")},
        headers=auth,
    )


# --- auth ---------------------------------------------------------------------------------


def test_list_requires_auth() -> None:
    resp = _client().get("/v1/documents")
    assert resp.status_code == 401


# --- empty / list -------------------------------------------------------------------------


def test_list_is_empty_for_new_tenant() -> None:
    resp = _client().get("/v1/documents", headers=AUTH_A)
    assert resp.status_code == 200
    assert resp.json() == {"items": []}


# --- upload → project → list --------------------------------------------------------------


def test_upload_then_list_shows_kind_and_ready_status() -> None:
    client = _client()
    text = b"Access Control Policy. All access must be authorised and reviewed quarterly."
    resp = _upload(client, filename="aup.txt", kind="policy", body=text)
    assert resp.status_code == 201
    row = resp.json()
    assert row["filename"] == "aup.txt"
    assert row["evidence_kind"] == "policy"
    assert row["status"] == "ready"
    assert row["size"] == len(text)
    # never exposes implementation
    assert "chunk" not in row and "chunks" not in row

    listing = client.get("/v1/documents", headers=AUTH_A).json()["items"]
    assert [d["id"] for d in listing] == [row["id"]]
    assert listing[0]["evidence_kind"] == "policy"


def test_upload_supports_the_evidence_kinds_the_view_groups_by() -> None:
    client = _client()
    _upload(client, filename="aup.txt", kind="policy", body=b"policy text one here")
    _upload(client, filename="acl.txt", kind="policy", body=b"policy text two here")
    _upload(client, filename="ir.txt", kind="procedure", body=b"incident response steps")
    _upload(client, filename="soc2.txt", kind="soc_report", body=b"soc 2 type II report body")

    items = client.get("/v1/documents", headers=AUTH_A).json()["items"]
    kinds: dict[str, int] = {}
    for d in items:
        kinds[d["evidence_kind"]] = kinds.get(d["evidence_kind"], 0) + 1
    # The API returns them flat; the view derives Policies (2) · Procedures (1) · SOC Reports (1).
    assert kinds == {"policy": 2, "procedure": 1, "soc_report": 1}


# --- validation ---------------------------------------------------------------------------


def test_unknown_evidence_kind_is_rejected() -> None:
    resp = _upload(_client(), filename="x.txt", kind="not_a_kind", body=b"body")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "validation_error"


def test_empty_upload_is_projected_failed_not_ready() -> None:
    # An upload that yields no retrievable chunks is honest about it — status failed, still listed.
    resp = _upload(_client(), filename="empty.txt", kind="policy", body=b"")
    assert resp.status_code == 201
    assert resp.json()["status"] == "failed"


# --- tenant isolation (fail-closed) -------------------------------------------------------


def test_one_tenant_never_sees_anothers_documents() -> None:
    client = _client()
    up = _upload(
        client, filename="a-secret.txt", kind="policy", body=b"tenant a evidence", auth=AUTH_A
    )
    assert up.status_code == 201

    # tenant B lists — must be empty, never A's document
    b_items = client.get("/v1/documents", headers=AUTH_B).json()["items"]
    assert b_items == []
    # and A still sees its own
    a_items = client.get("/v1/documents", headers=AUTH_A).json()["items"]
    assert [d["filename"] for d in a_items] == ["a-secret.txt"]
