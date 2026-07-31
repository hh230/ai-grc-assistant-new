"""Read the runtime observability journal and shape it for the Agents panel.

This is the ONLY place the dashboard touches observability, and it does so exactly the way the
design requires: it reads the journal solely through ``devteam_view_from_journal``, which returns a
``RuntimeStateView`` — the dashboard never parses the journal file itself, so the storage format
stays replaceable behind that seam.

Presentation-only, like the rest of the dashboard: no runtime behavior, just a read + a reshape.
"""

from __future__ import annotations

import statistics
from pathlib import Path

from devteam_observability import devteam_view_from_journal

# How far back to scan the view's recent-session history when slicing one agent's timeline. Ample
# for a dev-team's volumes; the sessions are the frozen view's, filtered here (presentation only).
_AGENT_HISTORY_LIMIT = 500
# Below this many timed sessions a median is not meaningful — surfaced as "insufficient data",
# never fabricated (owner constraint: do not infer or estimate missing information).
_MEDIAN_MIN_SESSIONS = 3
_RECENT_MISSIONS_LIMIT = 5
_UTILIZED_STATUSES = frozenset({"working", "thinking"})  # actively executing right now
_SEALED_STATUSES = frozenset({"completed", "failed"})  # a finished session carries a duration


def read_agents(journal_path: Path | str) -> dict[str, object]:
    """The Agents-panel payload, rebuilt from the journal: the roster with its live state, the
    recent session pipeline (execution timeline), mission ownership, and the observed missions. If
    the daemon has not written the journal yet, the view is the seeded (idle) roster — so the panel
    still shows the whole six-agent team, marked as not-yet-active."""
    view = devteam_view_from_journal(journal_path)
    return {
        "agents": view.agents(),
        "sessions": view.recent_sessions(50),
        "ownership": view.ownership(),
        "missions": view.missions(),
        "journal_path": str(journal_path),
        "journal_present": Path(journal_path).exists(),
    }


def read_agent(journal_path: Path | str, agent_key: str) -> dict[str, object]:
    """One agent's detail for the Agent Inspector drill-down (Agent Cards -> Agent Inspector).

    Its live-state DTO (identity, status, current mission/step, active session, aggregates, decision
    history) plus that agent's own execution timeline: the sessions it ran, oldest first, with the
    in-flight one (if any) appended so the timeline shows the live step too. The timeline reuses the
    same session shape the Mission Experience renders, so a session links back to its mission and an
    agent's work reads the same everywhere. Reads only ``RuntimeStateView`` (``agents`` +
    ``recent_sessions``); the per-agent slice is a presentation filter, not a runtime query.
    ``found`` is False when the roster has no such agent key."""
    view = devteam_view_from_journal(journal_path)
    present = Path(journal_path).exists()
    match = next((dto for dto in view.agents() if _dict_key(dto.get("agent")) == agent_key), None)
    if match is None:
        return {"found": False, "agent_key": agent_key, "journal_present": present}
    recent = view.recent_sessions(_AGENT_HISTORY_LIMIT)
    by_id: dict[object, dict[str, object]] = {s.get("session_id"): s for s in recent}
    sessions = agent_sessions(recent, by_id, match)
    return {
        "found": True,
        **match,
        "sessions": sessions,
        "metrics": agent_metrics(match, sessions),
        "journal_present": present,
    }


def agent_sessions(
    recent: list[dict[str, object]],
    by_id: dict[object, dict[str, object]],
    agent_dto: dict[str, object],
) -> list[dict[str, object]]:
    """One agent's sessions, oldest-first, from a pre-materialized recent-session list: its sealed
    history (filtered) plus its in-flight session appended, each tagged with ``handoff_from``. A
    reusable primitive — ``read_agent`` and the Executive Experience both build the same per-agent
    session set from one ``recent_sessions`` read."""
    agent_key = _dict_key(agent_dto.get("agent"))
    sessions = [s for s in recent if _dict_key(s.get("agent")) == agent_key]
    active = agent_dto.get("active_session")
    if isinstance(active, dict) and active.get("session_id") not in by_id:
        sessions.append(active)
    for session in sessions:
        _attach_handoff_from(session, by_id, agent_key)
    return sessions


