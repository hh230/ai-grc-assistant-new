from __future__ import annotations

import pytest
from assistant_runtime.intent import CapabilityIntent
from devteam_contracts import platform_tenant
from devteam_intake import (
    CIFailureSource,
    CorrelationDeactivator,
    CorrelationRepository,
    CreateMission,
    IntakeSignal,
    ManualRequestSource,
    StoreMissionCorrelator,
    UpdateMission,
)
from mission_engine.events import MissionCompleted, MissionStepCompleted


def _signal(ref: str) -> IntakeSignal:
    return IntakeSignal(
        tenant=platform_tenant(),
        intent=CapabilityIntent(capability_id="quality_review", inputs={}),
        correlation_ref=ref,
    )


def test_signal_requires_a_correlation_ref() -> None:
    with pytest.raises(ValueError):
        _signal("  ")


def test_index_registers_finds_and_deactivates_tenant_scoped() -> None:
    index = CorrelationRepository()
    tenant = platform_tenant()
    assert index.find_active(tenant, "ci:pipeline:api") is None
    index.register(tenant, "ci:pipeline:api", "m1")
    assert index.find_active(tenant, "ci:pipeline:api") == "m1"
    index.deactivate(tenant, "m1")
    assert index.find_active(tenant, "ci:pipeline:api") is None


def test_correlator_creates_when_no_active_mission() -> None:
    correlator = StoreMissionCorrelator(CorrelationRepository())
    command = correlator.correlate(_signal("ci:pipeline:api"))
    assert isinstance(command, CreateMission)


def test_correlator_updates_when_a_mission_is_active() -> None:
    index = CorrelationRepository()
    index.register(platform_tenant(), "ci:pipeline:api", "m1")
    command = StoreMissionCorrelator(index).correlate(_signal("ci:pipeline:api"))
    assert isinstance(command, UpdateMission)
    assert command.mission_id == "m1"


def test_deactivator_frees_the_entry_on_a_terminal_event_only() -> None:
    index = CorrelationRepository()
    tenant = platform_tenant()
    index.register(tenant, "ci:pipeline:api", "m1")
    deactivator = CorrelationDeactivator(index)

    deactivator.handle(MissionStepCompleted(trace_id="t", tenant_id="platform", mission_id="m1"))
    assert index.find_active(tenant, "ci:pipeline:api") == "m1"  # non-terminal: still active

    deactivator.handle(MissionCompleted(trace_id="t", tenant_id="platform", mission_id="m1"))
    assert index.find_active(tenant, "ci:pipeline:api") is None  # terminal: freed


def test_ci_failure_source_normalizes_per_pipeline_with_a_finding() -> None:
    signal = CIFailureSource().normalize({"pipeline": "api", "detail": "pytest failed"})
    assert signal.correlation_ref == "ci:pipeline:api"  # per-pipeline: reruns correlate
    assert signal.origin == "ci"
    assert signal.findings[0].kind == "ci_failure"


def test_manual_source_normalizes_per_request() -> None:
    signal = ManualRequestSource().normalize({"request": "look into flaky tests"})
    assert signal.correlation_ref == "manual:look into flaky tests"
    assert signal.intent.capability_id == "quality_review"
