"""Small domain-object builders shared across the persistence tests."""

from __future__ import annotations

from grc_domain.controls.entities import Control
from grc_domain.frameworks.entities import Framework
from grc_domain.frameworks.value_objects import FrameworkControl, FrameworkVersion, Requirement
from grc_domain.knowledge.entities import KnowledgeSource
from grc_domain.knowledge.enums import DocumentType, KnowledgeDomain
from grc_domain.knowledge.value_objects import KnowledgeScope, LocalizedText
from grc_domain.missions.entities import Mission, MissionStep
from grc_domain.missions.value_objects import MissionGoal
from grc_domain.policies.entities import Policy
from grc_domain.policies.value_objects import PolicyBody
from grc_domain.risks.entities import Risk
from grc_domain.shared.identifiers import (
    ControlId,
    FrameworkControlId,
    FrameworkId,
    KnowledgeSourceId,
    MissionId,
    MissionStepId,
    OrganizationId,
    PolicyId,
    RiskId,
    UserId,
    WorkspaceId,
)
from grc_domain.shared.value_objects import Citation
from grc_domain.tenancy.entities import Organization, User
from grc_domain.tenancy.enums import UserRole
from grc_domain.tenancy.value_objects import Email, Region


def make_org(org_id: str = "org-1", name: str = "Acme") -> Organization:
    return Organization.register(id=OrganizationId(org_id), name=name, region=Region("sa"))


def make_user(org_id: str = "org-1", user_id: str = "user-1") -> User:
    return User.invite(
        id=UserId(user_id),
        organization_id=OrganizationId(org_id),
        email=Email("owner@example.com"),
        display_name="Owner",
        roles={UserRole.COMPLIANCE_MANAGER},
    )


def make_control(org_id: str = "org-1", control_id: str = "ctl-1") -> Control:
    return Control.create(
        id=ControlId(control_id),
        organization_id=OrganizationId(org_id),
        workspace_id=WorkspaceId("ws-1"),
        title="Access control",
        description="Least privilege",
    )


def make_policy(org_id: str = "org-1", policy_id: str = "pol-1") -> Policy:
    return Policy.draft(
        id=PolicyId(policy_id),
        organization_id=OrganizationId(org_id),
        title="Acceptable Use",
        body=PolicyBody("All staff must..."),
        owner_id=UserId("user-1"),
        citations=(
            Citation(source_id=KnowledgeSourceId("ks-1"), locator="§1", snippet="policy basis"),
        ),
    )


def make_risk(org_id: str = "org-1", risk_id: str = "risk-1") -> Risk:
    return Risk.identify(
        id=RiskId(risk_id),
        organization_id=OrganizationId(org_id),
        title="Data exfiltration",
        category="security",
    )


def make_framework(framework_id: str = "framework:iso_27001", version: str = "2022") -> Framework:
    control = FrameworkControl(
        id=FrameworkControlId("A.5.1"),
        code="A.5.1",
        title="Policies for information security",
        domain="Organizational",
        requirements=(Requirement(code="A.5.1.1", text="Define policies"),),
    )
    return Framework.import_definition(
        id=FrameworkId(framework_id),
        name="ISO/IEC 27001",
        version=FrameworkVersion(version),
        controls=(control,),
        region="global",
        languages=("en",),
    )


def make_mission(
    org_id: str = "org-1",
    mission_id: str = "mission-1",
    *,
    step_ids: tuple[str, ...] = ("step-a", "step-b"),
) -> Mission:
    mission = Mission.create(
        id=MissionId(mission_id),
        organization_id=OrganizationId(org_id),
        workspace_id=WorkspaceId("ws-1"),
        goal=MissionGoal("Perform an ISO 27001 gap analysis"),
        created_by=UserId("user-1"),
    )
    mission.plan([MissionStep(id=MissionStepId(sid), name=sid.upper()) for sid in step_ids])
    return mission


def make_knowledge_source(
    source_id: str = "src-1", *, scope: KnowledgeScope | None = None
) -> KnowledgeSource:
    return KnowledgeSource.register(
        id=KnowledgeSourceId(source_id),
        scope=scope or KnowledgeScope.global_(),
        short_code="ISO-27001",
        title=LocalizedText(entries=(("en", "ISO/IEC 27001"), ("ar", "آيزو 27001"))),
        authority="ISO",
        jurisdiction="international",
        knowledge_domain=KnowledgeDomain.STANDARDS_FRAMEWORKS,
        document_type=DocumentType.STANDARD,
        tags=("iso", "information-security"),
    )
