"""Repository round-trip: persist an aggregate, reload it, and assert state is preserved.

Covers a representative aggregate from each shape: a tenant root, a JSON-collection root, a
value-object-bearing root, a composite-key (framework) root, and the child-bearing Mission.
"""

from __future__ import annotations

from collections.abc import Callable

from grc_domain.frameworks.value_objects import FrameworkVersion
from grc_domain.knowledge.value_objects import KnowledgeScope
from grc_domain.policies.value_objects import PolicyBody
from grc_domain.risks.enums import RiskImpact, RiskLikelihood, RiskStatus
from grc_domain.shared.identifiers import (
    FrameworkId,
    KnowledgeSourceId,
    MissionId,
    OrganizationId,
    PolicyId,
    RiskId,
)
from grc_persistence import SqlAlchemyUnitOfWork

from ._builders import (
    make_framework,
    make_knowledge_source,
    make_mission,
    make_org,
    make_policy,
    make_risk,
    make_user,
)


async def test_organization_and_user_round_trip(
    uow_factory: Callable[[], SqlAlchemyUnitOfWork],
) -> None:
    async with (uow := uow_factory()):
        await uow.organizations.add(make_org())
        await uow.users.add(make_user())
        uow.collect_new_events()
        await uow.commit()

    async with (uow := uow_factory()):
        org = await uow.organizations.get(OrganizationId("org-1"))
        users = await uow.users.list_for_organization(OrganizationId("org-1"))

    assert org is not None
    assert org.name == "Acme"
    assert org.region.code == "sa"
    assert [str(u.id) for u in users] == ["user-1"]
    assert users[0].roles  # roles survived the JSON round-trip


async def test_policy_round_trip_preserves_value_objects(
    uow_factory: Callable[[], SqlAlchemyUnitOfWork],
) -> None:
    async with (uow := uow_factory()):
        await uow.organizations.add(make_org())
        await uow.policies.add(make_policy())
        uow.collect_new_events()
        await uow.commit()

    async with (uow := uow_factory()):
        policy = await uow.policies.get(OrganizationId("org-1"), PolicyId("pol-1"))

    assert policy is not None
    assert policy.body == PolicyBody("All staff must...")
    assert policy.version.number == 1
    assert len(policy.citations) == 1
    assert policy.citations[0].locator == "§1"


async def test_risk_update_round_trip(uow_factory: Callable[[], SqlAlchemyUnitOfWork]) -> None:
    async with (uow := uow_factory()):
        await uow.organizations.add(make_org())
        await uow.risks.add(make_risk())
        uow.collect_new_events()
        await uow.commit()

    async with (uow := uow_factory()):
        risk = await uow.risks.get(OrganizationId("org-1"), RiskId("risk-1"))
        assert risk is not None
        risk.assess(likelihood=RiskLikelihood.LIKELY, impact=RiskImpact.MAJOR)
        await uow.risks.save(risk)
        uow.collect_new_events()
        await uow.commit()

    async with (uow := uow_factory()):
        risk = await uow.risks.get(OrganizationId("org-1"), RiskId("risk-1"))

    assert risk is not None
    assert risk.status is RiskStatus.ASSESSED
    assert risk.score is not None
    assert risk.score.value == RiskLikelihood.LIKELY.value * RiskImpact.MAJOR.value


async def test_framework_composite_key_round_trip(
    uow_factory: Callable[[], SqlAlchemyUnitOfWork],
) -> None:
    async with (uow := uow_factory()):
        framework = make_framework()
        framework.publish()
        await uow.frameworks.add(framework)
        uow.collect_new_events()
        await uow.commit()

    async with (uow := uow_factory()):
        loaded = await uow.frameworks.get(
            FrameworkId("framework:iso_27001"), FrameworkVersion("2022")
        )
        published = await uow.frameworks.list_published()

    assert loaded is not None
    assert loaded.controls[0].code == "A.5.1"
    assert loaded.controls[0].requirements[0].text == "Define policies"
    assert [str(f.id) for f in published] == ["framework:iso_27001"]


async def test_mission_round_trip_with_children(
    uow_factory: Callable[[], SqlAlchemyUnitOfWork],
) -> None:
    async with (uow := uow_factory()):
        await uow.organizations.add(make_org())
        await uow.missions.add(make_mission())
        uow.collect_new_events()
        await uow.commit()

    async with (uow := uow_factory()):
        mission = await uow.missions.get(OrganizationId("org-1"), MissionId("mission-1"))

    assert mission is not None
    assert [str(step.id) for step in mission.steps] == ["step-a", "step-b"]
    assert mission.goal.statement == "Perform an ISO 27001 gap analysis"


async def test_knowledge_source_round_trip_global_and_org_scoped(
    uow_factory: Callable[[], SqlAlchemyUnitOfWork],
) -> None:
    async with (uow := uow_factory()):
        await uow.organizations.add(make_org("org-a"))
        await uow.knowledge_sources.add(make_knowledge_source("src-global"))
        await uow.knowledge_sources.add(
            make_knowledge_source(
                "src-org", scope=KnowledgeScope.for_organization(OrganizationId("org-a"))
            )
        )
        uow.collect_new_events()
        await uow.commit()

    async with (uow := uow_factory()):
        visible = await uow.knowledge_sources.list_for_organization(OrganizationId("org-a"))
        global_source = await uow.knowledge_sources.get(
            OrganizationId("org-a"), KnowledgeSourceId("src-global")
        )

    assert {str(s.id) for s in visible} == {"src-global", "src-org"}
    assert global_source is not None
    assert global_source.scope.is_global
    assert global_source.title.entries == (("en", "ISO/IEC 27001"), ("ar", "آيزو 27001"))
    assert global_source.tags == ("iso", "information-security")


async def test_knowledge_source_org_scoped_not_visible_to_other_org(
    uow_factory: Callable[[], SqlAlchemyUnitOfWork],
) -> None:
    async with (uow := uow_factory()):
        await uow.organizations.add(make_org("org-a"))
        await uow.organizations.add(make_org("org-b"))
        await uow.knowledge_sources.add(
            make_knowledge_source(
                "src-org", scope=KnowledgeScope.for_organization(OrganizationId("org-a"))
            )
        )
        uow.collect_new_events()
        await uow.commit()

    async with (uow := uow_factory()):
        own = await uow.knowledge_sources.get(OrganizationId("org-a"), KnowledgeSourceId("src-org"))
        cross = await uow.knowledge_sources.get(
            OrganizationId("org-b"), KnowledgeSourceId("src-org")
        )

    assert own is not None
    assert cross is None
