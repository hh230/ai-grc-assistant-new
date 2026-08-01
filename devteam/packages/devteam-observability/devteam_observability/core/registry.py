"""``AgentRuntimeRegistry`` — the read-model that turns the runtime's event stream into live state.

The projection: it realizes ``RuntimeObserver``, and each ``observe`` folds one fact into per-agent
``AgentRuntimeState`` (the *current live state*: status, active session, aggregates) plus a mission
index (owner, participants, handoff chain, lifecycle status) plus an append-only ledger of
``AgentSession`` records (the *execution history*). Exactly the pattern the Core's
``MissionAuditSink`` uses — a read-model built purely by subscription.

Two model concepts (owner's design):
  * ``AgentRuntimeState`` is what an agent IS right now — it references the ``active_session``.
  * ``AgentSession`` is one execution INSTANCE — opened at ``AgentStarted``, enriched at
    ``AgentDecisionRecorded``, sealed at ``AgentCompleted``, after which it is immutable history.

Status transition rules (the only place status is decided):

    register            -> IDLE (or OFFLINE if a roster member is not composed in)
    AgentAssigned       -> WAITING            (routed to a step, not started)
    AgentStarted        -> WORKING/THINKING   (per phase); opens the active session
    AgentCompleted      -> BLOCKED if verdict in {block, escalate} else IDLE; seals the session
    MissionObserved(awaiting_approval) for the agent's current mission -> WAITING (human gate)
    MissionObserved(completed|failed|cancelled) -> participants -> IDLE; current mission cleared

Handoffs are NOT inferred here: the registry records the explicit ``AgentHandoffOccurred`` events
the adapter emits (their ``source`` says whether the agent declared them or they were observed from
routing). On any status change it records a derived ``AgentStatusChanged`` on the recent-events
feed; it never feeds that back into itself, so the fold stays acyclic.

Reserved forward-compatible states (owner decision): the ``AgentAssigned -> WAITING`` transition,
the ``THINKING`` phase, and the ``OFFLINE`` status are part of the model for future multi-agent
execution but are not produced by today's single DevTeam adapter (which emits WORKING and never
assigns-before-start). They are handled here so a richer runtime plugs in without changing the fold.

Synchronous and lock-free by design: the DevTeam runtime is single-threaded and in-process.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field, replace

from devteam_observability.core.events import (
    AgentAssigned,
    AgentCompleted,
    AgentDecisionRecorded,
    AgentHandoffOccurred,
    AgentPhase,
    AgentStarted,
    AgentStatusChanged,
    MissionEventKind,
    MissionObserved,
    RuntimeEvent,
)
from devteam_observability.core.ids import AgentId, AgentStatus
from devteam_observability.core.session import (
    AgentSession,
    DecisionRecord,
    SessionStatus,
)

# Machine verdicts that mean "a human must step in" — they move an agent to BLOCKED. Kept as lower
# case strings so the core stays free of the Core's ``AgentVerdict`` enum (the adapter passes
# ``verdict.value``).
_BLOCKING_VERDICTS: frozenset[str] = frozenset({"block", "escalate"})

# Terminal mission facts that release an agent back to IDLE and close its current-mission binding.
_TERMINAL_MISSION_KINDS: frozenset[MissionEventKind] = frozenset(
    {MissionEventKind.COMPLETED, MissionEventKind.FAILED, MissionEventKind.CANCELLED}
)

_DEFAULT_HISTORY = 50


def _empty_history() -> deque[DecisionRecord]:
    return deque(maxlen=_DEFAULT_HISTORY)


@dataclass
class AgentRuntimeState:
    """The current live state of one agent — the unit the dashboard renders. Mutated only by the
    registry's fold. ``active_session_id`` references the execution in flight (``None`` when idle);
    resolve it through the registry (``active_session_for`` / ``session``). ``executions`` counts
    sealed sessions; ``completed_missions`` counts distinct missions the agent took part in that
    reached a COMPLETED terminal."""

    agent_id: AgentId
    display_name: str = ""
    status: AgentStatus = AgentStatus.IDLE
    current_mission_id: str | None = None
    current_step_id: str | None = None
    last_activity_at: float | None = None
    executions: int = 0
    completed_missions: int = 0
    active_session_id: str | None = field(default=None, init=False)
    # Accumulators the fold mutates — never constructor args.
    _duration_total_ms: float = field(default=0.0, init=False)
    _history: deque[DecisionRecord] = field(default_factory=_empty_history, init=False)
    _counted_completions: set[str] = field(default_factory=set, init=False)

    @property
    def average_duration_ms(self) -> float:
        """Rolling mean session duration; 0.0 before the first sealed session."""
        return self._duration_total_ms / self.executions if self.executions else 0.0

    @property
    def decision_history(self) -> tuple[DecisionRecord, ...]:
        return tuple(self._history)

    def to_dict(self) -> dict[str, object]:
        # The view adds the resolved ``active_session`` (which carries its own ``session_id``), so
        # the DTO does not repeat the id — the object attribute stays for internal/registry use.
        return {
            "agent": self.agent_id.to_dict(),
            "display_name": self.display_name or self.agent_id.role,
            "status": self.status.value,
            "current_mission_id": self.current_mission_id,
            "current_step_id": self.current_step_id,
            "last_activity_at": self.last_activity_at,
            "executions": self.executions,
            "completed_missions": self.completed_missions,
            "average_duration_ms": self.average_duration_ms,
            "decision_history": [record.to_dict() for record in self.decision_history],
        }


@dataclass
class MissionRuntimeState:
    """The runtime's view of one mission: who owns it, who took part, the handoff chain, and its
    last observed lifecycle status. Powers ``ownership`` and ``mission_flow`` on the view."""

    mission_id: str
    owner: AgentId | None = None
    status: MissionEventKind | None = None
    participants: list[AgentId] = field(default_factory=list)
    handoffs: list[tuple[AgentId, AgentId]] = field(default_factory=list)

    def add_participant(self, agent: AgentId) -> None:
        if agent not in self.participants:
            self.participants.append(agent)
        if self.owner is None:
            self.owner = agent

    def to_dict(self) -> dict[str, object]:
        return {
            "mission_id": self.mission_id,
            "owner": self.owner.to_dict() if self.owner is not None else None,
            "status": self.status.value if self.status is not None else None,
            "participants": [agent.to_dict() for agent in self.participants],
            "handoffs": [
                {"from": src.to_dict(), "to": dst.to_dict()} for src, dst in self.handoffs
            ],
        }


class AgentRuntimeRegistry:
    """The projection. Wire it as a ``RuntimeObserver`` on the runtime's event stream; read live
    state through it or a ``RuntimeStateView``. ``feed_limit`` bounds the recent-events ring."""

    def __init__(self, *, feed_limit: int = 200) -> None:
        self._agents: dict[AgentId, AgentRuntimeState] = {}
        self._missions: dict[str, MissionRuntimeState] = {}
        # Sessions live in one id-keyed store; everything else holds ids. This lets an immutable
        # session be replaced (e.g. to append a child) in exactly one place, and keeps the reads
        # storage-agnostic (a journal replay rebuilds the same store).
        self._sessions: dict[str, AgentSession] = {}
        self._history_ids: list[str] = []
        self._mission_session_ids: dict[str, list[str]] = {}
        self._last_session_by_mission: dict[str, str] = {}
        self._session_seq = 0
        self._feed: deque[RuntimeEvent] = deque(maxlen=feed_limit)

    # --- roster seeding -----------------------------------------------------------------

    def register(
        self,
        agent_id: AgentId,
        *,
        display_name: str = "",
        status: AgentStatus = AgentStatus.IDLE,
    ) -> AgentRuntimeState:
        """Seed a known roster member so it is visible before any activity. Idempotent: re-register
        updates the display name without discarding accumulated state."""
        state = self._agents.get(agent_id)
        if state is None:
            state = AgentRuntimeState(agent_id=agent_id, status=status)
            self._agents[agent_id] = state
        if display_name:
            state.display_name = display_name
        return state

    # --- reads --------------------------------------------------------------------------

    def state_for(self, agent_id: AgentId) -> AgentRuntimeState | None:
        return self._agents.get(agent_id)

    def all_states(self) -> list[AgentRuntimeState]:
        return list(self._agents.values())

    def mission_state(self, mission_id: str) -> MissionRuntimeState | None:
        return self._missions.get(mission_id)

    def all_missions(self) -> list[MissionRuntimeState]:
        return list(self._missions.values())

    def session(self, session_id: str) -> AgentSession | None:
        return self._sessions.get(session_id)

    def active_session_for(self, agent_id: AgentId) -> AgentSession | None:
        state = self._agents.get(agent_id)
        if state is None or state.active_session_id is None:
            return None
        return self._sessions.get(state.active_session_id)

    def completed_sessions(self) -> list[AgentSession]:
        """The immutable execution history, in seal order."""
        return [self._sessions[sid] for sid in self._history_ids]

    def active_sessions(self) -> list[AgentSession]:
        """The sessions currently in flight (one per busy agent)."""
        return [
            self._sessions[s.active_session_id]
            for s in self._agents.values()
            if s.active_session_id is not None
        ]

    def sessions_for_mission(self, mission_id: str) -> list[AgentSession]:
        """A mission's execution timeline: every session opened on it (sealed + in flight) in start
        order — the foundation for a Live Pipeline / dashboard timeline."""
        return [self._sessions[sid] for sid in self._mission_session_ids.get(mission_id, [])]

    def recent_sessions(self, limit: int | None = None) -> list[AgentSession]:
        ids = self._history_ids[-limit:] if limit is not None else self._history_ids
        return [self._sessions[sid] for sid in ids]

    def recent_events(self, limit: int | None = None) -> list[RuntimeEvent]:
        events = list(self._feed)
        return events[-limit:] if limit is not None else events

    # --- the fold (RuntimeObserver) -----------------------------------------------------

    def observe(self, event: RuntimeEvent) -> None:
        """Fold one runtime fact into live state. Dispatches on the event type; unknown event types
        are recorded on the feed but change no state (forward-compatible)."""
        self._feed.append(event)
        if isinstance(event, AgentAssigned):
            self._on_assigned(event)
        elif isinstance(event, AgentStarted):
            self._on_started(event)
        elif isinstance(event, AgentCompleted):
            self._on_completed(event)
        elif isinstance(event, AgentHandoffOccurred):
            self._on_handoff(event)
        elif isinstance(event, AgentDecisionRecorded):
            self._on_decision(event)
        elif isinstance(event, MissionObserved):
            self._on_mission(event)

    # --- handlers -----------------------------------------------------------------------

    def _on_assigned(self, event: AgentAssigned) -> None:
        if event.agent is None:
            return
        state = self._touch(event.agent, event.occurred_at)
        state.current_mission_id = event.mission_id or state.current_mission_id
        state.current_step_id = event.step_id or state.current_step_id
        self._mission(event.mission_id).add_participant(event.agent)
        self._set_status(state, AgentStatus.WAITING, event)

    def _on_started(self, event: AgentStarted) -> None:
        if event.agent is None:
            return
        state = self._touch(event.agent, event.occurred_at)
        state.current_mission_id = event.mission_id or state.current_mission_id
        state.current_step_id = event.step_id or state.current_step_id
        state.active_session_id = self._open_session(event)
        self._mission(event.mission_id).add_participant(event.agent)
        thinking = event.phase is AgentPhase.THINKING
        self._set_status(state, AgentStatus.THINKING if thinking else AgentStatus.WORKING, event)

    def _on_decision(self, event: AgentDecisionRecorded) -> None:
        if event.agent is None:
            return
        state = self._touch(event.agent, event.occurred_at)
        record = DecisionRecord(
            verdict=event.verdict,
            rationale=event.rationale,
            mission_id=event.mission_id,
            occurred_at=event.occurred_at,
            confidence=event.confidence,
        )
        state._history.append(record)
        sid = state.active_session_id
        if sid is not None and sid in self._sessions:
            self._sessions[sid] = replace(self._sessions[sid], decision=record)

    def _on_completed(self, event: AgentCompleted) -> None:
        if event.agent is None:
            return
        state = self._touch(event.agent, event.occurred_at)
        duration = self._duration_ms(self.active_session_for(event.agent), event)
        self._seal_session(state, event, duration)
        state.executions += 1
        state._duration_total_ms += duration
        state.current_step_id = None
        blocked = event.verdict is not None and event.verdict.lower() in _BLOCKING_VERDICTS
        self._set_status(state, AgentStatus.BLOCKED if blocked else AgentStatus.IDLE, event)

    def _on_handoff(self, event: AgentHandoffOccurred) -> None:
        if event.from_agent is None or event.to_agent is None:
            return
        mission = self._mission(event.mission_id)
        mission.add_participant(event.from_agent)
        mission.add_participant(event.to_agent)
        mission.handoffs.append((event.from_agent, event.to_agent))

    def _on_mission(self, event: MissionObserved) -> None:
        mission = self._mission(event.mission_id)
        mission.status = event.kind
        if event.agent is not None:
            mission.add_participant(event.agent)
        if event.kind is MissionEventKind.AWAITING_APPROVAL:
            self._park_current_agents(event, AgentStatus.WAITING)
        elif event.kind in _TERMINAL_MISSION_KINDS:
            self._release_participants(event)

    # --- sessions -----------------------------------------------------------------------

    def _open_session(self, event: AgentStarted) -> str:
        """Open a new ACTIVE session, store it, index it on the mission, and link it to the session
        that last ran the mission (its ``parent`` — the relay predecessor). Returns the new id."""
        assert event.agent is not None
        self._session_seq += 1
        session_id = f"sess-{self._session_seq}"
        parent_id = self._last_session_by_mission.get(event.mission_id)
        self._sessions[session_id] = AgentSession(
            session_id=session_id,
            agent_id=event.agent,
            mission_id=event.mission_id,
            step_id=event.step_id,
            started_at=event.occurred_at,
            status=SessionStatus.ACTIVE,
            parent_session_id=parent_id,
        )
        self._mission_session_ids.setdefault(event.mission_id, []).append(session_id)
        self._last_session_by_mission[event.mission_id] = session_id
        if parent_id is not None:
            self._link_child(parent_id, session_id)
        return session_id

    def _link_child(self, parent_id: str, child_id: str) -> None:
        """Append a child to its parent — the one append-only change a sealed session allows (its
        execution facts stay immutable; only the tree completes as children appear)."""
        parent = self._sessions.get(parent_id)
        if parent is not None:
            self._sessions[parent_id] = replace(
                parent, child_session_ids=(*parent.child_session_ids, child_id)
            )

    def _seal_session(
        self, state: AgentRuntimeState, event: AgentCompleted, duration_ms: float
    ) -> None:
        """Finalize the active session into immutable history. If no session was open (a completion
        with no start — never in the normal flow), synthesize a minimal sealed one so the completion
        is still recorded."""
        assert event.agent is not None
        status = SessionStatus.COMPLETED if event.ok else SessionStatus.FAILED
        sid = state.active_session_id
        if sid is not None and sid in self._sessions:
            self._sessions[sid] = replace(
                self._sessions[sid],
                status=status,
                ended_at=event.occurred_at,
                duration_ms=duration_ms,
                artifacts=event.artifacts,
                output_summary=event.output_summary,
                errors=event.errors,
            )
        else:
            self._session_seq += 1
            sid = f"sess-{self._session_seq}"
            self._sessions[sid] = AgentSession(
                session_id=sid,
                agent_id=event.agent,
                mission_id=event.mission_id,
                step_id=event.step_id,
                started_at=event.occurred_at,
                status=status,
                ended_at=event.occurred_at,
                duration_ms=duration_ms,
                artifacts=event.artifacts,
                output_summary=event.output_summary,
                errors=event.errors,
            )
            self._mission_session_ids.setdefault(event.mission_id, []).append(sid)
        state.active_session_id = None
        self._history_ids.append(sid)

    @staticmethod
    def _duration_ms(session: AgentSession | None, event: AgentCompleted) -> float:
        """Prefer the adapter's measured ``duration_ms``; fall back to the span between the open
        session's start and this completion when the adapter reported none. Never negative."""
        if event.duration_ms > 0:
            return event.duration_ms
        if session is not None:
            return max(0.0, (event.occurred_at - session.started_at) * 1000.0)
        return 0.0

    # --- helpers ------------------------------------------------------------------------

    def _park_current_agents(self, event: MissionObserved, status: AgentStatus) -> None:
        """A human gate paused the mission: move whoever is on it to WAITING."""
        for state in self._agents.values():
            if state.current_mission_id == event.mission_id and state.status in (
                AgentStatus.WORKING,
                AgentStatus.THINKING,
            ):
                self._set_status(state, status, event)

    def _release_participants(self, event: MissionObserved) -> None:
        """The mission reached a terminal: release its participants to IDLE, clear their binding,
        and (for COMPLETED) count it once per agent."""
        completed = event.kind is MissionEventKind.COMPLETED
        for agent in self._mission(event.mission_id).participants:
            state = self._agents.get(agent)
            if state is None:
                continue
            if completed and event.mission_id not in state._counted_completions:
                state._counted_completions.add(event.mission_id)
                state.completed_missions += 1
            # Only release an agent that is actually on THIS mission — one busy on another mission
            # (a possibility a future concurrent runtime allows) keeps its live binding untouched.
            if state.current_mission_id == event.mission_id:
                state.current_mission_id = None
                state.current_step_id = None
                state.last_activity_at = event.occurred_at
                if state.status is not AgentStatus.BLOCKED:
                    self._set_status(state, AgentStatus.IDLE, event)

    def _touch(self, agent_id: AgentId, at: float) -> AgentRuntimeState:
        state = self._agents.get(agent_id)
        if state is None:
            state = self.register(agent_id)
        state.last_activity_at = at
        return state

    def _mission(self, mission_id: str) -> MissionRuntimeState:
        mission = self._missions.get(mission_id)
        if mission is None:
            mission = MissionRuntimeState(mission_id=mission_id)
            self._missions[mission_id] = mission
        return mission

    def _set_status(
        self, state: AgentRuntimeState, status: AgentStatus, cause: RuntimeEvent
    ) -> None:
        """Apply a status and, if it changed, record a derived ``AgentStatusChanged`` on the
        recent-events feed. Never re-enters ``observe``, so the fold stays acyclic."""
        if state.status is status:
            return
        previous = state.status
        state.status = status
        self._feed.append(
            AgentStatusChanged(
                mission_id=cause.mission_id,
                tenant_id=cause.tenant_id,
                occurred_at=cause.occurred_at,
                agent=state.agent_id,
                previous=previous,
                current=status,
            )
        )
