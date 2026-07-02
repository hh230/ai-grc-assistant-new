"""In-memory ``UnitOfWork`` — the reference runtime store binding.

This is a faithful, first-class implementation of the application's ``UnitOfWork`` port
(``grc_services.shared.unit_of_work``): it exposes every domain repository, enforces **absolute
tenant isolation** (every tenant-scoped read/list/save is keyed by ``organization_id``; default
deny — CLAUDE.md §20, ADR-0014), is **atomic** (writes are staged and applied only on
``commit``; an error rolls back with no partial effect — CLAUDE.md §16), and **collects the
domain events** recorded by the aggregates it touched so the handler can dispatch them after
commit (the same contract the SQLAlchemy implementation honours).

It is the default binding because it needs no external dependencies, keeps the API fully
runnable and testable end to end, and is the natural store for the "Tests" caller (CLAUDE.md
§9). The **production** binding is ``grc_persistence.SqlAlchemyUnitOfWork`` over Postgres /
pgvector; selecting it at runtime is a composition-root config swap that is currently **gated
on ADL-0008** (the knowledge-persistence re-alignment). No business logic differs between the
two — only durability and the backing store.
"""

from __future__ import annotations

import asyncio
import copy
from collections import defaultdict
from datetime import datetime

from grc_domain.assessments.entities import Assessment
from grc_domain.assessments.repositories import AssessmentRepository
from grc_domain.audit.entities import AuditRecord
from grc_domain.audit.repositories import AuditRecordRepository
from grc_domain.controls.entities import Control
from grc_domain.controls.repositories import ControlRepository
from grc_domain.evidence.entities import Evidence
from grc_domain.evidence.repositories import EvidenceRepository
from grc_domain.frameworks.entities import Framework, FrameworkMappingSet
from grc_domain.frameworks.enums import FrameworkStatus
from grc_domain.frameworks.repositories import (
    FrameworkMappingRepository,
    FrameworkRepository,
)
from grc_domain.frameworks.value_objects import FrameworkVersion
from grc_domain.knowledge.entities import KnowledgeSource
from grc_domain.knowledge.repositories import KnowledgeSourceRepository
from grc_domain.missions.entities import Mission
from grc_domain.missions.repositories import MissionRepository
from grc_domain.platform.entities import (
    AgentDescriptor,
    PluginDescriptor,
    ToolDescriptor,
)
from grc_domain.platform.enums import AgentStatus, ToolStatus
from grc_domain.platform.repositories import (
    AgentDescriptorRepository,
    PluginDescriptorRepository,
    ToolDescriptorRepository,
)
from grc_domain.policies.entities import Policy
from grc_domain.policies.repositories import PolicyRepository
from grc_domain.reporting.entities import Report
from grc_domain.reporting.repositories import ReportRepository
from grc_domain.risks.entities import Risk
from grc_domain.risks.repositories import RiskRepository
from grc_domain.shared.entity import AggregateRoot
from grc_domain.shared.events import DomainEvent
from grc_domain.shared.identifiers import (
    AgentId,
    AssessmentId,
    AuditRecordId,
    ControlId,
    EvidenceId,
    FrameworkId,
    FrameworkMappingId,
    KnowledgeSourceId,
    MissionId,
    OrganizationId,
    PluginId,
    PolicyId,
    ReportId,
    RiskId,
    ToolId,
    UserId,
    WorkspaceId,
)
from grc_domain.tenancy.entities import Organization, User
from grc_domain.tenancy.repositories import OrganizationRepository, UserRepository
from grc_domain.workspace.entities import Workspace
from grc_domain.workspace.repositories import WorkspaceRepository
from grc_services.shared.unit_of_work import UnitOfWork


class InMemoryDatabase:
    """The shared, committed backing store. One instance is held for the process lifetime."""

    def __init__(self) -> None:
        # table name -> primary key -> committed aggregate snapshot
        self.tables: dict[str, dict[str, object]] = defaultdict(dict)
        self.lock = asyncio.Lock()


def _tenant_key(organization_id: object, entity_id: object) -> str:
    return f"{organization_id}/{entity_id}"


