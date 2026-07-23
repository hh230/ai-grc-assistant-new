"""Read-side Application Services (Queries). One class per file; entry point is `execute(...)`."""

from __future__ import annotations

from mission_application.queries.approvals import ApprovalQueueProjection
from mission_application.queries.dashboard import (
    CoverageRollupProvider,
    DashboardProjection,
    MissionSummaryProvider,
)
from mission_application.queries.mission_detail import MissionDetailQuery
from mission_application.queries.result import ResultQuery

__all__ = [
    "ApprovalQueueProjection",
    "CoverageRollupProvider",
    "DashboardProjection",
    "MissionDetailQuery",
    "MissionSummaryProvider",
    "ResultQuery",
]
