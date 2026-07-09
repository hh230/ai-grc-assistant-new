"""Diff-based child synchronization keyed on stable identifiers.

The Mission aggregate owns ordered child collections (steps, approval gates). On save the
repository must add new children, update changed ones, remove dropped ones, and preserve
ordering — all keyed on the children's stable ids.
"""

from __future__ import annotations

from collections.abc import Callable

from grc_domain.missions.enums import MissionStepStatus
from grc_domain.missions.value_objects import ProposedAction
from grc_domain.shared.identifiers import (
    ApprovalGateId,
    MissionId,
    MissionStepId,
    OrganizationId,
)
from grc_persistence import SqlAlchemyUnitOfWork

from ._builders import make_mission, make_org

ORG = OrganizationId("org-1")
MISSION = MissionId("mission-1")


async def _seed(
    uow_factory: Callable[[], SqlAlchemyUnitOfWork],
    step_ids: tuple[str, ...] = ("step-a", "step-b", "step-c"),
) -> None:
    async with (uow := uow_factory()):
        await uow.organizations.add(make_org())
        await uow.missions.add(make_mission(step_ids=step_ids))
        uow.collect_new_events()
        await uow.commit()


async def test_add_update_remove_children(uow_factory: Callable[[], SqlAlchemyUnitOfWork]) -> None:
    await _seed(uow_factory)

    async with (uow := uow_factory()):
        mission = await uow.missions.get(ORG, MISSION)
        assert mission is not None
        mission.start()
        mission.start_step(MissionStepId("step-a"))  # update an existing child
        # Drop step-c (exercise the remove branch of the diff).
        mission.steps = [s for s in mission.steps if str(s.id) != "step-c"]
        # Add a new child (an approval gate).
        mission.request_approval(
            step_id=MissionStepId("step-b"),
            gate_id=ApprovalGateId("gate-1"),
            proposed_action=ProposedAction(description="Apply remediation"),
        )
        await uow.missions.save(mission)
        uow.collect_new_events()
        await uow.commit()

    async with (uow := uow_factory()):
        mission = await uow.missions.get(ORG, MISSION)
        assert mission is not None

    step_ids = [str(s.id) for s in mission.steps]
    assert step_ids == ["step-a", "step-b"]  # step-c removed, order preserved
    statuses = {str(s.id): s.status for s in mission.steps}
    assert statuses["step-a"] is MissionStepStatus.RUNNING  # updated
    assert statuses["step-b"] is MissionStepStatus.AWAITING_APPROVAL
    assert [str(g.id) for g in mission.approval_gates] == ["gate-1"]  # added
    assert str(mission.approval_gates[0].step_id) == "step-b"


async def test_child_ordering_is_preserved_on_reorder(
    uow_factory: Callable[[], SqlAlchemyUnitOfWork],
) -> None:
    await _seed(uow_factory, step_ids=("step-a", "step-b", "step-c"))

    async with (uow := uow_factory()):
        mission = await uow.missions.get(ORG, MISSION)
        assert mission is not None
        # Reverse the plan order; the repository must persist the new positions.
        mission.steps = list(reversed(mission.steps))
        await uow.missions.save(mission)
        uow.collect_new_events()
        await uow.commit()

    async with (uow := uow_factory()):
        mission = await uow.missions.get(ORG, MISSION)
        assert mission is not None

    assert [str(s.id) for s in mission.steps] == ["step-c", "step-b", "step-a"]


async def test_repeated_save_is_idempotent(uow_factory: Callable[[], SqlAlchemyUnitOfWork]) -> None:
    await _seed(uow_factory, step_ids=("step-a", "step-b"))

    async with (uow := uow_factory()):
        mission = await uow.missions.get(ORG, MISSION)
        assert mission is not None
        await uow.missions.save(mission)  # no changes
        uow.collect_new_events()
        await uow.commit()

    async with (uow := uow_factory()):
        mission = await uow.missions.get(ORG, MISSION)
        assert mission is not None

    assert [str(s.id) for s in mission.steps] == ["step-a", "step-b"]
