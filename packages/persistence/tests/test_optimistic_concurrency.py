"""Optimistic concurrency: two units of work that load the same aggregate and both write
must not both succeed — the later commit raises ``ConcurrencyError``.

This exercises the full path: the ``version_id_col`` guard on the ORM row, the repository
pinning the loaded row so its version stays authoritative, and the Unit of Work translating
SQLAlchemy's ``StaleDataError`` into the application's ``ConcurrencyError``.
"""

from __future__ import annotations

import pytest
from grc_domain.risks.enums import RiskImpact, RiskLikelihood
from grc_domain.shared.identifiers import MissionId, OrganizationId, RiskId
from grc_services.shared.exceptions import ConcurrencyError

from ._builders import make_mission, make_org, make_risk


async def test_concurrent_writes_conflict(uow_factory) -> None:
    async with (uow := uow_factory()):
        await uow.organizations.add(make_org())
        await uow.risks.add(make_risk())
        uow.collect_new_events()
        await uow.commit()

    first, second = uow_factory(), uow_factory()
    await first.begin()
    await second.begin()

    risk_a = await first.risks.get(OrganizationId("org-1"), RiskId("risk-1"))
    risk_b = await second.risks.get(OrganizationId("org-1"), RiskId("risk-1"))

    # Client A commits first.
    risk_a.assess(likelihood=RiskLikelihood.LIKELY, impact=RiskImpact.MAJOR)
    await first.risks.save(risk_a)
    first.collect_new_events()
    await first.commit()

    # Client B worked from the now-stale version: its commit must be rejected.
    risk_b.assess(likelihood=RiskLikelihood.RARE, impact=RiskImpact.MINOR)
    await second.risks.save(risk_b)
    second.collect_new_events()
    with pytest.raises(ConcurrencyError):
        await second.commit()


async def test_conflict_leaves_first_writers_state(uow_factory) -> None:
    async with (uow := uow_factory()):
        await uow.organizations.add(make_org())
        await uow.risks.add(make_risk())
        uow.collect_new_events()
        await uow.commit()

    first, second = uow_factory(), uow_factory()
    await first.begin()
    await second.begin()
    a = await first.risks.get(OrganizationId("org-1"), RiskId("risk-1"))
    b = await second.risks.get(OrganizationId("org-1"), RiskId("risk-1"))

    a.assess(likelihood=RiskLikelihood.ALMOST_CERTAIN, impact=RiskImpact.SEVERE)
    await first.risks.save(a)
    first.collect_new_events()
    await first.commit()

    b.assess(likelihood=RiskLikelihood.RARE, impact=RiskImpact.NEGLIGIBLE)
    await second.risks.save(b)
    second.collect_new_events()
    with pytest.raises(ConcurrencyError):
        await second.commit()

    async with (uow := uow_factory()):
        risk = await uow.risks.get(OrganizationId("org-1"), RiskId("risk-1"))
    # The winner's assessment survives; the loser's was rolled back.
    assert risk.score.value == RiskLikelihood.ALMOST_CERTAIN.value * RiskImpact.SEVERE.value


async def test_concurrent_mission_writes_conflict(uow_factory) -> None:
    async with (uow := uow_factory()):
        await uow.organizations.add(make_org())
        await uow.missions.add(make_mission(step_ids=("step-a",)))
        uow.collect_new_events()
        await uow.commit()

    first, second = uow_factory(), uow_factory()
    await first.begin()
    await second.begin()
    m_a = await first.missions.get(OrganizationId("org-1"), MissionId("mission-1"))
    m_b = await second.missions.get(OrganizationId("org-1"), MissionId("mission-1"))

    m_a.start()
    await first.missions.save(m_a)
    first.collect_new_events()
    await first.commit()

    m_b.start()
    await second.missions.save(m_b)
    second.collect_new_events()
    with pytest.raises(ConcurrencyError):
        await second.commit()
