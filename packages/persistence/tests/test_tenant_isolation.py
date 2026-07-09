"""Tenant isolation: a tenant can never read or list another tenant's aggregates."""

from __future__ import annotations

from collections.abc import Callable

from grc_domain.shared.identifiers import ControlId, OrganizationId, WorkspaceId
from grc_persistence import SqlAlchemyUnitOfWork
from grc_persistence.models import OutboxMessageModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine

from ._builders import make_control, make_mission, make_org


async def test_cross_tenant_get_returns_none(
    uow_factory: Callable[[], SqlAlchemyUnitOfWork],
) -> None:
    async with (uow := uow_factory()):
        await uow.organizations.add(make_org("org-a"))
        await uow.organizations.add(make_org("org-b"))
        await uow.controls.add(make_control(org_id="org-a", control_id="ctl-a"))
        uow.collect_new_events()
        await uow.commit()

    async with (uow := uow_factory()):
        own = await uow.controls.get(OrganizationId("org-a"), ControlId("ctl-a"))
        cross = await uow.controls.get(OrganizationId("org-b"), ControlId("ctl-a"))

    assert own is not None
    assert cross is None


async def test_cross_tenant_list_is_empty(
    uow_factory: Callable[[], SqlAlchemyUnitOfWork],
) -> None:
    async with (uow := uow_factory()):
        await uow.organizations.add(make_org("org-a"))
        await uow.organizations.add(make_org("org-b"))
        await uow.missions.add(make_mission(org_id="org-a", mission_id="m-a"))
        uow.collect_new_events()
        await uow.commit()

    async with (uow := uow_factory()):
        own = await uow.missions.list_for_workspace(OrganizationId("org-a"), WorkspaceId("ws-1"))
        cross = await uow.missions.list_for_workspace(OrganizationId("org-b"), WorkspaceId("ws-1"))

    assert [str(m.id) for m in own] == ["m-a"]
    assert cross == []


async def test_outbox_rows_carry_owning_tenant(
    uow_factory: Callable[[], SqlAlchemyUnitOfWork], engine: AsyncEngine
) -> None:
    async with (uow := uow_factory()):
        await uow.organizations.add(make_org("org-a"))
        await uow.controls.add(make_control(org_id="org-a", control_id="ctl-a"))
        uow.collect_new_events()
        await uow.commit()

    async with engine.connect() as conn:
        rows = (
            await conn.execute(
                select(OutboxMessageModel.aggregate_type, OutboxMessageModel.organization_id)
            )
        ).all()

    # Every integration event is attributed to its owning tenant.
    assert {(t, o) for t, o in rows} == {("Organization", "org-a"), ("Control", "org-a")}