class InMemoryUnitOfWork(UnitOfWork):
    """A single atomic transaction over the shared in-memory database."""

    def __init__(self, db: InMemoryDatabase) -> None:
        self._db = db
        self._staged: dict[tuple[str, str], object] = {}
        self._tracked: list[AggregateRoot] = []

    # ---- transaction control ----
    async def begin(self) -> None:
        self._staged = {}
        self._tracked = []

    async def commit(self) -> None:
        async with self._db.lock:
            for (table, key), aggregate in self._staged.items():
                self._db.tables[table][key] = copy.deepcopy(aggregate)
        self._staged = {}

    async def rollback(self) -> None:
        self._staged = {}

    def collect_new_events(self) -> list[DomainEvent]:
        events: list[DomainEvent] = []
        for aggregate in self._tracked:
            events.extend(aggregate.pull_events())
        return events

    # ---- store primitives used by the repositories ----
    def read(self, table: str, key: str) -> object | None:
        if (table, key) in self._staged:
            return self._staged[(table, key)]
        committed = self._db.tables[table].get(key)
        return copy.deepcopy(committed) if committed is not None else None

    def values(self, table: str) -> list[object]:
        merged: dict[str, object] = {
            key: copy.deepcopy(value) for key, value in self._db.tables[table].items()
        }
        for (staged_table, key), aggregate in self._staged.items():
            if staged_table == table:
                merged[key] = aggregate
        return list(merged.values())

    def put(self, table: str, key: str, aggregate: object, *, track: bool = True) -> None:
        self._staged[(table, key)] = aggregate
        if track and isinstance(aggregate, AggregateRoot) and aggregate not in self._tracked:
            self._tracked.append(aggregate)

    # ---- repositories (lazily built, cached per unit of work) ----
    def _repo(self, attr: str, factory: type) -> object:
        cached = self.__dict__.get(f"_repo_{attr}")
        if cached is None:
            cached = factory(self)
            self.__dict__[f"_repo_{attr}"] = cached
        return cached

    @property
    def organizations(self) -> OrganizationRepository:
        return self._repo("organizations", _OrganizationRepo)  # type: ignore[return-value]

    @property
    def users(self) -> UserRepository:
        return self._repo("users", _UserRepo)  # type: ignore[return-value]

    @property
    def workspaces(self) -> WorkspaceRepository:
        return self._repo("workspaces", _WorkspaceRepo)  # type: ignore[return-value]

    @property
    def missions(self) -> MissionRepository:
        return self._repo("missions", _MissionRepo)  # type: ignore[return-value]

    @property
    def frameworks(self) -> FrameworkRepository:
        return self._repo("frameworks", _FrameworkRepo)  # type: ignore[return-value]

    @property
    def framework_mappings(self) -> FrameworkMappingRepository:
        return self._repo("framework_mappings", _FrameworkMappingRepo)  # type: ignore[return-value]

    @property
    def controls(self) -> ControlRepository:
        return self._repo("controls", _ControlRepo)  # type: ignore[return-value]

    @property
    def policies(self) -> PolicyRepository:
        return self._repo("policies", _PolicyRepo)  # type: ignore[return-value]

    @property
    def risks(self) -> RiskRepository:
        return self._repo("risks", _RiskRepo)  # type: ignore[return-value]

    @property
    def assessments(self) -> AssessmentRepository:
        return self._repo("assessments", _AssessmentRepo)  # type: ignore[return-value]

    @property
    def evidence(self) -> EvidenceRepository:
        return self._repo("evidence", _EvidenceRepo)  # type: ignore[return-value]

    @property
    def knowledge_sources(self) -> KnowledgeSourceRepository:
        return self._repo("knowledge_sources", _KnowledgeSourceRepo)  # type: ignore[return-value]

    @property
    def reports(self) -> ReportRepository:
        return self._repo("reports", _ReportRepo)  # type: ignore[return-value]

    @property
    def tools(self) -> ToolDescriptorRepository:
        return self._repo("tools", _ToolRepo)  # type: ignore[return-value]

    @property
    def agents(self) -> AgentDescriptorRepository:
        return self._repo("agents", _AgentRepo)  # type: ignore[return-value]

    @property
    def plugins(self) -> PluginDescriptorRepository:
        return self._repo("plugins", _PluginRepo)  # type: ignore[return-value]

    @property
    def audit(self) -> AuditRecordRepository:
        return self._repo("audit", _AuditRepo)  # type: ignore[return-value]


# --------------------------------------------------------------------------------------
# Repository implementations. Each is intentionally tiny: tenant-scoped key construction,
# a default-deny read, and staging on write. Translation/business rules live in the domain.
# --------------------------------------------------------------------------------------

