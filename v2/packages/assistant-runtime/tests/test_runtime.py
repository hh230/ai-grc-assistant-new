"""Tests #1, #2, #4 — the thin `AssistantRuntime.handle` over an in-memory Core (no DB).

Proves: a recognized request → the right capability → a Mission (#1); an unrecognized request →
`simple_question` (#2); and `handle` calls the Core **exactly once** (#4).
"""

from __future__ import annotations

from assistant_runtime import (
    AssistantRuntime,
    CapabilityCatalog,
    KeywordIntentRecognizer,
    MissionCatalog,
)
from mission_engine import MissionStatus
from pipeline_contracts import TenantContext

from tests.conftest import SpyMissionDriver


def _runtime(
    driver: SpyMissionDriver,
    capability_catalog: CapabilityCatalog,
    mission_catalog: MissionCatalog,
    intent: KeywordIntentRecognizer,
) -> AssistantRuntime:
    return AssistantRuntime(
        missions=driver,
        capabilities=capability_catalog,
        mission_catalog=mission_catalog,
        intent=intent,
    )


# ── #1 — one capability → one mission ─────────────────────────────────────────
def test_recognized_request_runs_the_right_mission(
    spy_driver: SpyMissionDriver,
    capability_catalog: CapabilityCatalog,
    mission_catalog: MissionCatalog,
    intent: KeywordIntentRecognizer,
    tenant: TenantContext,
) -> None:
    runtime = _runtime(spy_driver, capability_catalog, mission_catalog, intent)

    response = runtime.handle("please assess this vendor", tenant)

    assert response.capability_id == "vendor_risk_assessment"
    assert response.status is MissionStatus.COMPLETED  # driven end-to-end via the (in-memory) Core
    assert len(response.mission.step_results) == 4  # the vendor plan's four steps ran
    assert response.mission_id  # a real mission was created


# ── #2 — unknown capability → simple_question ─────────────────────────────────
def test_unrecognized_request_falls_back_to_simple_question(
    spy_driver: SpyMissionDriver,
    capability_catalog: CapabilityCatalog,
    mission_catalog: MissionCatalog,
    intent: KeywordIntentRecognizer,
    tenant: TenantContext,
) -> None:
    runtime = _runtime(spy_driver, capability_catalog, mission_catalog, intent)

    response = runtime.handle("hello, how are you?", tenant)  # no "vendor" keyword

    assert response.capability_id == "simple_question"
    assert response.status is MissionStatus.COMPLETED
    assert len(response.mission.step_results) == 1  # the single-step question plan


# ── #4 — handle calls the Core exactly once ───────────────────────────────────
def test_handle_calls_mission_runtime_exactly_once(
    spy_driver: SpyMissionDriver,
    capability_catalog: CapabilityCatalog,
    mission_catalog: MissionCatalog,
    intent: KeywordIntentRecognizer,
    tenant: TenantContext,
) -> None:
    runtime = _runtime(spy_driver, capability_catalog, mission_catalog, intent)
    runtime.handle("assess this vendor", tenant)
    assert spy_driver.calls == 1  # exactly one run_transition — no hidden extra Core calls
