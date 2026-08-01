"""Shared, database-free fixtures. Tenant and mission builders are pure, so the codec, schema,
SQL-construction, and purity suites run anywhere; the contract and integration suites add their
own DB-gated fixtures (which auto-skip without a reachable Postgres)."""

from __future__ import annotations

import pytest
from mission_engine import (
    EchoExecutor,
    InMemoryMissionStore,
    Mission,
    MissionEngine,
    Plan,
    PlanStep,
    StepResult,
)
from pipeline_contracts import TenantContext


@pytest.fixture
def tenant() -> TenantContext:
    return TenantContext(
        tenant_id="org_acme", principal_id="u_owner", roles=("owner", "admin"), region="ksa"
    )


@pytest.fixture
def other_tenant() -> TenantContext:
    return TenantContext(tenant_id="org_globex", principal_id="u_intruder")


@pytest.fixture
def simple_mission(tenant: TenantContext) -> Mission:
    """A completed `simple` mission, driven end-to-end through the reference adapters — the "even
    the simplest question is a Mission" path (one step, no gate, COMPLETED)."""
    engine = MissionEngine(InMemoryMissionStore(), EchoExecutor())
    return engine.run_simple("MFA lookup", tenant, "what does NCA ECC say about MFA?")


@pytest.fixture
def rich_mission(tenant: TenantContext) -> Mission:
    """A mission that exercises every field the codec must round-trip: a recorded step result with
    citations/confidence/cost/warnings, a human-gate pause + resume, and a re-plan — so the
    aggregate carries a *multi-version* plan history and a `composite` execution profile."""
    mission = Mission.create(
        goal="draft an access-control policy", tenant=tenant, idempotency_key="k-rich"
    )
    mission.set_plan(Plan(steps=(PlanStep(description="retrieve", instruction="find ECC MFA"),)))
    mission.begin_execution()
    mission.record_step(
        StepResult(
            step_id="stp_seed",
            ok=True,
            output="draft",
            citations=("nca_ecc:2-3-1",),
            confidence=0.87,
            source_ids=("src_1", "src_2"),
            latency_ms=42.5,
            estimated_cost=0.0031,
            warnings=("thin evidence",),
        )
    )
    mission.await_approval()  # pause before the (future) consequential step
    mission.resume()
    mission.replan(
        (
            PlanStep(description="author", instruction="write policy", consequential=True),
            PlanStep(description="review", instruction="check coverage"),
        )
    )
    return mission
