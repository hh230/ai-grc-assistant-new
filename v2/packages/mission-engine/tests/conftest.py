"""Shared fixtures. The engine is wired against the reference adapters and a recording bus,
so tests exercise real port implementations (not mocks) while asserting on captured events."""

import pytest
from event_bus.bus import RecordingEventBus
from mission_engine import EchoExecutor, InMemoryMissionStore, MissionEngine
from pipeline_contracts import TenantContext


@pytest.fixture
def tenant() -> TenantContext:
    return TenantContext(tenant_id="org_acme", principal_id="u_owner", roles=("owner",))


@pytest.fixture
def other_tenant() -> TenantContext:
    return TenantContext(tenant_id="org_globex", principal_id="u_intruder")


@pytest.fixture
def bus() -> RecordingEventBus:
    return RecordingEventBus()


@pytest.fixture
def store() -> InMemoryMissionStore:
    return InMemoryMissionStore()


@pytest.fixture
def executor() -> EchoExecutor:
    return EchoExecutor()


@pytest.fixture
def engine(store, executor, bus) -> MissionEngine:
    return MissionEngine(store, executor, events=bus)
