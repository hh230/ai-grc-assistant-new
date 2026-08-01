"""Platform health — the facts the Supervisor computes from the live runtime (§11; CLAUDE.md §19).

A pure assessment over the FROZEN ``RuntimeStateView`` (the one read model — never a second state
model): read the agents and their sessions, and derive who is healthy, which agents are stalled
(executing far past the expected span), and which missions are stalled (an in-flight session that
never sealed). Every field is measured from the view or ``None`` — nothing is inferred or fabricated
(CLAUDE.md §19). The Supervisor agent reports this; the Supervisor controller acts on it.
"""

from __future__ import annotations

from dataclasses import dataclass

from devteam_observability import RuntimeStateView

# An agent actively executing right now (a stall candidate if it has been here too long).
_ACTIVE_STATUSES = frozenset({"working", "thinking"})


@dataclass(frozen=True)
class AgentHealth:
    key: str
    display_name: str
    status: str
    stalled: bool
    idle_for_s: float | None


@dataclass(frozen=True)
class MissionHealth:
    mission_id: str
    active_since_s: float
    stalled: bool


@dataclass(frozen=True)
class HealthReport:
    """One heartbeat's worth of platform health, computed from the view."""

    healthy: bool
    checked_at: float
    agents: tuple[AgentHealth, ...]
    missions: tuple[MissionHealth, ...]
    stalled_agents: tuple[str, ...]
    stalled_missions: tuple[str, ...]
    summary: str

    def to_dict(self) -> dict[str, object]:
        return {
            "healthy": self.healthy,
            "checked_at": self.checked_at,
            "stalled_agents": list(self.stalled_agents),
            "stalled_missions": list(self.stalled_missions),
            "agent_count": len(self.agents),
            "mission_count": len(self.missions),
            "summary": self.summary,
        }


def assess_health(
    view: RuntimeStateView, *, now: float, stall_after_s: float
) -> HealthReport:
    """Compute a ``HealthReport`` from the live view. ``now`` is the heartbeat time; an agent or an
    in-flight session older than ``stall_after_s`` is flagged stalled (a human/Supervisor concern),
    never killed here — detection is separate from recovery."""
    agents = _agent_healths(view, now=now, stall_after_s=stall_after_s)
    missions = _mission_healths(view, now=now, stall_after_s=stall_after_s)
    stalled_agents = tuple(a.key for a in agents if a.stalled)
    stalled_missions = tuple(m.mission_id for m in missions if m.stalled)
    healthy = not stalled_agents and not stalled_missions
    summary = (
        f"{len(agents)} agents observed; all healthy"
        if healthy
        else f"attention: {len(stalled_agents)} stalled agent(s), "
        f"{len(stalled_missions)} stalled mission(s)"
    )
    return HealthReport(
        healthy=healthy,
        checked_at=now,
        agents=agents,
        missions=missions,
        stalled_agents=stalled_agents,
        stalled_missions=stalled_missions,
        summary=summary,
    )


def _agent_healths(
    view: RuntimeStateView, *, now: float, stall_after_s: float
) -> tuple[AgentHealth, ...]:
    healths: list[AgentHealth] = []
    for dto in view.agents():
        key = _agent_key(dto.get("agent"))
        status = _as_str(dto.get("status")) or "unknown"
        last = _as_float(dto.get("last_activity_at"))
        idle_for = (now - last) if last is not None else None
        stalled = (
            status in _ACTIVE_STATUSES and idle_for is not None and idle_for > stall_after_s
        )
        healths.append(
            AgentHealth(
                key=key,
                display_name=_as_str(dto.get("display_name")) or key,
                status=status,
                stalled=stalled,
                idle_for_s=idle_for,
            )
        )
    return tuple(healths)


def _mission_healths(
    view: RuntimeStateView, *, now: float, stall_after_s: float
) -> tuple[MissionHealth, ...]:
    """A mission is stalled when it has a session still ACTIVE (never sealed) older than the
    threshold — the runtime opened a step and never finished it. In-flight sessions live on the
    agents that hold them (``active_session``), not in the sealed ``recent_sessions`` history, so
    read them from the agent DTOs."""
    healths: list[MissionHealth] = []
    for dto in view.agents():
        active = dto.get("active_session")
        if not isinstance(active, dict):
            continue
        started = _as_float(active.get("started_at"))
        if started is None:
            continue
        active_since = now - started
        mission_id = _as_str(active.get("mission_id")) or ""
        healths.append(
            MissionHealth(
                mission_id=mission_id,
                active_since_s=active_since,
                stalled=active_since > stall_after_s,
            )
        )
    return tuple(healths)


def _agent_key(agent: object) -> str:
    if isinstance(agent, dict):
        key = agent.get("key")
        if isinstance(key, str):
            return key
    return ""


def _as_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _as_float(value: object) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None
