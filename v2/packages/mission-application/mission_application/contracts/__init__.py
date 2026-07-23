"""The **shared language** of the Application layer (ADR 0054).

As Queries and Commands multiply, these unify them: the ambient `CommandContext`, the stable
`CommandResult`, the typed error taxonomy, and the collaborator `Port`s commands depend on. New
services speak this vocabulary; the vocabulary itself changes rarely.
"""

from __future__ import annotations

from mission_application.contracts.context import CommandContext
from mission_application.contracts.errors import (
    ApplicationError,
    DeliverableNotReady,
    IllegalCommand,
    MissionNotFound,
    NotAuthorized,
    UnsupportedFormat,
)
from mission_application.contracts.ports import (
    DeliverableProvider,
    FrameworkProvider,
    MissionAccess,
    MissionCreator,
    MissionDefinitionProvider,
    MissionWorkflow,
    ProjectionPort,
)
from mission_application.contracts.result import CommandResult

__all__ = [
    "ApplicationError",
    "CommandContext",
    "CommandResult",
    "DeliverableNotReady",
    "DeliverableProvider",
    "FrameworkProvider",
    "IllegalCommand",
    "MissionAccess",
    "MissionCreator",
    "MissionDefinitionProvider",
    "MissionNotFound",
    "MissionWorkflow",
    "NotAuthorized",
    "ProjectionPort",
    "UnsupportedFormat",
]
