"""Resolution checks — verify a problem is resolved from MULTIPLE evidence sources (ADR 0065).

A resolution check is a **plugin**, one per strategy/domain — never an ``if mission_type ==`` inside
the driver (owner principle, 2026-07-30). Each check combines several evidence sources per its own
policy (**multi-evidence**, owner principle) into the driver's two-part ``Resolution``:

    Execution Evidence  +  Connector Evidence  +  (optional) Human Confirmation

Examples: Code → CI + connector; Infrastructure → connector + runtime; Compliance → evidence +
human; Audit → documentation + human review. Closure still means the ORIGINATING evidence is gone
AND every required success signal holds — "execution finished" alone never closes (§3.3). An
unobservable source is ``UNAVAILABLE`` (never fabricated) and keeps the problem open.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable

from devteam_organization.lifecycle.correlation import ProblemSignal
from devteam_organization.lifecycle.driver import Resolution


class EvidenceState(str, Enum):
    """One evidence source's reading. ``UNAVAILABLE`` (source unreachable) is never treated as
    success — it keeps the problem open, honoring no-fabrication."""

    SATISFIED = "satisfied"  # this signal confirms resolution / success
    UNSATISFIED = "unsatisfied"  # the problem persists, or the fix failed
    UNAVAILABLE = "unavailable"  # the source could not be observed


@dataclass(frozen=True)
class Evidence:
    """One evidence source's contribution to a resolution decision."""

    name: str
    state: EvidenceState
    detail: str = ""

    @classmethod
    def satisfied(cls, name: str, detail: str = "") -> Evidence:
        return cls(name, EvidenceState.SATISFIED, detail)

    @classmethod
    def unsatisfied(cls, name: str, detail: str = "") -> Evidence:
        return cls(name, EvidenceState.UNSATISFIED, detail)

    @classmethod
    def unavailable(cls, name: str, detail: str = "") -> Evidence:
        return cls(name, EvidenceState.UNAVAILABLE, detail)


# An evidence provider: maps a problem to one Evidence reading (a connector re-fetch, a CI check, a
# runtime probe, a human-confirmation lookup). Injected, so the checks are pure and testable.
EvidenceSource = Callable[[ProblemSignal], Evidence]


@runtime_checkable
class ResolutionCheck(Protocol):
    """The plugin the lifecycle uses to verify a problem. Registered per strategy — a new domain is
    a new check, never a branch in the driver. ``id`` is read-only so a frozen check satisfies."""

    @property
    def id(self) -> str: ...

    def resolve(self, signal: ProblemSignal) -> Resolution: ...


@dataclass(frozen=True)
class EvidenceResolutionCheck:
    """Combines a **clearing** source (the originating evidence is gone) with zero or more
    **execution** sources (the remediation succeeded) — the two-part contract over many sources.
    Closure needs the clearing source SATISFIED and every execution source SATISFIED; an UNSATISFIED
    execution source means the fix failed; anything UNAVAILABLE keeps the problem open."""

    id: str
    clearing: EvidenceSource
    execution: tuple[EvidenceSource, ...] = ()

    def resolve(self, signal: ProblemSignal) -> Resolution:
        cleared = self.clearing(signal)
        executed = tuple(source(signal) for source in self.execution)
        detail = "; ".join(f"{ev.name}:{ev.state.value}" for ev in (cleared, *executed))
        if cleared.state is not EvidenceState.SATISFIED:
            return Resolution.pending(detail)  # the originating evidence is not (confirmed) gone
        if not executed:
            return Resolution.cleared(detail)  # human-ops: symptom gone, no exec proof expected
        if any(ev.state is EvidenceState.UNSATISFIED for ev in executed):
            return Resolution.execution_failed(detail)  # the remediation ran but did not succeed
        if all(ev.state is EvidenceState.SATISFIED for ev in executed):
            return Resolution.confirmed(detail)  # evidence gone AND every success signal holds
        return Resolution.pending(detail)  # some execution evidence unavailable → wait


class ResolutionCheckRegistry:
    """Maps a strategy id to its resolution check — plugin lookup, never if/else. A new domain
    registers a new check (CLAUDE.md §17)."""

    def __init__(self) -> None:
        self._by_strategy: dict[str, ResolutionCheck] = {}

    def register(self, strategy_id: str, check: ResolutionCheck) -> None:
        self._by_strategy[strategy_id] = check

    def for_strategy(self, strategy_id: str) -> ResolutionCheck | None:
        return self._by_strategy.get(strategy_id)

    def strategy_ids(self) -> tuple[str, ...]:
        return tuple(self._by_strategy)


@dataclass(frozen=True)
class EvidenceSources:
    """The evidence providers the built-in checks draw on — each maps a problem to an Evidence.
    Injected so the pure checks are testable; the real connector/CI/runtime/human wiring is in S4b.
    Multi-evidence: a check may require several of these together."""

    connector_cleared: EvidenceSource  # the originating signature is absent from a fresh re-fetch
    ci_green: EvidenceSource  # the change's CI / tests pass
    runtime_healthy: EvidenceSource  # the runtime / service is healthy
    evidence_present: EvidenceSource  # required compliance evidence exists
    human_confirmed: EvidenceSource  # a human confirmed the resolution
    documentation_reviewed: EvidenceSource  # the documentation exists and was reviewed


def default_resolution_registry(sources: EvidenceSources) -> ResolutionCheckRegistry:
    """Wire each built-in strategy to its multi-evidence check. A new strategy registers its own —
    no if/else, no driver change. The source per role mirrors the owner's examples."""
    specs: tuple[tuple[str, EvidenceSource, tuple[EvidenceSource, ...]], ...] = (
        ("code_remediation", sources.connector_cleared, (sources.ci_green,)),
        ("infrastructure_change", sources.connector_cleared, (sources.runtime_healthy,)),
        ("evidence_collection", sources.evidence_present, ()),
        ("policy_update", sources.evidence_present, (sources.human_confirmed,)),
        ("documentation", sources.documentation_reviewed, (sources.human_confirmed,)),
        ("risk_acceptance", sources.human_confirmed, ()),
        ("runbook_execution", sources.connector_cleared, (sources.runtime_healthy,)),
    )
    registry = ResolutionCheckRegistry()
    for strategy_id, clearing, execution in specs:
        registry.register(strategy_id, EvidenceResolutionCheck(strategy_id, clearing, execution))
    return registry
