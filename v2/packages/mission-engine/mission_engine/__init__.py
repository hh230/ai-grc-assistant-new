"""Rasheed V2 Mission Engine (Phase 15) — the platform's single top-level unit of governed
work, realized as the smallest production-quality package that satisfies ADR 0042.

A **Mission** is a tenant-owned, goal-directed, resumable, auditable envelope with a
versioned plan and a lifecycle. The **MissionEngine** creates missions and drives them
through `CREATED → PLANNED → EXECUTING → COMPLETED` (the full state machine — incl.
`AWAITING_APPROVAL` — is present, only the happy path is exercised) via two ports:

    ExecutionPort     — the single seam to all step execution (Tools/Agents/pipeline, later)
    MissionStorePort  — the single persistence seam (Postgres store, later)

It emits tenant- and mission-stamped domain events onto the existing Event Bus. It does not
reason, execute capability, resolve tenancy, or persist itself — those live behind the ports
and in later phases. This package is pure domain: no database, no LLM SDK, no framework, no
tool registry.
"""

from mission_engine.adapters import EchoExecutor, InMemoryMissionStore
from mission_engine.approval import ApprovalDecision, ApprovalRequest
from mission_engine.engine import MissionEngine
from mission_engine.errors import (
    ApprovalError,
    IllegalTransition,
    MissionError,
    MissionNotFound,
    PlanError,
    TenantMismatch,
)
from mission_engine.events import (
    MissionApproved,
    MissionAwaitingApproval,
    MissionCancelled,
    MissionCompleted,
    MissionCreated,
    MissionEvent,
    MissionFailed,
    MissionPlanned,
    MissionRejected,
    MissionResumed,
    MissionStepCompleted,
)
from mission_engine.lifecycle import MissionStatus
from mission_engine.mission import Mission
from mission_engine.plan import (
    ExecutionProfile,
    Plan,
    PlanStep,
    single_step_plan,
)
from mission_engine.ports import (
    ExecutionPort,
    MissionStorePort,
    StepRequest,
    StepResult,
)

__all__ = [
    # engine
    "MissionEngine",
    # aggregate
    "Mission",
    # lifecycle (the state enum only; the transition table is internal machinery)
    "MissionStatus",
    # plan
    "Plan",
    "PlanStep",
    "ExecutionProfile",
    "single_step_plan",
    # approval (ADR 0044, Slice 1): value objects owned by the Mission aggregate
    "ApprovalRequest",
    "ApprovalDecision",
    # ports
    "ExecutionPort",
    "MissionStorePort",
    "StepRequest",
    "StepResult",
    # reference adapters (not production implementations)
    "EchoExecutor",
    "InMemoryMissionStore",
    # events
    "MissionEvent",
    "MissionCreated",
    "MissionPlanned",
    "MissionStepCompleted",
    "MissionAwaitingApproval",
    "MissionResumed",
    "MissionApproved",
    "MissionRejected",
    "MissionCompleted",
    "MissionFailed",
    "MissionCancelled",
    # errors
    "MissionError",
    "IllegalTransition",
    "TenantMismatch",
    "MissionNotFound",
    "PlanError",
    "ApprovalError",
]
