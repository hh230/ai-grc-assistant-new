"""The Executive Experience — an operational command center built by AGGREGATING the existing
Mission and Agent Experiences, not by introducing a new data model.

Everything here is a roll-up of shapes the dashboard already produces from ``RuntimeStateView``:
``agent_metrics`` (the additive per-agent metrics from Increment 3) summed across the roster, and
``session_summary`` (the Mission Experience's per-mission tally) over the missions. One view is
built per request; the journal is never read directly and no runtime logic is introduced. Where the
underlying data can't support a figure the roll-up returns ``None`` — the UI shows "insufficient
data" rather than inventing one.

Increment 1 is the top-level overview; Increment 2 adds the ``organization`` section (fleet status,
the agent-performance table, mission performance, operational health) — the same fleet metrics and
mission sessions, reshaped. Both come back in one payload so the command center renders in one pass.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from devteam_observability import devteam_view_from_journal

from devteam_dashboard.agents_view import _AGENT_HISTORY_LIMIT, agent_metrics, agent_sessions
from devteam_dashboard.pipeline_view import session_summary

# Mission lifecycle statuses after which a mission is no longer in flight.
_TERMINAL_STATUSES = frozenset({"completed", "failed", "cancelled"})
# One mission's sessions, keyed by mission id — read once and reused across the roll-up sections.
_Sessions = dict[str, list[dict[str, object]]]


def read_executive_overview(journal_path: Path | str) -> dict[str, object]:
    """The command center: the Increment-1 overview (active missions, active agents, throughput,
    fleet decisions, queue health, utilization) plus the Increment-2 ``organization`` roll-up —
    all aggregated from one pass over the per-agent ``agent_metrics`` and per-mission sessions."""
    view = devteam_view_from_journal(journal_path)
    agents = view.agents()
    missions = view.missions()
    recent = view.recent_sessions(_AGENT_HISTORY_LIMIT)
    by_id: dict[object, dict[str, object]] = {s.get("session_id"): s for s in recent}
    fleet = [agent_metrics(dto, agent_sessions(recent, by_id, dto)) for dto in agents]

    # One sessions read per mission, reused by every section below (active list, avg completion,
    # long-running) — so a mission is measured once, the same way everywhere.
    sessions_by_mission: dict[str, list[dict[str, object]]] = {}
    for mission in missions:
        mission_id = mission.get("mission_id")
        if isinstance(mission_id, str):
            sessions_by_mission[mission_id] = view.mission_sessions(mission_id)

    active_missions = [m for m in missions if m.get("status") not in _TERMINAL_STATUSES]
    completed = sum(1 for m in missions if m.get("status") == "completed")
    awaiting = sum(1 for m in missions if m.get("status") == "awaiting_approval")
    failed = sum(1 for m in missions if m.get("status") == "failed")

    utilized = sum(1 for m in fleet if m.get("utilized"))
    idle = sum(1 for m in fleet if m.get("status") == "idle")
    blocked = sum(1 for m in fleet if m.get("status") == "blocked")
    waiting = sum(1 for m in fleet if m.get("status") == "waiting")
    engaged = sum(1 for m in fleet if _mapping(m.get("queue")).get("participating"))

    total_active = sum(_num(m.get("active_ms")) for m in fleet)
    total_idle = sum(_num(m.get("idle_ms")) for m in fleet)
    window = total_active + total_idle

    # Computed once, reused by both the overview and the organization section (never recomputed).
    utilization: dict[str, object] = {
        "utilized_now": utilized,
        "total_agents": len(agents),
        "ratio_now": (utilized / len(agents)) if agents else None,
        "active_ms": total_active,
        "idle_ms": total_idle,
        "ratio_window": (total_active / window) if window else None,
    }
    queue_health = _queue_health(blocked, awaiting, engaged, completed)

    active_list = [_mission_card(m, sessions_by_mission) for m in active_missions]
    # Attention lists — built once and reused by the organization section AND the insights layer, so
    # a fact is composed, never recomputed differently ("Executive owns composition, not facts").
    waiting_approvals = [
        {"mission_id": m.get("mission_id"), "owner": _owner(m), "status": "awaiting_approval"}
        for m in missions
        if m.get("status") == "awaiting_approval"
    ]
    long_running = [_long_running(m, sessions_by_mission) for m in active_missions]
    briefs = [_agent_brief(dto, m) for dto, m in zip(agents, fleet, strict=True)]
    stalled = [b for b in briefs if b.get("status") == "blocked"]
    hotspots = [b for b in briefs if b.get("status") in ("working", "thinking", "waiting")]
    available = [b for b in briefs if b.get("status") == "idle"]

    return {
        "missions": {
            "total": len(missions),
            "active": len(active_missions),
            "completed": completed,
            "awaiting_approval": awaiting,
            "failed": failed,
            "active_list": active_list,
        },
        "agents": {
            "total": len(agents),
            "utilized": utilized,
            "idle": idle,
            "blocked": blocked,
            "waiting": waiting,
            "engaged": engaged,
        },
        "throughput": {"completed_missions": completed},
        "decision_distribution": _fleet_decisions(fleet),
        "queue": {
            "engaged_agents": engaged,
            "awaiting_approval": awaiting,
            "blocked_agents": blocked,
            "health": queue_health,
        },
        "utilization": utilization,
        "organization": {
            "fleet": {
                "status_distribution": _status_distribution(fleet),
                "utilization": utilization,
            },
            "agent_performance": [
                _agent_row(dto, m) for dto, m in zip(agents, fleet, strict=True)
            ],
            "mission_performance": {
                "lifecycle_distribution": _lifecycle_distribution(missions),
                "avg_completion_ms": _avg_completion_ms(missions, sessions_by_mission),
                "completed_missions": completed,
                "queue_health": queue_health,
                "bottlenecks": {"awaiting_approval": awaiting, "blocked_agents": blocked},
            },
            "operational_health": {
                "waiting_approvals": waiting_approvals,
                "long_running": long_running,
                "idle_capacity": {"idle": idle, "total": len(agents), "engaged": engaged},
                "workload": {"engaged": engaged, "idle": idle, "total": len(agents)},
            },
        },
        # Increment 3 — Operations Intelligence: the same facts recomposed as actionable insights.
        # Nothing new is measured here; it is a composition of the lists/counts already assembled.
        "insights": {
            "attention_required": {
                "waiting_approvals": waiting_approvals,
                "long_running": long_running,
                "stalled": stalled,
                "queue_hotspots": hotspots,
            },
            "capacity_outlook": {
                "idle": idle,
                "utilized": utilized,
                "total": len(agents),
                "available_agents": available,
                "workload": {"engaged": engaged, "idle": idle, "total": len(agents)},
            },
            "operational_summary": _operational_summary(
                awaiting=awaiting,
                active=len(active_missions),
                utilized=utilized,
                idle=idle,
                blocked=blocked,
                completed=completed,
                ratio_now=utilization["ratio_now"],
            ),
        },
        "journal_present": Path(journal_path).exists(),
    }


def _mission_card(mission: dict[str, object], sessions_by_mission: _Sessions) -> dict[str, object]:
    """An active mission shaped like a Mission card (owner, status, session tally via the shared
    ``session_summary``) so the Executive list and the Missions tab count it identically."""
    mission_id = mission.get("mission_id")
    sessions = sessions_by_mission.get(mission_id, []) if isinstance(mission_id, str) else []
    participants = mission.get("participants")
    return {
        "mission_id": mission_id,
        "status": mission.get("status"),
        "owner": _owner(mission),
        "participants": len(participants) if isinstance(participants, list) else 0,
        **session_summary(sessions),
    }


def _agent_row(agent_dto: dict[str, object], metrics: dict[str, object]) -> dict[str, object]:
    """One row of the org-wide agent-performance table — the per-agent ``agent_metrics`` (completed
    missions, avg duration, decision mix) plus the DTO's current assignment and last activity. No
    new numbers, just the existing metrics arranged as a row that links to the Agent Inspector."""
    return {
        "agent": agent_dto.get("agent"),
        "display_name": agent_dto.get("display_name"),
        "status": metrics.get("status"),
        "completed_missions": metrics.get("missions_completed"),
        "avg_duration_ms": metrics.get("avg_duration_ms"),
        "decision_distribution": metrics.get("decision_distribution"),
        "current_mission_id": agent_dto.get("current_mission_id"),
        "current_step_id": agent_dto.get("current_step_id"),
        "last_activity_at": agent_dto.get("last_activity_at"),
    }


def _long_running(mission: dict[str, object], sessions_by_mission: _Sessions) -> dict[str, object]:
    """An active mission with the start of its earliest still-active session, so the UI can show how
    long it has been running as of now (the frontend does the elapsed math against the wall clock —
    the backend stays deterministic and never guesses a duration)."""
    mission_id = mission.get("mission_id")
    sessions = sessions_by_mission.get(mission_id, []) if isinstance(mission_id, str) else []
    active = [s for s in sessions if s.get("status") == "active"]
    starts = [t for t in (_num_or_none(s.get("started_at")) for s in active) if t is not None]
    return {
        "mission_id": mission_id,
        "status": mission.get("status"),
        "owner": _owner(mission),
        "active_since": min(starts) if starts else None,
    }


def _avg_completion_ms(
    missions: list[dict[str, object]], sessions_by_mission: _Sessions
) -> float | None:
    """Average completion time from COMPLETED missions only — the span from a mission's first
    session start to its last session end. Measured from real session timestamps; ``None`` (→
    "insufficient data") when no completed mission has timed sessions, never estimated."""
    spans: list[float] = []
    for mission in missions:
        if mission.get("status") != "completed":
            continue
        mission_id = mission.get("mission_id")
        sessions = sessions_by_mission.get(mission_id, []) if isinstance(mission_id, str) else []
        starts = [t for t in (_num_or_none(s.get("started_at")) for s in sessions) if t is not None]
        ends = [t for t in (_num_or_none(s.get("ended_at")) for s in sessions) if t is not None]
        if starts and ends:
            spans.append((max(ends) - min(starts)) * 1000.0)
    return (sum(spans) / len(spans)) if spans else None


def _agent_brief(agent_dto: dict[str, object], metrics: dict[str, object]) -> dict[str, object]:
    """A compact agent card for the insights layer (identity, live status, current mission, last
    activity) — everything an attention/capacity item needs to drill into the Agent Inspector."""
    return {
        "agent": agent_dto.get("agent"),
        "display_name": agent_dto.get("display_name"),
        "status": metrics.get("status"),
        "current_mission_id": agent_dto.get("current_mission_id"),
        "current_step_id": agent_dto.get("current_step_id"),
        "last_activity_at": agent_dto.get("last_activity_at"),
    }


def _operational_summary(
    *,
    awaiting: int,
    active: int,
    utilized: int,
    idle: int,
    blocked: int,
    completed: int,
    ratio_now: object,
) -> list[str]:
    """Short declarative sentences composed ONLY from the counts already observed — no
    recommendations, no predictions, nothing inferred. Utilization is "insufficient data" when it
    cannot be measured; zero-valued lines are dropped rather than padded."""
    lines: list[str] = []
    if isinstance(ratio_now, (int, float)) and not isinstance(ratio_now, bool):
        lines.append(f"Fleet utilization is {round(ratio_now * 100)}%.")
    else:
        lines.append("Fleet utilization: insufficient data.")
    if awaiting:
        lines.append(_plural(awaiting, "mission", "awaiting approval"))
    if active:
        lines.append(_plural(active, "mission", "in flight"))
    if utilized:
        lines.append(_plural(utilized, "agent", "currently working"))
    if idle:
        lines.append(_plural(idle, "agent", "currently idle"))
    if blocked:
        lines.append(_plural(blocked, "agent", "blocked"))
    lines.append(_plural(completed, "mission", "completed"))
    return lines


def _plural(count: int, noun: str, tail: str) -> str:
    return f"{count} {noun if count == 1 else noun + 's'} {tail}."


def _status_distribution(fleet: list[dict[str, object]]) -> dict[str, int]:
    """How the roster is distributed across live statuses (working / waiting / idle / blocked …)."""
    return _count_by(m.get("status") for m in fleet)


def _lifecycle_distribution(missions: list[dict[str, object]]) -> dict[str, int]:
    """How observed missions are distributed across lifecycle statuses (created / … / completed)."""
    return _count_by(m.get("status") for m in missions)


def _fleet_decisions(fleet: list[dict[str, object]]) -> dict[str, int]:
    """Sum the per-agent ``decision_distribution`` counts — the additive roll-up the metrics were
    designed for (approve / proceed / request_changes / …)."""
    distribution: dict[str, int] = {}
    for metrics in fleet:
        for verdict, count in _mapping(metrics.get("decision_distribution")).items():
            if isinstance(count, int):
                distribution[verdict] = distribution.get(verdict, 0) + count
    return distribution


def _queue_health(blocked: int, awaiting: int, engaged: int, completed: int) -> str:
    """A blunt queue-health label from live counts (not inferred): work needs a human if anything
    is blocked or awaiting approval; otherwise healthy if anything is moving, else idle."""
    if blocked or awaiting:
        return "attention"
    if engaged or completed:
        return "healthy"
    return "idle"


def _count_by(values: Iterable[object]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        key = value if isinstance(value, str) else "unknown"
        counts[key] = counts.get(key, 0) + 1
    return counts


def _owner(mission: dict[str, object]) -> str | None:
    owner = mission.get("owner")
    return owner.get("key") if isinstance(owner, dict) else None


def _mapping(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _num(value: object) -> float:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0.0


def _num_or_none(value: object) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None