def agent_metrics(agent: dict[str, object], sessions: list[dict[str, object]]) -> dict[str, object]:
    """Operational metrics for one agent, derived purely from its RuntimeStateView sessions + DTO.
    Every field is either measured from the data or ``None`` — nothing is inferred or estimated
    (a median needs ``_MEDIAN_MIN_SESSIONS`` timed sessions; active/idle needs a measurable span).

    The shape is additive by design so a future Executive Dashboard can aggregate a fleet WITHOUT a
    new data model: sum ``session_count`` / ``active_ms`` / ``idle_ms`` / ``missions_*`` and the
    ``decision_distribution`` counts across agents, then recompute fleet averages from those raw
    totals (per-agent ``avg`` / ``median`` are display-only and never summed). This is a pure
    function of the agent DTO + its sessions, so the Executive Dashboard can call it per agent."""
    sealed = [s for s in sessions if s.get("status") in _SEALED_STATUSES]
    durations = [d for d in (_as_float(s.get("duration_ms")) for s in sealed) if d is not None]
    starts = [t for t in (_as_float(s.get("started_at")) for s in sealed) if t is not None]
    ends = [t for t in (_as_float(s.get("ended_at")) for s in sealed) if t is not None]
    active_ms = sum(durations)
    # The observed window (first start -> last end) in ms; active is time executing, idle the gaps.
    span_ms = (max(ends) - min(starts)) * 1000.0 if starts and ends else None
    idle_ms = max(0.0, span_ms - active_ms) if span_ms is not None else None
    raw_status = agent.get("status")
    status = raw_status if isinstance(raw_status, str) else None
    mission_ids = {m for m in (s.get("mission_id") for s in sessions) if isinstance(m, str)}
    return {
        "utilized": status in _UTILIZED_STATUSES,
        "status": status,
        "session_count": len(sealed),
        "active_ms": active_ms,
        "idle_ms": idle_ms,
        "span_ms": span_ms,
        "utilization_ratio": (active_ms / span_ms) if span_ms else None,
        "avg_duration_ms": (active_ms / len(durations)) if durations else None,
        "median_duration_ms": (
            statistics.median(durations) if len(durations) >= _MEDIAN_MIN_SESSIONS else None
        ),
        "median_min_sessions": _MEDIAN_MIN_SESSIONS,
        "decision_distribution": _decision_distribution(sessions),
        "missions_worked": len(mission_ids),
        "missions_completed": _as_int(agent.get("completed_missions")),
        "recent_missions": _recent_missions(sessions),
        "queue": _queue_participation(agent, status),
    }


def _decision_distribution(sessions: list[dict[str, object]]) -> dict[str, int]:
    """Counts of the agent's verdicts across the observed sessions (approve / proceed /
    request_changes / …). Additive: fleet distribution is the per-agent sum."""
    distribution: dict[str, int] = {}
    for session in sessions:
        verdict = _session_verdict(session)
        if verdict is not None:
            distribution[verdict] = distribution.get(verdict, 0) + 1
    return distribution


def _recent_missions(sessions: list[dict[str, object]]) -> list[dict[str, object]]:
    """The agent's most-recently-touched distinct missions (newest first) with its verdict + the
    session status — the cross-link into Mission Experience. Sessions arrive oldest-first."""
    seen: set[str] = set()
    entries: list[dict[str, object]] = []
    for session in reversed(sessions):
        mission_id = session.get("mission_id")
        if isinstance(mission_id, str) and mission_id not in seen:
            seen.add(mission_id)
            ended = _as_float(session.get("ended_at"))
            entries.append(
                {
                    "mission_id": mission_id,
                    "verdict": _session_verdict(session),
                    "status": session.get("status"),
                    "at": ended if ended is not None else _as_float(session.get("started_at")),
                }
            )
            if len(entries) >= _RECENT_MISSIONS_LIMIT:
                break
    return entries


def _queue_participation(agent: dict[str, object], status: str | None) -> dict[str, object]:
    """The agent's current mission binding — its 'queue' in the single-threaded runtime (at most one
    mission in hand). ``participating`` is False when idle/unbound; the Executive Dashboard sums it
    for a live 'agents engaged' count."""
    mission_id = agent.get("current_mission_id")
    step_id = agent.get("current_step_id")
    return {
        "participating": bool(mission_id) or status in _UTILIZED_STATUSES or status == "waiting",
        "mission_id": mission_id if isinstance(mission_id, str) else None,
        "step_id": step_id if isinstance(step_id, str) else None,
        "status": status,
    }


def _session_verdict(session: dict[str, object]) -> str | None:
    decision = session.get("decision")
    if isinstance(decision, dict):
        verdict = decision.get("verdict")
        if isinstance(verdict, str):
            return verdict
    return None


def _as_float(value: object) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _as_int(value: object) -> int:
    return int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0


def _attach_handoff_from(
    session: dict[str, object], by_id: dict[object, dict[str, object]], agent_key: str | None
) -> None:
    """Tag a session with ``handoff_from`` (the predecessor's agent) when it followed a session run
    by a DIFFERENT agent — so the agent timeline shows '⇄ from X'. A presentation join over the
    view's recent sessions: the parent (a sealed relay predecessor) is already in that set."""
    parent = by_id.get(session.get("parent_session_id"))
    if isinstance(parent, dict):
        parent_agent = parent.get("agent")
        if _dict_key(parent_agent) not in (None, agent_key):
            session["handoff_from"] = parent_agent


def _dict_key(agent: object) -> str | None:
    """The ``key`` off an agent sub-dict (from a session or agent DTO), or ``None``."""
    if isinstance(agent, dict):
        key = agent.get("key")
        if isinstance(key, str):
            return key
    return None
