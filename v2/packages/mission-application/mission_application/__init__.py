"""Mission Application layer — product Application Services between the HTTP host and the Core.

Organised as a small, stable **language** plus the services that speak it (ADR 0054):

- `contracts/` — the shared vocabulary: `CommandContext` (ambient inputs), `CommandResult` (the
  stable outcome), the typed error taxonomy, and the collaborator `Port`s commands depend on.
- `queries/` — read-side services (`MissionDetailQuery`); depend on the store + read models only.
- `commands/` — write-side services (`ApproveMissionStepCommand`, …); depend on the engine +
  projection port + (later) an event publisher; never read a read model.
- `views.py` — the read-side View Models (query results).

One class per file; every service's entry point is `execute(...)`. Nothing here imports a web
framework, so the same services are callable from the API, a CLI, or tests.
"""

from __future__ import annotations

from mission_application.builders import DeliverableBuilder, DeliverableBuilderRegistry
from mission_application.commands import (
    ApproveInputs,
    ApproveMissionStepCommand,
    CreatedMission,
    CreateMissionCommand,
    CreateMissionInputs,
    MissionCommand,
    MissionCreatedResult,
    RejectInputs,
    RejectMissionStepCommand,
    StartInputs,
    StartMissionCommand,
)
from mission_application.contracts import (
    ApplicationError,
    CommandContext,
    CommandResult,
    DeliverableNotReady,
    DeliverableProvider,
    FrameworkProvider,
    IllegalCommand,
    MissionAccess,
    MissionCreator,
    MissionDefinitionProvider,
    MissionNotFound,
    MissionWorkflow,
    NotAuthorized,
    ProjectionPort,
    UnsupportedFormat,
)
from mission_application.dashboard_views import (
    CoverageSnapshotView,
    DashboardView,
    RecentMissionView,
)
from mission_application.decision_views import DecisionItemView, RecentDecisionView
from mission_application.export import ExportedFile, Exporter, ExportService
from mission_application.queries import (
    ApprovalQueueProjection,
    CoverageRollupProvider,
    DashboardProjection,
    MissionDetailQuery,
    MissionSummaryProvider,
    ResultQuery,
)
from mission_application.result_views import (
    CoverageView,
    GapAssessmentContent,
    GapRowView,
    GenericContent,
    ResultContent,
    ResultSectionView,
    ResultView,
    TrustBar,
)
from mission_application.views import (
    ApprovalView,
    FindingView,
    MissionDetailView,
    PlanStepView,
)

__all__ = [
    "ApplicationError",
    "ApprovalQueueProjection",
    "ApprovalView",
    "ApproveInputs",
    "ApproveMissionStepCommand",
    "CommandContext",
    "CommandResult",
    "CreateMissionCommand",
    "CreateMissionInputs",
    "CreatedMission",
    "CoverageRollupProvider",
    "CoverageSnapshotView",
    "CoverageView",
    "DashboardProjection",
    "DashboardView",
    "DecisionItemView",
    "DeliverableBuilder",
    "DeliverableBuilderRegistry",
    "DeliverableNotReady",
    "DeliverableProvider",
    "ExportService",
    "ExportedFile",
    "Exporter",
    "FindingView",
    "FrameworkProvider",
    "GapAssessmentContent",
    "GapRowView",
    "GenericContent",
    "IllegalCommand",
    "MissionAccess",
    "MissionCommand",
    "MissionCreatedResult",
    "MissionCreator",
    "MissionDefinitionProvider",
    "MissionDetailQuery",
    "MissionDetailView",
    "MissionNotFound",
    "MissionSummaryProvider",
    "MissionWorkflow",
    "NotAuthorized",
    "PlanStepView",
    "RecentDecisionView",
    "RecentMissionView",
    "ProjectionPort",
    "RejectInputs",
    "RejectMissionStepCommand",
    "StartInputs",
    "StartMissionCommand",
    "ResultContent",
    "ResultQuery",
    "ResultSectionView",
    "ResultView",
    "TrustBar",
    "UnsupportedFormat",
]
