"""Roster-neutral agent identity and the live status vocabulary.

An ``AgentId`` names an agent WITHOUT committing to any one agent system's role enum: it is a
``(subsystem, role)`` pair. The DevTeam adapter maps ``devteam_protocol.AgentRole`` ->
``AgentId(AgentSubsystem.PLATFORM, role.value)``; a future system maps its own roles the same way.
Identity is exactly those two fields (frozen + hashable, so an ``AgentId`` is a dict key); a
human-facing ``display_name`` is metadata carried on the runtime *state*, never part of identity.

``AgentStatus`` is a PROJECTION over invocations, not a heartbeat from a live process — the agents
are stateless functions the Mission Engine invokes per step (``Agent.handle``), so there is no agent
daemon to be "up" or "down". Read the states accordingly: ``Offline`` means "not composed into the
running runtime", not "the process crashed".
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AgentSubsystem(str, Enum):
    """Which agent system an agent belongs to. Only ``PLATFORM`` — the autonomous DevTeam runtime
    (ADR 0061) — is wired this milestone. The enum exists so that integrating a second system (e.g.
    the GRC product agents) is a new member here plus a new adapter, never a change to the
    projection below (owner constraint: extensible without redesign)."""

    PLATFORM = "platform"
    # A second agent system is added here when its adapter lands, e.g.:
    # PRODUCT = "product"   # the GRC product agents (CLAUDE.md §11) — out of scope this milestone.


class AgentStatus(str, Enum):
    """The live status a dashboard renders for an agent. Derived by the registry from the runtime's
    event stream (see ``registry`` for the exact transition rules).

    IDLE     — composed into the runtime and ready; no work in hand.
    WORKING  — actively executing a mission step (inside the agent's ``handle``).
    BLOCKED  — the agent reached a BLOCK/ESCALATE verdict; a human must intervene.

    RESERVED forward-compatible states (owner decision): the following are part of the model for a
    future multi-agent runtime but are NOT produced by today's single DevTeam adapter — they are
    not dead code, they are the extension surface, and the projection already handles them:
    THINKING — a distinct reason-before-act phase (the DevTeam adapter uses WORKING for the whole
               ``handle`` span). WAITING — assigned to a step not yet started (a planner fanning
               work out ahead of execution), or paused at a human approval gate. OFFLINE — known
               to the roster but not composed into this runtime.
    """

    IDLE = "idle"
    THINKING = "thinking"
    WORKING = "working"
    WAITING = "waiting"
    BLOCKED = "blocked"
    OFFLINE = "offline"


@dataclass(frozen=True)
class AgentId:
    """A roster-neutral agent identity: which subsystem, which role. Frozen and hashable so it keys
    the projection's per-agent state. ``role`` is a plain string (the source enum's ``.value``), so
    the core never imports an agent system's role type."""

    subsystem: AgentSubsystem
    role: str

    @property
    def key(self) -> str:
        """A stable flat key (``"platform:developer"``) for JSON maps and log lines."""
        return f"{self.subsystem.value}:{self.role}"

    def to_dict(self) -> dict[str, str]:
        return {"subsystem": self.subsystem.value, "role": self.role, "key": self.key}
