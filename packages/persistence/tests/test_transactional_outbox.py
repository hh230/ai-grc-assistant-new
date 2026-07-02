"""Transactional outbox: domain events become outbox rows, atomically with the state change.

The outbox is the single source of integration events, so the assertions check that events
are captured, attributed, left unpublished, and — critically — written in the *same*
transaction as the aggregate change (a rejected commit leaves no outbox rows behind).
"""

from __future__ import annotations

import pytest
from grc_domain.risks.enums import RiskImpact, RiskLikelihood
from grc_domain.shared.identifiers import OrganizationId, RiskId
from grc_persistence.models import OutboxMessageModel
from grc_services.shared.exceptions import ConcurrencyError
from sqlalchemy import func, select

from ._builders import make_mission, make_org, make_risk


async def _outbox(engine):
    async with engine.connect() as conn:
        return (await conn.execute(select(OutboxMessageModel))).mappings().all()


async def test_events_are_captured_as_outbox_rows(uow_factory, engine) -> None:
    async with (uow := uow_factory()):
        await uow.organizations.add(make_org())
        await uow.missions.add(make_mission(step_ids=("step-a",)))
        uow.collect_new_events()
        await uow.commit()

    rows = await _outbox(engine)
    by_type = {row["event_type"]: row for row in rows}

    assert set(by_type) == {"OrganizationRegistered", "MissionCreated", "MissionPlanned"}
    created = by_type["MissionCreated"]
    assert created["aggregate_type"] == "Mission"
    assert created["aggregate_id"] == "mission-1"
    assert created["organization_id"] == "org-1"
    assert created["payload"]["goal"] == "Perform an ISO 27001 gap analysis"
    assert created["payload"]["workspace_id"] == "ws-1"


async def test_new_outbox_rows_are_unpublished(uow_factory, engine) -> None:
    async with (uow := uow_factory()):
        await uow.organizations.add(make_org())
        uow.collect_new_events()
        await uow.commit()

    rows = await _outbox(engine)
    assert rows
    assert all(row["published_at"] is None for row in rows)


async def test_rejected_commit_writes_no_outbox_rows(uow_factory, engine) -> None:
    async with (uow := uow_factory()):
        await uow.organizations.add(make_org())
        await uow.risks.add(make_risk())
        uow.collect_new_events()
        await uow.commit()

    baseline = len(await _outbox(engine))

    # Force an optimistic-concurrency conflict on the losing unit of work.
    first, second = uow_factory(), uow_factory()
    await first.begin()
    await second.begin()
    a = await first.risks.get(OrganizationId("org-1"), RiskId("risk-1"))
    b = await second.risks.get(OrganizationId("org-1"), RiskId("risk-1"))

    a.assess(likelihood=RiskLikelihood.LIKELY, impact=RiskImpact.MAJOR)
    await first.risks.save(a)
    first.collect_new_events()
    await first.commit()  # writes one RiskAssessed outbox row

    b.assess(likelihood=RiskLikelihood.RARE, impact=RiskImpact.MINOR)
    await second.risks.save(b)
    second.collect_new_events()
    with pytest.raises(ConcurrencyError):
        await second.commit()  # rolled back: must leave no outbox row

    rows = await _outbox(engine)
    assert len(rows) == baseline + 1  # only client A's event was persisted
    assert sum(1 for r in rows if r["event_type"] == "RiskAssessed") == 1


async def test_outbox_count_matches_collected_events(uow_factory, engine) -> None:
    async with (uow := uow_factory()):
        await uow.organizations.add(make_org())
        recorded = uow.collect_new_events()
        await uow.commit()

    async with engine.connect() as conn:
        count = await conn.scalar(select(func.count()).select_from(OutboxMessageModel))

    assert count == len(recorded) == 1
