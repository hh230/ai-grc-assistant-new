"""The master use-case registry: every healthy command/query mapped to its handler.

This is the API's view of the Application layer's capability surface. Adding a use case to the
platform means registering it here — the bus then dispatches to it and a router can expose it.
The **knowledge** capability is intentionally absent: its application service targets the
pre-refactor ``KnowledgeSource`` aggregate and is deferred pending ADL-0008.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from grc_services.agents import commands as agents_c
from grc_services.agents import handlers as agents_h
from grc_services.agents import queries as agents_q
from grc_services.assessments import commands as assessments_c
from grc_services.assessments import handlers as assessments_h
from grc_services.assessments import queries as assessments_q
from grc_services.audit import commands as audit_c
from grc_services.audit import handlers as audit_h
from grc_services.audit import queries as audit_q
from grc_services.controls import commands as controls_c
from grc_services.controls import handlers as controls_h
from grc_services.controls import queries as controls_q
from grc_services.evidence import commands as evidence_c
from grc_services.evidence import handlers as evidence_h
from grc_services.evidence import queries as evidence_q
from grc_services.frameworks import commands as frameworks_c
from grc_services.frameworks import handlers as frameworks_h
from grc_services.frameworks import queries as frameworks_q
from grc_services.missions import commands as missions_c
from grc_services.missions import handlers as missions_h
from grc_services.missions import queries as missions_q
from grc_services.plugins import commands as plugins_c
from grc_services.plugins import handlers as plugins_h
from grc_services.plugins import queries as plugins_q
from grc_services.policies import commands as policies_c
from grc_services.policies import handlers as policies_h
from grc_services.policies import queries as policies_q
from grc_services.reporting import commands as reporting_c
from grc_services.reporting import handlers as reporting_h
from grc_services.reporting import queries as reporting_q
from grc_services.risks import commands as risks_c
from grc_services.risks import handlers as risks_h
from grc_services.risks import queries as risks_q
from grc_services.shared.messages import Command, Query
from grc_services.tools import commands as tools_c
from grc_services.tools import handlers as tools_h
from grc_services.tools import queries as tools_q
from grc_services.workspaces import commands as workspaces_c
from grc_services.workspaces import handlers as workspaces_h
from grc_services.workspaces import queries as workspaces_q


@dataclass(frozen=True)
class HandlerRegistry:
    commands: dict[type[Command], type] = field(default_factory=dict)
    queries: dict[type[Query], type] = field(default_factory=dict)


def build_registry() -> HandlerRegistry:
    commands: dict[type[Command], type] = {
        # missions (the flagship lifecycle: create → plan → execute → human-gate → complete)
        missions_c.CreateMission: missions_h.CreateMissionHandler,
        missions_c.PlanMission: missions_h.PlanMissionHandler,
        missions_c.StartMission: missions_h.StartMissionHandler,
        missions_c.StartStep: missions_h.StartStepHandler,
        missions_c.RequestStepApproval: missions_h.RequestStepApprovalHandler,
        missions_c.ApproveGate: missions_h.ApproveGateHandler,
        missions_c.RejectGate: missions_h.RejectGateHandler,
        missions_c.CompleteStep: missions_h.CompleteStepHandler,
        missions_c.CompleteMission: missions_h.CompleteMissionHandler,
        missions_c.CancelMission: missions_h.CancelMissionHandler,
        # workspaces
        workspaces_c.CreateWorkspace: workspaces_h.CreateWorkspaceHandler,
        workspaces_c.AddWorkspaceMember: workspaces_h.AddWorkspaceMemberHandler,
        workspaces_c.RemoveWorkspaceMember: workspaces_h.RemoveWorkspaceMemberHandler,
        workspaces_c.ArchiveWorkspace: workspaces_h.ArchiveWorkspaceHandler,
        # frameworks
        frameworks_c.ImportFramework: frameworks_h.ImportFrameworkHandler,
        frameworks_c.PublishFramework: frameworks_h.PublishFrameworkHandler,
        frameworks_c.DeprecateFramework: frameworks_h.DeprecateFrameworkHandler,
        # controls
        controls_c.CreateControl: controls_h.CreateControlHandler,
        controls_c.MapControlToFramework: controls_h.MapControlToFrameworkHandler,
        controls_c.LinkControlEvidence: controls_h.LinkControlEvidenceHandler,
        controls_c.SetControlImplementationStatus: controls_h.SetControlImplementationStatusHandler,
        # policies
        policies_c.DraftPolicy: policies_h.DraftPolicyHandler,
        policies_c.SubmitPolicyForReview: policies_h.SubmitPolicyForReviewHandler,
        policies_c.ApprovePolicy: policies_h.ApprovePolicyHandler,
        policies_c.PublishPolicy: policies_h.PublishPolicyHandler,
        policies_c.RetirePolicy: policies_h.RetirePolicyHandler,
        # risks
        risks_c.IdentifyRisk: risks_h.IdentifyRiskHandler,
        risks_c.AssessRisk: risks_h.AssessRiskHandler,
        risks_c.PlanRiskTreatment: risks_h.PlanRiskTreatmentHandler,
        risks_c.AcceptRisk: risks_h.AcceptRiskHandler,
        risks_c.CloseRisk: risks_h.CloseRiskHandler,
        # assessments
        assessments_c.PlanAssessment: assessments_h.PlanAssessmentHandler,
        assessments_c.StartAssessment: assessments_h.StartAssessmentHandler,
        assessments_c.RecordAssessmentResult: assessments_h.RecordAssessmentResultHandler,
        assessments_c.CompleteAssessment: assessments_h.CompleteAssessmentHandler,
        # evidence
        evidence_c.CollectEvidence: evidence_h.CollectEvidenceHandler,
        evidence_c.ValidateEvidence: evidence_h.ValidateEvidenceHandler,
        evidence_c.RejectEvidence: evidence_h.RejectEvidenceHandler,
        evidence_c.LinkEvidenceToControl: evidence_h.LinkEvidenceToControlHandler,
        # reporting
        reporting_c.RequestReport: reporting_h.RequestReportHandler,
        reporting_c.AttachReportContent: reporting_h.AttachReportContentHandler,
        reporting_c.FinalizeReport: reporting_h.FinalizeReportHandler,
        reporting_c.PublishReport: reporting_h.PublishReportHandler,
        # audit
        audit_c.RecordAuditEntry: audit_h.RecordAuditEntryHandler,
        # platform: tools / agents / plugins
        tools_c.RegisterTool: tools_h.RegisterToolHandler,
        tools_c.DeprecateTool: tools_h.DeprecateToolHandler,
        agents_c.RegisterAgent: agents_h.RegisterAgentHandler,
        plugins_c.InstallPlugin: plugins_h.InstallPluginHandler,
        plugins_c.EnablePlugin: plugins_h.EnablePluginHandler,
        plugins_c.DisablePlugin: plugins_h.DisablePluginHandler,
    }

    queries: dict[type[Query], type] = {
        missions_q.GetMission: missions_h.GetMissionHandler,
        missions_q.ListMissionsForWorkspace: missions_h.ListMissionsForWorkspaceHandler,
        workspaces_q.GetWorkspace: workspaces_h.GetWorkspaceHandler,
        workspaces_q.ListWorkspaces: workspaces_h.ListWorkspacesHandler,
        frameworks_q.GetFramework: frameworks_h.GetFrameworkHandler,
        frameworks_q.ListPublishedFrameworks: frameworks_h.ListPublishedFrameworksHandler,
        controls_q.GetControl: controls_h.GetControlHandler,
        controls_q.ListControlsForWorkspace: controls_h.ListControlsForWorkspaceHandler,
        policies_q.GetPolicy: policies_h.GetPolicyHandler,
        policies_q.ListPolicies: policies_h.ListPoliciesHandler,
        risks_q.GetRisk: risks_h.GetRiskHandler,
        risks_q.ListRisks: risks_h.ListRisksHandler,
        assessments_q.GetAssessment: assessments_h.GetAssessmentHandler,
        assessments_q.ListAssessments: assessments_h.ListAssessmentsHandler,
        evidence_q.GetEvidence: evidence_h.GetEvidenceHandler,
        evidence_q.ListEvidenceForControl: evidence_h.ListEvidenceForControlHandler,
        reporting_q.GetReport: reporting_h.GetReportHandler,
        reporting_q.ListReports: reporting_h.ListReportsHandler,
        audit_q.GetAuditRecord: audit_h.GetAuditRecordHandler,
        audit_q.QueryAuditTrail: audit_h.QueryAuditTrailHandler,
        tools_q.GetTool: tools_h.GetToolHandler,
        tools_q.ListActiveTools: tools_h.ListActiveToolsHandler,
        agents_q.GetAgent: agents_h.GetAgentHandler,
        agents_q.ListActiveAgents: agents_h.ListActiveAgentsHandler,
        plugins_q.GetPlugin: plugins_h.GetPluginHandler,
        plugins_q.ListPlugins: plugins_h.ListPluginsHandler,
    }

    return HandlerRegistry(commands=commands, queries=queries)
