"""The DevTeam adapter — the only agent system wired this milestone.

This subpackage is the *realization* the roster-neutral ``core`` was designed for: it maps the
autonomous dev team (``devteam_protocol`` agents on the frozen Mission Engine) onto ``core``'s
identity and events, and nothing more. It is purely additive — it wraps the ``ExecutionPort`` and
subscribes to the Bus; it never edits an agent, the engine, or the Monitor (owner constraints).

A second agent system integrates later by writing a sibling adapter against ``core`` — this one is
never widened to know about it.
"""

from __future__ import annotations

from devteam_observability.adapter.capture import StepCapture
from devteam_observability.adapter.mission_bridge import MissionEventBridge
from devteam_observability.adapter.observing_executor import ObservingExecutor
from devteam_observability.adapter.result_courier import ResultCourier
from devteam_observability.adapter.roster import (
    CAPABILITY_ROLES,
    DISPLAY_NAMES,
    ORG_ROSTER,
    PLATFORM_ROSTER,
    agent_id_for,
    role_for_tool,
    seed_roster,
)
from devteam_observability.adapter.wiring import (
    DevTeamObservability,
    devteam_view_from_journal,
)

__all__ = [
    "CAPABILITY_ROLES",
    "DISPLAY_NAMES",
    "ORG_ROSTER",
    "PLATFORM_ROSTER",
    "DevTeamObservability",
    "MissionEventBridge",
    "ObservingExecutor",
    "ResultCourier",
    "StepCapture",
    "agent_id_for",
    "devteam_view_from_journal",
    "role_for_tool",
    "seed_roster",
]
