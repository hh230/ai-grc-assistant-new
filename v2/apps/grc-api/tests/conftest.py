"""Test wiring: an app whose read model is seeded with two tenants' missions.

`tenant-a` (token `dev-tenant-a`) has 3 missions; `tenant-b` (token `dev-tenant-b`) has 2. This lets
the HTTP tests prove fail-closed isolation end-to-end: a token for A never surfaces B's missions.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from grc_api.app import create_app
from grc_api.composition import Storage
from mission_read_model import InMemoryMissionListReadModel, MissionListItem

# (mission_id, tenant_id, mission_type, title, status, created_at, updated_at)
_SEED = [
    ("m1", "tenant-a", "gap_assessment", "Technological", "executing", 100.0, 300.0),
    ("m2", "tenant-a", "risk_assessment", "Customer DB", "completed", 100.0, 200.0),
    ("m3", "tenant-a", "vendor_review", "Acme Cloud", "awaiting_approval", 100.0, 100.0),
    ("x1", "tenant-b", "gap_assessment", "Organizational", "executing", 100.0, 100.0),
    ("x2", "tenant-b", "policy_generator", "AUP", "completed", 100.0, 150.0),
]


def _seed() -> InMemoryMissionListReadModel:
    rm = InMemoryMissionListReadModel()
    for row in _SEED:
        rm.record(MissionListItem(*row))
    return rm


@pytest.fixture
def client() -> TestClient:
    # This suite declares its environment: `storage=MEMORY`. The host is durable by default, so an
    # in-memory suite says so rather than inheriting it — which is why a new test cannot fall into
    # an assumption it never made. `tests/production` is the suite that speaks to PostgreSQL.
    return TestClient(create_app(storage=Storage.MEMORY, read_model=_seed()))


AUTH_A = {"Authorization": "Bearer dev-tenant-a"}
AUTH_B = {"Authorization": "Bearer dev-tenant-b"}
