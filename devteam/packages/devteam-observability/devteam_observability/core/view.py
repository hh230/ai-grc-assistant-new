"""``RuntimeStateView`` — the clean read API the Dashboard consumes (later, not this task).

A read-only façade over the ``AgentRuntimeRegistry`` that returns plain JSON-ready ``dict``s
(matching the dashboard's existing ``dict[str, object]`` convention, e.g. ``/api/missions``). This
is the seam the task asks for: "expose clean runtime APIs/events that the Dashboard can consume
later." Wiring an actual ``/api/agents`` route onto this is a separate, later step — the view makes
no HTTP or transport assumption.

Every method is a pure read; nothing here mutates state or reaches the runtime. Output is sorted for
stable rendering.
"""

from __future__ import annotations

from devteam_observability.core.ids import AgentId
from devteam_observability.core.registry import AgentRuntimeRegistry, AgentRuntimeState


class RuntimeStateView:
    """Read-only projection of the runtime for a consumer. Construct with the live registry; call
    ``snapshot`` for a whole-dashboard poll, or the finer methods for a single panel."""

    def __init__(self, registry: AgentRuntimeRegistry) -> None:
        self._registry = registry

    def agents(self) -> list[dict[str, object]]:
        """Every known agent's live state, sorted by identity key for stable order."""
        states = sorted(self._registry.all_states(), key=lambda state: state.agent_id.key)
        return [self._agent_dto(state) for state in states]

    def agent(self, agent_id: AgentId) -> dict[str, object] | None:
        """One agent's live state, or ``None`` if it is not known to the runtime."""
        state = self._registry.state_for(agent_id)
        return self._agent_dto(state) if state is not None else None

    def _agent_dto(self, state: AgentRuntimeState) -> dict[str, object]:
        """The agent DTO, with its active session resolved from the store (the state holds only the
        id, so the view — which has the registry — attaches the full session)."""
        dto = state.to_dict()
        active = self._registry.active_session_for(state.agent_id)
        dto["active_session"] = active.to_dict() if active is not None else None
        return dto

    def missions(self) -> list[dict[str, object]]:
        """Every mission the runtime has observed, with owner, participants, and handoff chain."""
        missions = sorted(self._registry.all_missions(), key=lambda mission: mission.mission_id)
        return [mission.to_dict() for mission in missions]

    def ownership(self) -> dict[str, str]:
        """The ``mission_id -> owning-agent key`` map: which agent owns each mission."""
        return {
            mission.mission_id: mission.owner.key
            for mission in self._registry.all_missions()
            if mission.owner is not None
        }

    def mission_flow(self, mission_id: str) -> dict[str, object] | None:
        """One mission's observable flow (owner, ordered participants, handoffs, lifecycle status),
        or ``None`` if the runtime has not seen that mission."""
        mission = self._registry.mission_state(mission_id)
        return mission.to_dict() if mission is not None else None

    def recent_events(self, limit: int = 100) -> list[dict[str, object]]:
        """The tail of the runtime's event feed (agent + derived status-change events), oldest
        first — the live activity stream a dashboard renders."""
        return [event.to_dict() for event in self._registry.recent_events(limit)]

    def mission_sessions(self, mission_id: str) -> list[dict[str, object]]:
        """A mission's execution timeline: its sessions (sealed + in-flight), oldest first. The
        foundation for a Live Pipeline view / dashboard timeline / replay."""
        return [session.to_dict() for session in self._registry.sessions_for_mission(mission_id)]

    def recent_sessions(self, limit: int = 100) -> list[dict[str, object]]:
        """The tail of the immutable session history — the analytics/replay ledger."""
        return [session.to_dict() for session in self._registry.recent_sessions(limit)]

    def snapshot(self) -> dict[str, object]:
        """Everything a dashboard needs in one poll: agents (each with its active session),
        missions, ownership, recent sessions, and the recent event feed."""
        return {
            "agents": self.agents(),
            "missions": self.missions(),
            "ownership": self.ownership(),
            "recent_sessions": self.recent_sessions(),
            "recent_events": self.recent_events(),
        }