_TABLE_ORGANIZATIONS = "organizations"
_TABLE_USERS = "users"
_TABLE_WORKSPACES = "workspaces"
_TABLE_MISSIONS = "missions"
_TABLE_FRAMEWORKS = "frameworks"
_TABLE_FRAMEWORK_MAPPINGS = "framework_mappings"
_TABLE_CONTROLS = "controls"
_TABLE_POLICIES = "policies"
_TABLE_RISKS = "risks"
_TABLE_ASSESSMENTS = "assessments"
_TABLE_EVIDENCE = "evidence"
_TABLE_KNOWLEDGE = "knowledge_sources"
_TABLE_REPORTS = "reports"
_TABLE_TOOLS = "tools"
_TABLE_AGENTS = "agents"
_TABLE_PLUGINS = "plugins"
_TABLE_AUDIT = "audit"


class _OrganizationRepo(OrganizationRepository):
    def __init__(self, uow: InMemoryUnitOfWork) -> None:
        self._uow = uow

    async def get(self, organization_id: OrganizationId) -> Organization | None:
        return self._uow.read(_TABLE_ORGANIZATIONS, str(organization_id))  # type: ignore[return-value]

    async def add(self, organization: Organization) -> None:
        self._uow.put(_TABLE_ORGANIZATIONS, str(organization.id), organization)

    async def save(self, organization: Organization) -> None:
        self._uow.put(_TABLE_ORGANIZATIONS, str(organization.id), organization)


class _UserRepo(UserRepository):
    def __init__(self, uow: InMemoryUnitOfWork) -> None:
        self._uow = uow

    async def get(self, organization_id: OrganizationId, user_id: UserId) -> User | None:
        return self._uow.read(_TABLE_USERS, _tenant_key(organization_id, user_id))  # type: ignore[return-value]

    async def list_for_organization(self, organization_id: OrganizationId) -> list[User]:
        return [
            user
            for user in self._uow.values(_TABLE_USERS)
            if isinstance(user, User) and user.organization_id == organization_id
        ]

    async def add(self, user: User) -> None:
        self._uow.put(_TABLE_USERS, _tenant_key(user.organization_id, user.id), user)

    async def save(self, user: User) -> None:
        self._uow.put(_TABLE_USERS, _tenant_key(user.organization_id, user.id), user)


class _WorkspaceRepo(WorkspaceRepository):
    def __init__(self, uow: InMemoryUnitOfWork) -> None:
        self._uow = uow

    async def get(
        self, organization_id: OrganizationId, workspace_id: WorkspaceId
    ) -> Workspace | None:
        return self._uow.read(_TABLE_WORKSPACES, _tenant_key(organization_id, workspace_id))  # type: ignore[return-value]

    async def list_for_organization(self, organization_id: OrganizationId) -> list[Workspace]:
        return [
            ws
            for ws in self._uow.values(_TABLE_WORKSPACES)
            if isinstance(ws, Workspace) and ws.organization_id == organization_id
        ]

    async def add(self, workspace: Workspace) -> None:
        self._uow.put(
            _TABLE_WORKSPACES, _tenant_key(workspace.organization_id, workspace.id), workspace
        )

    async def save(self, workspace: Workspace) -> None:
        self._uow.put(
            _TABLE_WORKSPACES, _tenant_key(workspace.organization_id, workspace.id), workspace
        )


class _MissionRepo(MissionRepository):
    def __init__(self, uow: InMemoryUnitOfWork) -> None:
        self._uow = uow

    async def get(self, organization_id: OrganizationId, mission_id: MissionId) -> Mission | None:
        return self._uow.read(_TABLE_MISSIONS, _tenant_key(organization_id, mission_id))  # type: ignore[return-value]

    async def list_for_workspace(
        self, organization_id: OrganizationId, workspace_id: WorkspaceId
    ) -> list[Mission]:
        return [
            mission
            for mission in self._uow.values(_TABLE_MISSIONS)
            if isinstance(mission, Mission)
            and mission.organization_id == organization_id
            and mission.workspace_id == workspace_id
        ]

    async def add(self, mission: Mission) -> None:
        self._uow.put(_TABLE_MISSIONS, _tenant_key(mission.organization_id, mission.id), mission)

    async def save(self, mission: Mission) -> None:
        self._uow.put(_TABLE_MISSIONS, _tenant_key(mission.organization_id, mission.id), mission)


