"""Shared fixtures for the assistant-runtime suite.

The **demo capabilities and Mission types live here, in the tests — not in the package** (Slice 2
ships the *mechanism*, not GRC capabilities). The plan factories build plan *structure* only; the
steps are run by the reference `EchoExecutor` behind the injected Core. A `SpyMissionDriver` runs
transitions against an in-memory Core and counts calls, so most tests need no database.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, TypeVar

import pytest
from assistant_runtime import (
    Capability,
    CapabilityCatalog,
    KeywordIntentRecognizer,
    MissionCatalog,
    MissionType,
)
from mission_engine import (
    EchoExecutor,
    InMemoryMissionStore,
    Mission,
    MissionEngine,
    Plan,
    PlanStep,
    single_step_plan,
)
from pipeline_contracts import TenantContext

T = TypeVar("T")


# ── demo plan factories (structure only; no tools, no real GRC work) ──────────────────────
def simple_question_plan(inputs: Mapping[str, Any], tenant: TenantContext) -> tuple[str, Plan]:
    request = str(inputs.get("request", "")) or "answer the question"
    return request, single_step_plan(request, description="simple question")


def vendor_risk_plan(inputs: Mapping[str, Any], tenant: TenantContext) -> tuple[str, Plan]:
    request = str(inputs.get("request", ""))
    goal = f"vendor risk assessment: {request}".strip()
    plan = Plan(
        steps=(
            PlanStep(description="collect evidence", instruction="collect vendor evidence"),
            PlanStep(description="analyze", instruction="analyze evidence"),
            PlanStep(description="score", instruction="score risk"),
            PlanStep(description="report", instruction="draft report"),
        )
    )
    return goal, plan


# ── catalogs + intent ─────────────────────────────────────────────────────────────────────
@pytest.fixture
def tenant() -> TenantContext:
    return TenantContext(tenant_id="org_acme", principal_id="u_owner", roles=("owner",))


@pytest.fixture
def mission_catalog() -> MissionCatalog:
    return MissionCatalog(
        [
            MissionType(id="simple_question", plan_factory=simple_question_plan),
            MissionType(id="vendor_risk_assessment", plan_factory=vendor_risk_plan),
        ]
    )


@pytest.fixture
def capability_catalog() -> CapabilityCatalog:
    return CapabilityCatalog(
        [
            Capability(
                id="simple_question",
                name="Ask",
                description="answer a general question",
                resolver="simple_question",
            ),
            Capability(
                id="vendor_risk_assessment",
                name="Vendor Risk Assessment",
                description="assess a vendor's risk",
                input_schema=("request",),
                resolver="vendor_risk_assessment",
            ),
        ]
    )


@pytest.fixture
def intent() -> KeywordIntentRecognizer:
    # "vendor" in the request → the vendor capability; anything else → no candidate → fallback.
    return KeywordIntentRecognizer({"vendor": "vendor_risk_assessment"})


# ── a MissionDriver that runs in-memory and counts calls (no DB) ────────────────────────────
class SpyMissionDriver:
    """Satisfies the `MissionDriver` port by running each transition against an in-memory Core, and
    records how many times `run_transition` was called — the proof for 'handle calls the Core
    exactly once'."""

    def __init__(self) -> None:
        self.calls = 0
        self._engine = MissionEngine(InMemoryMissionStore(), EchoExecutor())

    def run_transition(self, apply: Callable[[MissionEngine], T]) -> T:
        self.calls += 1
        return apply(self._engine)


@pytest.fixture
def spy_driver() -> SpyMissionDriver:
    return SpyMissionDriver()


# expose the demo mission used for assertions elsewhere
__all__ = ["SpyMissionDriver", "simple_question_plan", "vendor_risk_plan", "Mission"]
