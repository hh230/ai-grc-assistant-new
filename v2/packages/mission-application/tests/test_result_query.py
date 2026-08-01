"""S3 read-side (Application): the builder registry routes by mission type, and ResultQuery enforces
found/completed — verified with fakes (no deliverables package, no HTTP). Proves *Result adapts to
the mission* and the 404 / 409 boundaries."""

from __future__ import annotations

from typing import Any

import pytest
from mission_application import (
    DeliverableBuilderRegistry,
    DeliverableNotReady,
    GenericContent,
    ResultContent,
    ResultQuery,
    ResultSectionView,
)
from mission_engine import Mission, Plan, PlanStep, StepResult
from pipeline_contracts import TenantContext

TENANT = TenantContext(tenant_id="T", principal_id="u")


class _FakeBuilder:
    """Returns content only (per ADR: the builder builds content, the query builds the view). The
    `tag` rides in a section heading so a test can tell which builder ran; two citations let a test
    check the query-assembled evidence count."""

    def __init__(self, tag: str) -> None:
        self.tag = tag

    def build_content(self, mission: Any) -> ResultContent:
        return GenericContent(
            sections=(
                ResultSectionView(heading=self.tag, body="b", citations=("doc-1", "doc-2")),
            )
        )


class _Store:
    def __init__(self, mission: Mission | None) -> None:
        self._mission = mission

    def get(self, mission_id: str, tenant: TenantContext) -> Any | None:
        if self._mission is None or mission_id != self._mission.id:
            return None
        return self._mission


class _ReadModel:
    def __init__(self, mission_type: str) -> None:
        self._type = mission_type

    def get(self, mission_id: str, tenant: TenantContext) -> Any:
        return type("Item", (), {"mission_type": self._type})()


def _completed() -> Mission:
    m = Mission.create(goal="g", tenant=TENANT)
    m.set_plan(Plan(steps=(PlanStep(description="Do", instruction="x"),)))
    m.begin_execution()
    m.record_step(StepResult(step_id="s1", output="done"))
    m.complete()
    return m


def _awaiting() -> Mission:
    m = Mission.create(goal="g", tenant=TENANT)
    m.set_plan(Plan(steps=(PlanStep(description="Do", instruction="x", consequential=True),)))
    m.begin_execution()
    m.await_approval()
    return m


# --- registry: Result adapts to the mission ---------------------------------------------


def test_registry_routes_by_type_with_a_default() -> None:
    generic, gap = _FakeBuilder("generic"), _FakeBuilder("gap")
    registry = DeliverableBuilderRegistry(default=generic, by_type={"gap_assessment": gap})
    mission = _completed()
    assert registry.for_mission(mission, "gap_assessment") is gap
    assert registry.for_mission(mission, "policy_generator") is generic  # falls back to default


def test_registry_register_adds_a_builder() -> None:
    generic = _FakeBuilder("generic")
    registry = DeliverableBuilderRegistry(default=generic)
    vendor = _FakeBuilder("vendor")
    registry.register("vendor_review", vendor)
    assert registry.for_mission(_completed(), "vendor_review") is vendor


# --- ResultQuery: found / completed / type-routed ---------------------------------------


def test_returns_result_built_by_the_type_specific_builder() -> None:
    mission = _completed()
    registry = DeliverableBuilderRegistry(
        default=_FakeBuilder("generic"), by_type={"gap_assessment": _FakeBuilder("gap")}
    )
    query = ResultQuery(_Store(mission), _ReadModel("gap_assessment"), registry)
    view = query.execute(mission.id, TENANT)
    assert view is not None
    assert view.content.sections[0].heading == "gap"  # the gap builder's content, not the default


def test_query_assembles_the_frame_around_the_builder_content() -> None:
    mission = _completed()
    registry = DeliverableBuilderRegistry(default=_FakeBuilder("generic"))
    view = ResultQuery(_Store(mission), _ReadModel(""), registry).execute(mission.id, TENANT)
    assert view is not None
    # The Trust Bar is the query's job, not the builder's: evidence counted from the content,
    # human-review from the mission, updated from the mission.
    assert view.trust.evidence_count == 2  # doc-1, doc-2 (deduplicated)
    assert view.trust.human_review == "Not required"  # no gate on this mission
    assert view.trust.updated_at == mission.updated_at


def test_missing_mission_returns_none() -> None:
    registry = DeliverableBuilderRegistry(default=_FakeBuilder("generic"))
    query = ResultQuery(_Store(None), _ReadModel(""), registry)
    assert query.execute("nope", TENANT) is None


def test_not_completed_raises_deliverable_not_ready() -> None:
    mission = _awaiting()
    registry = DeliverableBuilderRegistry(default=_FakeBuilder("generic"))
    query = ResultQuery(_Store(mission), _ReadModel("gap_assessment"), registry)
    with pytest.raises(DeliverableNotReady):
        query.execute(mission.id, TENANT)