class _FrameworkRepo(FrameworkRepository):
    def __init__(self, uow: InMemoryUnitOfWork) -> None:
        self._uow = uow

    @staticmethod
    def _key(framework_id: object, version: object) -> str:
        return f"{framework_id}@{version}"

    async def get(self, framework_id: FrameworkId, version: FrameworkVersion) -> Framework | None:
        return self._uow.read(_TABLE_FRAMEWORKS, self._key(framework_id, version))  # type: ignore[return-value]

    async def list_published(self) -> list[Framework]:
        return sorted(
            (
                fw
                for fw in self._uow.values(_TABLE_FRAMEWORKS)
                if isinstance(fw, Framework) and fw.status == FrameworkStatus.PUBLISHED
            ),
            key=lambda fw: str(fw.id),
        )

    async def add(self, framework: Framework) -> None:
        self._uow.put(_TABLE_FRAMEWORKS, self._key(framework.id, framework.version), framework)

    async def save(self, framework: Framework) -> None:
        self._uow.put(_TABLE_FRAMEWORKS, self._key(framework.id, framework.version), framework)


class _FrameworkMappingRepo(FrameworkMappingRepository):
    def __init__(self, uow: InMemoryUnitOfWork) -> None:
        self._uow = uow

    async def get(self, mapping_id: FrameworkMappingId) -> FrameworkMappingSet | None:
        return self._uow.read(_TABLE_FRAMEWORK_MAPPINGS, str(mapping_id))  # type: ignore[return-value]

    async def find_between(
        self, source_framework_id: FrameworkId, target_framework_id: FrameworkId
    ) -> FrameworkMappingSet | None:
        for mapping in self._uow.values(_TABLE_FRAMEWORK_MAPPINGS):
            if (
                isinstance(mapping, FrameworkMappingSet)
                and mapping.source_framework_id == source_framework_id
                and mapping.target_framework_id == target_framework_id
            ):
                return mapping
        return None

    async def add(self, mapping_set: FrameworkMappingSet) -> None:
        self._uow.put(_TABLE_FRAMEWORK_MAPPINGS, str(mapping_set.id), mapping_set)


class _ControlRepo(ControlRepository):
    def __init__(self, uow: InMemoryUnitOfWork) -> None:
        self._uow = uow

    async def get(self, organization_id: OrganizationId, control_id: ControlId) -> Control | None:
        return self._uow.read(_TABLE_CONTROLS, _tenant_key(organization_id, control_id))  # type: ignore[return-value]

    async def list_for_workspace(
        self, organization_id: OrganizationId, workspace_id: WorkspaceId
    ) -> list[Control]:
        return [
            control
            for control in self._uow.values(_TABLE_CONTROLS)
            if isinstance(control, Control)
            and control.organization_id == organization_id
            and control.workspace_id == workspace_id
        ]

    async def add(self, control: Control) -> None:
        self._uow.put(_TABLE_CONTROLS, _tenant_key(control.organization_id, control.id), control)

    async def save(self, control: Control) -> None:
        self._uow.put(_TABLE_CONTROLS, _tenant_key(control.organization_id, control.id), control)


class _PolicyRepo(PolicyRepository):
    def __init__(self, uow: InMemoryUnitOfWork) -> None:
        self._uow = uow

    async def get(self, organization_id: OrganizationId, policy_id: PolicyId) -> Policy | None:
        return self._uow.read(_TABLE_POLICIES, _tenant_key(organization_id, policy_id))  # type: ignore[return-value]

    async def list_for_organization(self, organization_id: OrganizationId) -> list[Policy]:
        return [
            policy
            for policy in self._uow.values(_TABLE_POLICIES)
            if isinstance(policy, Policy) and policy.organization_id == organization_id
        ]

    async def add(self, policy: Policy) -> None:
        self._uow.put(_TABLE_POLICIES, _tenant_key(policy.organization_id, policy.id), policy)

    async def save(self, policy: Policy) -> None:
        self._uow.put(_TABLE_POLICIES, _tenant_key(policy.organization_id, policy.id), policy)


class _RiskRepo(RiskRepository):
    def __init__(self, uow: InMemoryUnitOfWork) -> None:
        self._uow = uow

    async def get(self, organization_id: OrganizationId, risk_id: RiskId) -> Risk | None:
        return self._uow.read(_TABLE_RISKS, _tenant_key(organization_id, risk_id))  # type: ignore[return-value]

    async def list_for_organization(self, organization_id: OrganizationId) -> list[Risk]:
        return [
            risk
            for risk in self._uow.values(_TABLE_RISKS)
            if isinstance(risk, Risk) and risk.organization_id == organization_id
        ]

    async def add(self, risk: Risk) -> None:
        self._uow.put(_TABLE_RISKS, _tenant_key(risk.organization_id, risk.id), risk)

    async def save(self, risk: Risk) -> None:
        self._uow.put(_TABLE_RISKS, _tenant_key(risk.organization_id, risk.id), risk)


