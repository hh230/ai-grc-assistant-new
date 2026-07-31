"""The Mission Lifecycle — drive a detected problem from evidence to closure (ADR 0065).

The core (this package) is pure policy: ``LifecycleDriver.advance`` mirrors the squad's
``ChainDriver``, verifying resolution (evidence-cleared + execution-evidence) and climbing a
two-tier escalation ladder (Supervisor → CEO). Connectors, the runtime, and the tick wire the seams.
"""

from __future__ import annotations

from devteam_organization.lifecycle.adapters import (
    Adapter,
    AdapterRegistry,
)
from devteam_organization.lifecycle.composition import (
    EscalateMission,
    LifecycleComposition,
    OpenMission,
    build_lifecycle,
)
from devteam_organization.lifecycle.coordinator import (
    AdvanceSink,
    LifecycleCoordinator,
    LifecycleEvent,
    LifecycleEventKind,
    ProblemRecord,
    ProblemState,
    ProcessedEventLog,
    ResolutionResolver,
    Transition,
    TransitionSink,
    Trigger,
)
from devteam_organization.lifecycle.correlation import (
    ActiveProblem,
    ProblemLedger,
    ProblemSignal,
    Severity,
)
from devteam_organization.lifecycle.driver import (
    EscalationLedger,
    EscalationTier,
    IsFinished,
    LifecycleDriver,
    LifecycleOutcome,
    LifecycleStatus,
    OpenRemediation,
    Problem,
    RaiseEscalation,
    Resolution,
    VerifyProblem,
)
from devteam_organization.lifecycle.emission import (
    ProblemEmitter,
    default_emitters,
    emit_all,
)
from devteam_organization.lifecycle.metrics import (
    LifecycleMetrics,
    LifecycleMetricsSnapshot,
)
from devteam_organization.lifecycle.resolution import (
    Evidence,
    EvidenceResolutionCheck,
    EvidenceSource,
    EvidenceSources,
    EvidenceState,
    ResolutionCheck,
    ResolutionCheckRegistry,
    default_resolution_registry,
)
from devteam_organization.lifecycle.sources import build_evidence_sources
from devteam_organization.lifecycle.strategies import (
    MissionType,
    default_strategies,
    default_strategy_registry,
)
from devteam_organization.lifecycle.strategy import (
    ApprovalPolicy,
    ApprovalRequirement,
    RemediationPlan,
    RemediationPlanner,
    RemediationStrategy,
    StrategyRegistry,
)

__all__ = [
    "ActiveProblem",
    "Adapter",
    "AdapterRegistry",
    "AdvanceSink",
    "ApprovalPolicy",
    "ApprovalRequirement",
    "EscalateMission",
    "EscalationLedger",
    "EscalationTier",
    "Evidence",
    "EvidenceResolutionCheck",
    "EvidenceSource",
    "EvidenceSources",
    "EvidenceState",
    "IsFinished",
    "LifecycleComposition",
    "LifecycleCoordinator",
    "LifecycleDriver",
    "LifecycleEvent",
    "LifecycleEventKind",
    "LifecycleMetrics",
    "LifecycleMetricsSnapshot",
    "LifecycleOutcome",
    "LifecycleStatus",
    "MissionType",
    "ProblemRecord",
    "ProblemState",
    "ProcessedEventLog",
    "ResolutionResolver",
    "Transition",
    "TransitionSink",
    "Trigger",
    "OpenMission",
    "OpenRemediation",
    "Problem",
    "ProblemEmitter",
    "ProblemLedger",
    "ProblemSignal",
    "RaiseEscalation",
    "RemediationPlan",
    "RemediationPlanner",
    "RemediationStrategy",
    "Resolution",
    "ResolutionCheck",
    "ResolutionCheckRegistry",
    "Severity",
    "StrategyRegistry",
    "VerifyProblem",
    "build_evidence_sources",
    "build_lifecycle",
    "default_emitters",
    "default_resolution_registry",
    "default_strategies",
    "default_strategy_registry",
    "emit_all",
]
