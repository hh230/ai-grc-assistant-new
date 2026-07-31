"""AI Organization Jobs — recurring departmental responsibilities on the existing runtime (§11).

Each agent owns recurring jobs that run on a schedule and obtain evidence from connectors
(via the registry) — never a direct integration. A job opens a real Mission only when a connector
returns real evidence. The scheduler runs inside the existing service; missions flow through the
existing Mission Engine; job telemetry lands beside the existing journal; the Dashboard shows
it. No new runtime/service.
"""

from devteam_organization.jobs.framework import (
    ExecutionResult,
    Job,
    JobContext,
    JobHealth,
    JobResult,
    JobState,
    MissionGate,
    MissionRequest,
    Observation,
    Schedule,
)
from devteam_organization.jobs.journal import (
    FileJobJournal,
    JobEvent,
    JobEventKind,
    JobJournalSink,
    NullJobJournal,
    read_jobs_snapshot,
)
from devteam_organization.jobs.scheduler import (
    JobRun,
    JobScheduler,
    open_mission_via_runtime,
)
from devteam_organization.jobs.wiring import build_default_jobs, build_scheduler

__all__ = [
    "ExecutionResult",
    "FileJobJournal",
    "Job",
    "JobContext",
    "JobEvent",
    "JobEventKind",
    "JobHealth",
    "JobJournalSink",
    "JobResult",
    "JobRun",
    "JobScheduler",
    "JobState",
    "MissionGate",
    "MissionRequest",
    "NullJobJournal",
    "Observation",
    "Schedule",
    "build_default_jobs",
    "build_scheduler",
    "open_mission_via_runtime",
    "read_jobs_snapshot",
]