class _AssessmentRepo(AssessmentRepository):
    def __init__(self, uow: InMemoryUnitOfWork) -> None:
        self._uow = uow

    async def get(
        self, organization_id: OrganizationId, assessment_id: AssessmentId
    ) -> Assessment | None:
        return self._uow.read(_TABLE_ASSESSMENTS, _tenant_key(organization_id, assessment_id))  # type: ignore[return-value]

    async def list_for_organization(self, organization_id: OrganizationId) -> list[Assessment]:
        return [
            assessment
            for assessment in self._uow.values(_TABLE_ASSESSMENTS)
            if isinstance(assessment, Assessment) and assessment.organization_id == organization_id
        ]

    async def add(self, assessment: Assessment) -> None:
        self._uow.put(
            _TABLE_ASSESSMENTS, _tenant_key(assessment.organization_id, assessment.id), assessment
        )

    async def save(self, assessment: Assessment) -> None:
        self._uow.put(
            _TABLE_ASSESSMENTS, _tenant_key(assessment.organization_id, assessment.id), assessment
        )


class _EvidenceRepo(EvidenceRepository):
    def __init__(self, uow: InMemoryUnitOfWork) -> None:
        self._uow = uow

    async def get(
        self, organization_id: OrganizationId, evidence_id: EvidenceId
    ) -> Evidence | None:
        return self._uow.read(_TABLE_EVIDENCE, _tenant_key(organization_id, evidence_id))  # type: ignore[return-value]

    async def list_for_control(
        self, organization_id: OrganizationId, control_id: ControlId
    ) -> list[Evidence]:
        return [
            evidence
            for evidence in self._uow.values(_TABLE_EVIDENCE)
            if isinstance(evidence, Evidence)
            and evidence.organization_id == organization_id
            and control_id in evidence.linked_control_ids
        ]

    async def add(self, evidence: Evidence) -> None:
        self._uow.put(_TABLE_EVIDENCE, _tenant_key(evidence.organization_id, evidence.id), evidence)

    async def save(self, evidence: Evidence) -> None:
        self._uow.put(_TABLE_EVIDENCE, _tenant_key(evidence.organization_id, evidence.id), evidence)


class _KnowledgeSourceRepo(KnowledgeSourceRepository):
    def __init__(self, uow: InMemoryUnitOfWork) -> None:
        self._uow = uow

    async def get(
        self, organization_id: OrganizationId, source_id: KnowledgeSourceId
    ) -> KnowledgeSource | None:
        return self._uow.read(_TABLE_KNOWLEDGE, _tenant_key(organization_id, source_id))  # type: ignore[return-value]

    async def list_for_organization(self, organization_id: OrganizationId) -> list[KnowledgeSource]:
        return [
            source
            for source in self._uow.values(_TABLE_KNOWLEDGE)
            if isinstance(source, KnowledgeSource)
            and source.scope.organization_id == organization_id
        ]

    async def add(self, source: KnowledgeSource) -> None:
        self._uow.put(_TABLE_KNOWLEDGE, self._key(source), source)

    async def save(self, source: KnowledgeSource) -> None:
        self._uow.put(_TABLE_KNOWLEDGE, self._key(source), source)

    @staticmethod
    def _key(source: KnowledgeSource) -> str:
        # Tenancy is carried by the KnowledgeScope (org-scoped or platform-global).
        org = source.scope.organization_id
        return _tenant_key(org if org is not None else "__global__", source.id)


class _ReportRepo(ReportRepository):
    def __init__(self, uow: InMemoryUnitOfWork) -> None:
        self._uow = uow

    async def get(self, organization_id: OrganizationId, report_id: ReportId) -> Report | None:
        return self._uow.read(_TABLE_REPORTS, _tenant_key(organization_id, report_id))  # type: ignore[return-value]

    async def list_for_organization(self, organization_id: OrganizationId) -> list[Report]:
        return [
            report
            for report in self._uow.values(_TABLE_REPORTS)
            if isinstance(report, Report) and report.organization_id == organization_id
        ]

    async def add(self, report: Report) -> None:
        self._uow.put(_TABLE_REPORTS, _tenant_key(report.organization_id, report.id), report)

    async def save(self, report: Report) -> None:
        self._uow.put(_TABLE_REPORTS, _tenant_key(report.organization_id, report.id), report)


