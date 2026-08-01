"""Autonomous Platform Dev Team — Mission Intake & Correlation (ADR 0063/0064).

TriggerSource normalizes any external event into one IntakeSignal; MissionCorrelator (the boundary)
decides create vs update, with correlation storage a detail behind it;
MissionIntake receives that command (never a raw event) and produces a governed Dev Mission or an
audited signal.
"""

from devteam_intake.commands import CreateMission, IntakeCommand, UpdateMission
from devteam_intake.correlation import (
    CorrelationDeactivator,
    CorrelationRepository,
    MissionCorrelator,
    StoreMissionCorrelator,
)
from devteam_intake.events import MissionSignalReceived
from devteam_intake.intake import IntakeGateway, IntakeOutcome, MissionIntake
from devteam_intake.signal import IntakeSignal
from devteam_intake.triggers import CIFailureSource, ManualRequestSource, TriggerSource

__all__ = [
    "CIFailureSource",
    "CorrelationDeactivator",
    "CorrelationRepository",
    "CreateMission",
    "IntakeCommand",
    "IntakeGateway",
    "IntakeOutcome",
    "IntakeSignal",
    "ManualRequestSource",
    "MissionCorrelator",
    "MissionIntake",
    "MissionSignalReceived",
    "StoreMissionCorrelator",
    "TriggerSource",
    "UpdateMission",
]
