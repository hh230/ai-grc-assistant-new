"""The roster-neutral observability core — the extension seam (owner constraint).

Nothing in this subpackage imports any agent system. It defines *what an observable agent runtime
looks like* — an identity (``AgentId``), a status vocabulary (``AgentStatus``), the facts a runtime
emits (``RuntimeEvent`` and its subclasses), the one seam those facts travel through
(``RuntimeObserver``), the read-model that folds them into live per-agent state
(``AgentRuntimeRegistry`` / ``AgentRuntimeState``), and the read API a dashboard consumes
(``RuntimeStateView``).

Because the core commits to no concrete agent system, a new one (e.g. the GRC product agents, out
of scope this milestone) is integrated later by writing an *adapter* that maps its roles to
``AgentId`` and its activity to ``RuntimeEvent``s — the projection, the view, and the events below
never change. That is the "extensible without redesign" contract.
"""

from __future__ import annotations

from devteam_observability.core.events import (
    AgentAssigned,
    AgentCompleted,
    AgentDecisionRecorded,
    AgentHandoffOccurred,
    AgentPhase,
    AgentStarted,
    AgentStatusChanged,
    HandoffSource,
    MissionEventKind,
    MissionObserved,
    RuntimeEvent,
    now,
)
from devteam_observability.core.ids import AgentId, AgentStatus, AgentSubsystem
from devteam_observability.core.journal import (
    JOURNAL_FILENAME,
    JOURNAL_SCHEMA_VERSION,
    JournalingObserver,
    JournalReader,
    build_view_from_journal,
)
from devteam_observability.core.observer import CompositeObserver, RuntimeObserver
from devteam_observability.core.registry import (
    AgentRuntimeRegistry,
    AgentRuntimeState,
    MissionRuntimeState,
)
from devteam_observability.core.session import (
    AgentSession,
    ArtifactRef,
    DecisionRecord,
    SessionStatus,
)
from devteam_observability.core.view import RuntimeStateView

__all__ = [
    "AgentAssigned",
    "AgentCompleted",
    "AgentDecisionRecorded",
    "AgentHandoffOccurred",
    "AgentId",
    "AgentPhase",
    "AgentRuntimeRegistry",
    "AgentRuntimeState",
    "AgentSession",
    "AgentStarted",
    "AgentStatus",
    "AgentStatusChanged",
    "AgentSubsystem",
    "ArtifactRef",
    "CompositeObserver",
    "DecisionRecord",
    "HandoffSource",
    "JOURNAL_FILENAME",
    "JOURNAL_SCHEMA_VERSION",
    "JournalReader",
    "JournalingObserver",
    "MissionEventKind",
    "MissionObserved",
    "MissionRuntimeState",
    "RuntimeEvent",
    "RuntimeObserver",
    "RuntimeStateView",
    "SessionStatus",
    "build_view_from_journal",
    "now",
]
