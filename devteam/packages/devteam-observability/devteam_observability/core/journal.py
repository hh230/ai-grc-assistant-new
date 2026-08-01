"""The journal — a replaceable TRANSPORT for the runtime event stream (owner constraint).

The daemon and the Dashboard are separate processes, and the in-process bus cannot cross that
boundary. The journal bridges it as pure transport, in one direction only:

    MissionEngine -> Observability -> Journal -> JournalReader -> RuntimeStateView -> Dashboard API

The ``JournalingObserver`` (writer side) appends each ingress runtime fact as one **versioned** JSON
line. The ``JournalReader`` (reader side) rebuilds state by folding those facts back through a fresh
``AgentRuntimeRegistry`` — deterministic replay: same facts in the same order reproduce the same
sessions (ids, tree) and the same derived status. The Dashboard consumes the resulting
``RuntimeStateView`` and NEVER reads the file itself, so the storage format (JSONL today, something
else tomorrow) stays hidden behind this module.

Every record carries ``schema_version`` so a future format change stays backward-compatible: the
reader can recognize an old record and migrate or skip it instead of misreading it.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from devteam_observability.core.events import (
    AgentAssigned,
    AgentCompleted,
    AgentDecisionRecorded,
    AgentHandoffOccurred,
    AgentPhase,
    AgentStarted,
    HandoffSource,
    MissionEventKind,
    MissionObserved,
    RuntimeEvent,
)
from devteam_observability.core.ids import AgentId, AgentSubsystem
from devteam_observability.core.registry import AgentRuntimeRegistry
from devteam_observability.core.session import ArtifactRef
from devteam_observability.core.view import RuntimeStateView

# The journal record schema. Bump when a record's shape changes; the reader keys migration on it.
JOURNAL_SCHEMA_VERSION = 1

# The canonical journal filename — the ONE source of truth the writer (the monitor) and the reader
# (the dashboard) share, so the two never drift onto different files.
JOURNAL_FILENAME = "runtime.jsonl"


class JournalingObserver:
    """Writer side: append each ingress runtime fact to a JSONL journal as one versioned record.
    Realizes ``RuntimeObserver``, so it drops into the fan-out. An append-per-event write keeps a
    reader in another process able to tail it. Derived ``AgentStatusChanged`` events
    are re-derived on replay, so wiring this as an *ingress* observer keeps the journal to facts."""

    def __init__(self, path: Path | str, *, schema_version: int = JOURNAL_SCHEMA_VERSION) -> None:
        self._path = Path(path)
        self._schema_version = schema_version

    def observe(self, event: RuntimeEvent) -> None:
        record = {"schema_version": self._schema_version, "event": event.to_dict()}
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")


Seeder = Callable[[AgentRuntimeRegistry], None]


class JournalReader:
    """Reader side: rebuild runtime state from a journal, hiding the format. ``seed`` runs before
    the fold to register known agents the same way the live runtime did (register() calls are not
    events), so a reconstructed view is byte-identical to the live one — pass the SAME seeder the
    live side used. ``view`` returns the ``RuntimeStateView`` the Dashboard consumes."""

    def __init__(self, path: Path | str, *, seed: Seeder | None = None) -> None:
        self._path = Path(path)
        self._seed = seed

    def replay(self) -> AgentRuntimeRegistry:
        registry = AgentRuntimeRegistry()
        if self._seed is not None:
            self._seed(registry)
        if not self._path.exists():
            return registry
        for line in self._path.read_text(encoding="utf-8").splitlines():
            event = _event_from_line(line)
            if event is not None:
                registry.observe(event)
        return registry

    def view(self) -> RuntimeStateView:
        return RuntimeStateView(self.replay())


def build_view_from_journal(path: Path | str, *, seed: Seeder | None = None) -> RuntimeStateView:
    """The Dashboard-side entry point: a ``RuntimeStateView`` fed by the journal, never the file."""
    return JournalReader(path, seed=seed).view()


# --- reconstruction: a journal record -> the typed event (the inverse of ``event.to_dict()``) ----


def _event_from_line(line: str) -> RuntimeEvent | None:
    stripped = line.strip()
    if not stripped:
        return None
    try:
        record: dict[str, Any] = json.loads(stripped)
    except json.JSONDecodeError:
        # A torn line — the daemon was mid-append when the reader (another process) read the file.
        # Skip it rather than crash the replay; the next read sees the completed line.
        return None
    if record.get("schema_version") != JOURNAL_SCHEMA_VERSION:
        # A record from a different schema version. Only v1 exists today, so anything else is
        # skipped; a real migration for a future version would translate the record here instead.
        return None
    event = record.get("event")
    if not isinstance(event, dict):
        return None
    builder = _EVENT_BUILDERS.get(str(event.get("kind")))
    return builder(event) if builder is not None else None


def _agent(data: Any) -> AgentId | None:
    if not data:
        return None
    return AgentId(AgentSubsystem(data["subsystem"]), str(data["role"]))


def _artifacts(items: Any) -> tuple[ArtifactRef, ...]:
    return tuple(
        ArtifactRef(kind=str(i["kind"]), title=str(i["title"]), media_type=str(i["media_type"]))
        for i in (items or ())
    )


def _assigned(e: dict[str, Any]) -> RuntimeEvent:
    return AgentAssigned(
        mission_id=e["mission_id"],
        tenant_id=e["tenant_id"],
        occurred_at=e["occurred_at"],
        agent=_agent(e.get("agent")),
        step_id=e["step_id"],
    )


def _started(e: dict[str, Any]) -> RuntimeEvent:
    return AgentStarted(
        mission_id=e["mission_id"],
        tenant_id=e["tenant_id"],
        occurred_at=e["occurred_at"],
        agent=_agent(e.get("agent")),
        step_id=e["step_id"],
        phase=AgentPhase(e["phase"]),
    )


def _completed(e: dict[str, Any]) -> RuntimeEvent:
    return AgentCompleted(
        mission_id=e["mission_id"],
        tenant_id=e["tenant_id"],
        occurred_at=e["occurred_at"],
        agent=_agent(e.get("agent")),
        step_id=e["step_id"],
        ok=e["ok"],
        duration_ms=e["duration_ms"],
        verdict=e["verdict"],
        output_summary=e.get("output_summary", ""),
        artifacts=_artifacts(e.get("artifacts")),
        errors=tuple(e.get("errors", ())),
    )


def _handoff(e: dict[str, Any]) -> RuntimeEvent:
    return AgentHandoffOccurred(
        mission_id=e["mission_id"],
        tenant_id=e["tenant_id"],
        occurred_at=e["occurred_at"],
        from_agent=_agent(e.get("from_agent")),
        to_agent=_agent(e.get("to_agent")),
        reason=e["reason"],
        source=HandoffSource(e["source"]),
    )


def _decision(e: dict[str, Any]) -> RuntimeEvent:
    return AgentDecisionRecorded(
        mission_id=e["mission_id"],
        tenant_id=e["tenant_id"],
        occurred_at=e["occurred_at"],
        agent=_agent(e.get("agent")),
        verdict=e["verdict"],
        rationale=e["rationale"],
        confidence=e["confidence"],
    )


def _mission(e: dict[str, Any]) -> RuntimeEvent:
    return MissionObserved(
        mission_id=e["mission_id"],
        tenant_id=e["tenant_id"],
        occurred_at=e["occurred_at"],
        kind=MissionEventKind(e["mission_kind"]),
        agent=_agent(e.get("agent")),
        step_id=e["step_id"],
        detail=e.get("detail", ""),
    )


# Only ingress facts are reconstructed; a derived ``AgentStatusChanged`` has no builder and is
# skipped (the fold re-derives it), so a journal that happens to contain one replays cleanly.
_EVENT_BUILDERS: dict[str, Callable[[dict[str, Any]], RuntimeEvent]] = {
    "AgentAssigned": _assigned,
    "AgentStarted": _started,
    "AgentCompleted": _completed,
    "AgentHandoffOccurred": _handoff,
    "AgentDecisionRecorded": _decision,
    "MissionObserved": _mission,
}
