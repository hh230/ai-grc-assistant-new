"""Write-side Application Services (Commands). One class per file; entry point is `execute(...)`.

A Command knows nothing about HTTP, FastAPI, requests, headers, or tokens — it receives only the
resolved application inputs (tenant, principal, mission_id, step_id, …) and returns a Domain or
Application result. It drives the Mission Engine; the HTTP host stays a thin adapter.

Populated alongside the S2 action endpoints: `ApproveMissionStepCommand`,
`RejectMissionStepCommand`, `RetryMissionCommand`.
"""

from __future__ import annotations

from mission_application.commands.approve_step import ApproveInputs, ApproveMissionStepCommand
from mission_application.commands.base import MissionCommand
from mission_application.commands.create_mission import (
    CreatedMission,
    CreateMissionCommand,
    CreateMissionInputs,
    MissionCreatedResult,
)
from mission_application.commands.reject_step import RejectInputs, RejectMissionStepCommand
from mission_application.commands.start_mission import StartInputs, StartMissionCommand

__all__ = [
    "ApproveInputs",
    "ApproveMissionStepCommand",
    "CreateMissionCommand",
    "CreateMissionInputs",
    "CreatedMission",
    "MissionCreatedResult",
    "MissionCommand",
    "RejectInputs",
    "RejectMissionStepCommand",
    "StartInputs",
    "StartMissionCommand",
]
