"""Fixtures: a completed Gap Assessment mission driven through the real Mission Engine with a
scripted executor (so step results are exactly what a real gap run records), and the bundled
framework library. No LLM, no database."""

from __future__ import annotations

import pytest
from event_bus.bus import RecordingEventBus
from framework_library import FrameworkLibrary
from mission_engine import (
    InMemoryMissionStore,
    Mission,
    MissionEngine,
    Plan,
    PlanStep,
    StepRequest,
    StepResult,
)
from pipeline_contracts import TenantContext


class _ScriptedExecutor:
    """Returns a pre-scripted `(output, source_ids)` per step, in order — so a test controls exactly
    what each mission step records, without any tool/LLM."""

    def __init__(self, scripted: list[tuple[str, tuple[str, ...]]]) -> None:
        self._scripted = scripted
        self._index = 0

    def execute(self, request: StepRequest) -> StepResult:
        output, source_ids = self._scripted[self._index]
        self._index += 1
        return StepResult(step_id=request.step_id, ok=True, output=output, source_ids=source_ids)


@pytest.fixture
def tenant() -> TenantContext:
    return TenantContext(tenant_id="org_acme", principal_id="u1", roles=("analyst",))


@pytest.fixture
def library() -> FrameworkLibrary:
    return FrameworkLibrary.from_bundled()


@pytest.fixture
def gap_mission(tenant: TenantContext) -> Mission:
    """A completed gap-assessment mission: two ISO controls required, evidence that covers one of
    them (A.8.5 Secure authentication) but not the other (A.8.24 Use of cryptography)."""
    scripted = [
        # identify_controls → source_ids are control ids
        ("A.8.5 Secure authentication [Technological]\nA.8.24 Use of cryptography [Technological]",
         ("iso_27001:A.8.5", "iso_27001:A.8.24")),
        # gather_evidence → the customer's evidence mentions authentication, not cryptography
        ("Acme implements secure authentication with hardware keys; sessions are logged.",
         ("doc-acme-1",)),
        # compute_gap → the synthesis narrative
        ("Authentication is covered; cryptography has no supporting evidence.", ()),
    ]
    engine = MissionEngine(InMemoryMissionStore(), _ScriptedExecutor(scripted),
                           events=RecordingEventBus())
    mission = engine.create("gap assessment: Technological", tenant)
    engine.plan(
        mission,
        Plan(steps=(
            PlanStep(description="identify_controls", instruction="Technological"),
            PlanStep(description="gather_evidence", instruction="Technological evidence"),
            PlanStep(description="compute_gap", instruction="compute the gap"),
        )),
    )
    engine.execute(mission)
    return mission
