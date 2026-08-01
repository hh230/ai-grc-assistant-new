"""S1 write-side acceptance: a projected Mission appears in the read model with its product metadata
(type + scope) and its live status snapshot — and re-projecting on a transition updates the row in
place, tenant-scoped throughout."""

from __future__ import annotations

from mission_engine import Mission, single_step_plan
from mission_projection import MissionProjector
from mission_read_model import InMemoryMissionListReadModel
from pipeline_contracts import TenantContext


def tenant(tenant_id: str) -> TenantContext:
    return TenantContext(
        tenant_id=tenant_id, principal_id="user-1", roles=("practitioner",), region="ksa"
    )


def test_projects_a_created_mission_with_product_metadata() -> None:
    rm = InMemoryMissionListReadModel()
    projector = MissionProjector(rm)
    mission = Mission.create(goal="Gap on ISO A.8", tenant=tenant("T"))

    projector.project(mission, mission_type="gap_assessment", scope="Technological controls")

    page = rm.list_missions(tenant("T"))
    assert page.total == 1
    row = page.items[0]
    assert row.mission_id == mission.id
    assert row.mission_type == "gap_assessment"
    assert row.title == "Technological controls"
    assert row.status == "created"


def test_reprojecting_after_a_transition_updates_status_in_place() -> None:
    rm = InMemoryMissionListReadModel()
    projector = MissionProjector(rm)
    mission = Mission.create(goal="Gap", tenant=tenant("T"))
    projector.project(mission, mission_type="gap_assessment", scope="Scope")

    mission.set_plan(single_step_plan("do the thing"))  # CREATED → PLANNED
    projector.project(mission, mission_type="gap_assessment", scope="Scope")

    page = rm.list_missions(tenant("T"))
    assert page.total == 1  # upsert, not a duplicate
    assert page.items[0].status == "planned"


def test_projection_is_tenant_scoped() -> None:
    rm = InMemoryMissionListReadModel()
    projector = MissionProjector(rm)
    projector.project(
        Mission.create(goal="A", tenant=tenant("T")), mission_type="risk_assessment", scope="A"
    )
    projector.project(
        Mission.create(goal="B", tenant=tenant("T2")), mission_type="risk_assessment", scope="B"
    )

    assert rm.list_missions(tenant("T")).total == 1
    assert rm.list_missions(tenant("T2")).total == 1
    # and neither tenant sees the other's mission
    assert rm.list_missions(tenant("T")).items[0].title == "A"
    assert rm.list_missions(tenant("T2")).items[0].title == "B"