class _ToolRepo(ToolDescriptorRepository):
    def __init__(self, uow: InMemoryUnitOfWork) -> None:
        self._uow = uow

    async def get(self, tool_id: ToolId) -> ToolDescriptor | None:
        return self._uow.read(_TABLE_TOOLS, str(tool_id))  # type: ignore[return-value]

    async def find_by_name(self, name: str) -> list[ToolDescriptor]:
        return [
            tool
            for tool in self._uow.values(_TABLE_TOOLS)
            if isinstance(tool, ToolDescriptor) and tool.name == name
        ]

    async def list_active(self) -> list[ToolDescriptor]:
        return sorted(
            (
                tool
                for tool in self._uow.values(_TABLE_TOOLS)
                if isinstance(tool, ToolDescriptor) and tool.status == ToolStatus.REGISTERED
            ),
            key=lambda tool: tool.name,
        )

    async def add(self, tool: ToolDescriptor) -> None:
        self._uow.put(_TABLE_TOOLS, str(tool.id), tool)

    async def save(self, tool: ToolDescriptor) -> None:
        self._uow.put(_TABLE_TOOLS, str(tool.id), tool)


class _AgentRepo(AgentDescriptorRepository):
    def __init__(self, uow: InMemoryUnitOfWork) -> None:
        self._uow = uow

    async def get(self, agent_id: AgentId) -> AgentDescriptor | None:
        return self._uow.read(_TABLE_AGENTS, str(agent_id))  # type: ignore[return-value]

    async def list_active(self) -> list[AgentDescriptor]:
        return sorted(
            (
                agent
                for agent in self._uow.values(_TABLE_AGENTS)
                if isinstance(agent, AgentDescriptor) and agent.status == AgentStatus.REGISTERED
            ),
            key=lambda agent: agent.name,
        )

    async def add(self, agent: AgentDescriptor) -> None:
        self._uow.put(_TABLE_AGENTS, str(agent.id), agent)

    async def save(self, agent: AgentDescriptor) -> None:
        self._uow.put(_TABLE_AGENTS, str(agent.id), agent)


class _PluginRepo(PluginDescriptorRepository):
    def __init__(self, uow: InMemoryUnitOfWork) -> None:
        self._uow = uow

    async def get(self, plugin_id: PluginId) -> PluginDescriptor | None:
        return self._uow.read(_TABLE_PLUGINS, str(plugin_id))  # type: ignore[return-value]

    async def list_installed(self) -> list[PluginDescriptor]:
        return sorted(
            (
                plugin
                for plugin in self._uow.values(_TABLE_PLUGINS)
                if isinstance(plugin, PluginDescriptor)
            ),
            key=lambda plugin: plugin.name,
        )

    async def add(self, plugin: PluginDescriptor) -> None:
        self._uow.put(_TABLE_PLUGINS, str(plugin.id), plugin)

    async def save(self, plugin: PluginDescriptor) -> None:
        self._uow.put(_TABLE_PLUGINS, str(plugin.id), plugin)


class _AuditRepo(AuditRecordRepository):
    def __init__(self, uow: InMemoryUnitOfWork) -> None:
        self._uow = uow

    async def append(self, record: AuditRecord) -> None:
        # Audit records are entities, not aggregate roots: stage without event tracking.
        self._uow.put(
            _TABLE_AUDIT, _tenant_key(record.organization_id, record.id), record, track=False
        )

    async def get(
        self, organization_id: OrganizationId, record_id: AuditRecordId
    ) -> AuditRecord | None:
        return self._uow.read(_TABLE_AUDIT, _tenant_key(organization_id, record_id))  # type: ignore[return-value]

    async def query(
        self,
        organization_id: OrganizationId,
        *,
        object_type: str | None = None,
        object_id: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[AuditRecord]:
        records = [
            record
            for record in self._uow.values(_TABLE_AUDIT)
            if isinstance(record, AuditRecord) and record.organization_id == organization_id
        ]
        if object_type is not None:
            records = [r for r in records if r.object_type == object_type]
        if object_id is not None:
            records = [r for r in records if r.object_id == object_id]
        if since is not None:
            records = [r for r in records if r.occurred_at >= since]
        if until is not None:
            records = [r for r in records if r.occurred_at <= until]
        return sorted(records, key=lambda r: r.occurred_at)
