"""Test #6 — end to end against the **real** `MissionRuntime` (mission-integration) on real
PostgreSQL: `AssistantRuntime.handle` turns a request into a durably persisted, driven Mission.
DB-gated; auto-skips without a database, like the Core integration suites.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest

psycopg = pytest.importorskip("psycopg")

from assistant_runtime import (  # noqa: E402
    AssistantRuntime,
    CapabilityCatalog,
    KeywordIntentRecognizer,
    MissionCatalog,
    build_assistant,
)
from mission_engine import MissionStatus  # noqa: E402
from mission_integration import MissionRuntime  # noqa: E402
from mission_store.config import dsn as default_dsn  # noqa: E402
from mission_store.outbox_schema import apply_outbox_schema  # noqa: E402
from mission_store.schema import apply_schema  # noqa: E402
from pipeline_contracts import TenantContext  # noqa: E402


def _connect(*, autocommit: bool = True) -> psycopg.Connection:
    try:
        return psycopg.connect(default_dsn(), connect_timeout=3, autocommit=autocommit)
    except Exception as exc:  # noqa: BLE001 - any connect failure means "no DB": skip
        pytest.skip(f"no reachable PostgreSQL ({exc})")


@pytest.fixture
def observer() -> Iterator[psycopg.Connection]:
    conn = _connect()
    yield conn
    conn.close()


@pytest.fixture
def real_runtime(observer: psycopg.Connection) -> Iterator[MissionRuntime]:
    suffix = uuid.uuid4().hex[:8]
    missions_table = f"missions_ar_{suffix}"
    outbox_table = f"outbox_ar_{suffix}"
    apply_schema(observer, missions_table)
    apply_outbox_schema(observer, outbox_table)
    yield MissionRuntime(missions_table=missions_table, outbox_table=outbox_table)
    observer.execute(f"DROP TABLE IF EXISTS {missions_table}")
    observer.execute(f"DROP TABLE IF EXISTS {outbox_table}")


def test_handle_drives_a_real_mission_end_to_end(
    real_runtime: MissionRuntime,
    capability_catalog: CapabilityCatalog,
    mission_catalog: MissionCatalog,
    intent: KeywordIntentRecognizer,
    tenant: TenantContext,
) -> None:
    assistant = AssistantRuntime(
        missions=real_runtime,
        capabilities=capability_catalog,
        mission_catalog=mission_catalog,
        intent=intent,
    )

    response = assistant.handle("please assess this vendor", tenant)

    assert response.capability_id == "vendor_risk_assessment"
    assert response.status is MissionStatus.COMPLETED

    # durably persisted in the Mission Store — reload it through the real runtime
    reloaded = real_runtime.load(response.mission_id, tenant)
    assert reloaded is not None
    assert reloaded.status is MissionStatus.COMPLETED
    assert len(reloaded.step_results) == 4


def test_unknown_request_runs_a_simple_question_mission_e2e(
    real_runtime: MissionRuntime,
    capability_catalog: CapabilityCatalog,
    mission_catalog: MissionCatalog,
    intent: KeywordIntentRecognizer,
    tenant: TenantContext,
) -> None:
    assistant = AssistantRuntime(
        missions=real_runtime,
        capabilities=capability_catalog,
        mission_catalog=mission_catalog,
        intent=intent,
    )

    response = assistant.handle("what does NCA ECC say about MFA?", tenant)

    assert response.capability_id == "simple_question"
    reloaded = real_runtime.load(response.mission_id, tenant)
    assert reloaded is not None
    assert reloaded.status is MissionStatus.COMPLETED
    assert len(reloaded.step_results) == 1


# ── Slice 3: the first built-in capability, full loop on real PostgreSQL ───────
def test_first_capability_full_loop_e2e(
    real_runtime: MissionRuntime, tenant: TenantContext
) -> None:
    """The Slice-3 proof: `build_assistant` over the real `MissionRuntime` answers any request as a
    Simple Question, driven end to end and durably persisted — the full loop
    User → AssistantRuntime → Capability (ask) → Mission → MissionRuntime → Response."""
    assistant = build_assistant(real_runtime)

    response = assistant.handle("what does NCA ECC say about MFA?", tenant)

    assert response.capability_id == "ask"
    assert response.status is MissionStatus.COMPLETED

    reloaded = real_runtime.load(response.mission_id, tenant)
    assert reloaded is not None
    assert reloaded.status is MissionStatus.COMPLETED
    assert len(reloaded.step_results) == 1
    assert reloaded.step_results[0].output.startswith("echo:")  # ran through the Core executor


# ── ADR 0047: Risk Assessment (first composite capability), full loop on real PostgreSQL ──
def test_risk_assessment_composite_mission_e2e(
    real_runtime: MissionRuntime, tenant: TenantContext
) -> None:
    """The Slice-1b proof: a request with the `risk` intent runs a **composite** (3-step) Mission
    end to end, durably persisted — the Assistant drives more than a single question."""
    assistant = build_assistant(real_runtime)

    response = assistant.handle("assess the risk of vendor X", tenant)

    assert response.capability_id == "risk_assessment"
    assert response.status is MissionStatus.COMPLETED

    reloaded = real_runtime.load(response.mission_id, tenant)
    assert reloaded is not None
    assert reloaded.status is MissionStatus.COMPLETED
    assert len(reloaded.step_results) == 3  # collect_context → assess_risk → generate_report
