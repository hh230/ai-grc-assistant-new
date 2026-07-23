"""The Wave 1 exit criterion, expressed as a test.

> *No production path depends on the Development Composition.*
> — MIGRATION_ASSESSMENT.md, Exit Criterion

Every other test in this suite composes the durable adapters **itself**, by injection. That proves
the adapters work through the host; it does not prove the host *uses* them. This file closes that
gap: it asks what `create_app()` builds when nobody hands it anything — which is what a deployment
gets.

It **fails on arrival**, by construction: the defaults are still `InMemoryMissionStore`,
`InMemory*ReadModel`, `EchoExecutor`, and the seeded development identity provider. It is the
**last** test in Wave 1 to go green, and when it does, Wave 1 is over.

No database is needed here — this inspects composition, not behaviour.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from document_read_model import InMemoryDocumentReadModel
from fastapi.testclient import TestClient
from grc_api.app import create_app
from grc_api.security import DevelopmentIdentityProvider
from mission_engine import InMemoryMissionStore
from mission_read_model import InMemoryMissionListReadModel

from tests.production.conftest import AUTH_A

pytestmark = pytest.mark.xfail(
    reason="Wave 1 in progress: the default composition is still the Development Composition. "
    "This is the exit criterion — when it passes, Wave 1 is complete.",
    strict=True,
)


def _state() -> Any:
    """The object graph a deployment gets: `create_app()` with nothing injected."""
    return create_app().state


def test_the_default_store_is_durable() -> None:
    assert not isinstance(_state().mission_store, InMemoryMissionStore), (
        "the default mission store is still in-memory — every mission dies with the process"
    )


def test_the_default_mission_read_model_is_durable() -> None:
    assert not isinstance(_state().mission_read_model, InMemoryMissionListReadModel)


def test_the_default_document_read_model_is_durable() -> None:
    assert not isinstance(_state().document_read_model, InMemoryDocumentReadModel)


def test_the_default_composition_does_not_echo() -> None:
    """The executor criterion, asserted as **behaviour** rather than by inspecting the engine.

    An earlier version of this test read `engine._executor` and compared its type — which would have
    made a private attribute name part of the contract, and would break the day the engine composed
    its executor differently. What actually matters is not which class is wired; it is that a
    finished mission contains real work. `EchoExecutor` returns `f"echo: {instruction}"`, so a
    product shipping it produces missions that look complete and contain nothing
    (MIGRATION_ASSESSMENT R1). Any executor that does real work passes; only an echo fails.
    """
    client = TestClient(create_app())
    created = client.post(
        "/v1/missions",
        json={"type": "gap_assessment", "scope": "Technological controls", "document_ids": []},
        headers={**AUTH_A, "Idempotency-Key": uuid.uuid4().hex},
    )
    assert created.status_code == 201, created.text
    mission_id = created.json()["mission"]["id"]
    assert client.post(f"/v1/missions/{mission_id}/run", headers=AUTH_A).status_code == 200

    detail = client.get(f"/v1/missions/{mission_id}", headers=AUTH_A)
    assert detail.status_code == 200, detail.text
    summaries = [finding["summary"] for finding in detail.json()["findings"]]

    assert summaries, "the mission ran but produced nothing at all"
    echoes = [text for text in summaries if text.strip().lower().startswith("echo:")]
    assert not echoes, (
        f"the default composition echoes its instructions instead of doing work: {echoes[0]!r}"
    )


def test_the_default_identity_provider_is_not_the_seeded_one() -> None:
    """A hardcoded credential map reaching a deployment authenticates every visitor as a seeded
    principal (MIGRATION_ASSESSMENT R4)."""
    assert not isinstance(_state().identity_provider, DevelopmentIdentityProvider)
