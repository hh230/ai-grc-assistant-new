"""Shape the Mission Experience (observed mission executions) from the runtime journal.

Like ``agents_view``, this reads the journal ONLY through ``devteam_view_from_journal`` — the frozen
observability read model (``RuntimeStateView``) — and never parses the journal itself. It is pure
presentation shaping: it composes the view's mission + session reads into a mission-card payload the
dashboard renders. No runtime behavior, no business logic.

Increment 3 (Live Pipeline) adds a Server-Sent Events stream (``mission_event_stream``) over the
SAME shaped payload: it re-reads through the view whenever the journal file changes and pushes a
frame only when the payload actually differs, so the timeline becomes live without a new read model
or any runtime logic. The journal's mtime is used only as a cheap change-trigger — never parsed.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path

from devteam_observability import devteam_view_from_journal

# Live-stream tuning. The interval is a poll of the journal's mtime (a stat, not a read); a frame is
# only emitted when the shaped payload changes. Terminal missions end the stream immediately.
_STREAM_INTERVAL_SECONDS = 1.0
_HEARTBEAT_EVERY_TICKS = 15  # emit an SSE comment this often while idle, so proxies keep the socket
_HEARTBEAT_FRAME = ": keep-alive\n\n"
# Mission lifecycle statuses (MissionEventKind values) after which no further sessions can appear.
_TERMINAL_STATUSES = frozenset({"completed", "failed", "cancelled"})


def session_summary(sessions: list[dict[str, object]]) -> dict[str, object]:
    """The session tally for one mission (total / completed / active / failed). Reused by the
    Mission cards, the timeline, and the Executive Experience so a mission is counted the same way
    everywhere (aggregate, don't recompute differently)."""
    statuses = [str(session["status"]) for session in sessions]
    return {
        "session_count": len(sessions),
        "completed": statuses.count("completed"),
        "active": statuses.count("active"),
        "failed": statuses.count("failed"),
    }


def read_pipeline(journal_path: Path | str) -> dict[str, object]:
    """One card per observed mission: its owner, lifecycle status, participants, handoff chain, and
    a session summary (total / completed / active / failed) plus the ordered sessions for the
    timeline. Rebuilt from the journal; an absent journal yields an empty list."""
    view = devteam_view_from_journal(journal_path)
    cards: list[dict[str, object]] = []
    for mission in view.missions():
        sessions = view.mission_sessions(str(mission["mission_id"]))
        cards.append({**mission, **session_summary(sessions), "sessions": sessions})
    return {"missions": cards, "journal_present": Path(journal_path).exists()}


def read_mission(journal_path: Path | str, mission_id: str) -> dict[str, object]:
    """One mission's full detail for the timeline drill-down: its flow (owner, status, participants,
    handoffs) and the ordered ``AgentSession`` records — each already carrying its parent/child
    links, decision, timing, and output. The single-mission shape Increment 3 (Live Pipeline) polls.
    Reads only ``RuntimeStateView.mission_flow`` / ``mission_sessions``; ``found`` is False if the
    journal has not seen this mission."""
    view = devteam_view_from_journal(journal_path)
    flow = view.mission_flow(mission_id)
    if flow is None:
        return {"found": False, "mission_id": mission_id}
    sessions = view.mission_sessions(mission_id)
    return {"found": True, **flow, **session_summary(sessions), "sessions": sessions}


# --- Live Pipeline (Increment 3): a Server-Sent Events stream over the read_mission payload -------


def mission_signature(payload: dict[str, object]) -> str:
    """A stable fingerprint of a mission payload, used to emit a live frame only when something
    actually moved. Deterministic given the journal state (the view is a pure projection), so an
    unchanged mission hashes the same and produces no frame."""
    encoded = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha1(encoded.encode("utf-8"), usedforsecurity=False).hexdigest()


def mission_is_terminal(payload: dict[str, object]) -> bool:
    """True once the mission has reached a lifecycle status after which no more sessions appear —
    the point at which the live stream can close."""
    return bool(payload.get("found")) and payload.get("status") in _TERMINAL_STATUSES


def _journal_mtime(journal_path: Path | str) -> float | None:
    """The journal file's last-modified time as a cheap change-trigger, or ``None`` if it does not
    exist yet. This stats the file; it never opens or parses it — data always comes from the view.
    """
    try:
        return Path(journal_path).stat().st_mtime
    except OSError:
        return None


def _sse_data_frame(payload: dict[str, object]) -> str:
    return f"data: {json.dumps(payload, default=str)}\n\n"


def _sse_done_frame(mission_id: str) -> str:
    return f"event: done\ndata: {json.dumps({'mission_id': mission_id})}\n\n"


async def mission_event_stream(
    journal_path: Path | str,
    mission_id: str,
    *,
    is_disconnected: Callable[[], Awaitable[bool]] | None = None,
    interval: float = _STREAM_INTERVAL_SECONDS,
    max_ticks: int | None = None,
) -> AsyncIterator[str]:
    """Stream one mission's timeline as Server-Sent Events.

    Emits the current ``read_mission`` payload immediately, then re-emits it whenever the journal
    file changes AND the shaped payload actually differs (client patches only what moved). Sends an
    ``event: done`` and stops once the mission is terminal. Every payload comes from the frozen
    ``RuntimeStateView`` via ``read_mission``; the journal's mtime is only a trigger, never parsed.

    ``is_disconnected`` (Starlette's ``request.is_disconnected``) ends the stream when the client
    goes away; ``max_ticks`` bounds an otherwise-endless non-terminal stream for tests.
    """
    last_signature: str | None = None
    last_mtime: float | None = None
    idle_ticks = 0
    ticks = 0
    while True:
        if is_disconnected is not None and await is_disconnected():
            return
        mtime = _journal_mtime(journal_path)
        if last_signature is None or mtime != last_mtime:
            last_mtime = mtime
            payload = await asyncio.to_thread(read_mission, journal_path, mission_id)
            signature = mission_signature(payload)
            if signature != last_signature:
                last_signature = signature
                idle_ticks = 0
                yield _sse_data_frame(payload)
                if mission_is_terminal(payload):
                    yield _sse_done_frame(mission_id)
                    return
            else:
                idle_ticks += 1
        else:
            idle_ticks += 1
        if idle_ticks and idle_ticks % _HEARTBEAT_EVERY_TICKS == 0:
            yield _HEARTBEAT_FRAME
        ticks += 1
        if max_ticks is not None and ticks >= max_ticks:
            return
        if interval:
            await asyncio.sleep(interval)
