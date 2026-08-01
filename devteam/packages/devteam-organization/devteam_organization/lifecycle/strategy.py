"""Remediation as a STRATEGY, not a fixed workflow (ADR 0065, owner principle 2026-07-30).

Mission type is **not** bound to an execution method. A ``RemediationStrategy`` sits between them —
``Mission → Strategy → Execution`` — so the same mission type can be handled several ways by context
(Security via Code Remediation *or* Infrastructure Change; Compliance via Evidence Collection *or* a
Policy Update). And **approval binds to the Strategy + severity, not the mission type**: reading
evidence needs none, a policy update needs the policy owner, a prod merge needs a human, a risk
acceptance needs the CEO/risk owner — ``Mission → Strategy → Approval → Execution``.

This module is the pure abstraction: the ``RemediationStrategy`` protocol, the ``ApprovalPolicy`` it
declares, a ``StrategyRegistry`` (the plugin seam, CLAUDE.md §17), and a ``RemediationPlanner`` that
turns a problem into a ``RemediationPlan``. Concrete strategies are in ``strategies.py``; wiring the
chosen step into the engine is a later slice.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable

from devteam_organization.lifecycle.correlation import ProblemSignal


class ApprovalRequirement(str, Enum):
    """How much authority a remediation needs — from the Strategy + severity, never the mission
    type. Ascending; only ``NONE`` skips the human gate."""

    NONE = "none"  # read-only / safe → no human gate
    OWNER = "owner"  # the asset/policy owner approves
    STANDARD = "standard"  # a human operator approves (the default gate)
    EXECUTIVE = "executive"  # the CEO / risk owner approves


@dataclass(frozen=True)
class ApprovalPolicy:
    """The approval a remediation requires. ``approver`` names the role/owner that decides
    (``policy_owner``, ``risk_owner``, ``ceo``); empty means any authorized human. ``requires_gate``
    maps to the engine's ``PlanStep.consequential`` — a step gates iff its policy demands it."""

    requirement: ApprovalRequirement
    approver: str = ""
    reason: str = ""

    @property
    def requires_gate(self) -> bool:
        return self.requirement is not ApprovalRequirement.NONE

    @classmethod
    def none(cls, reason: str = "") -> ApprovalPolicy:
        return cls(ApprovalRequirement.NONE, reason=reason)

    @classmethod
    def owner(cls, approver: str, reason: str = "") -> ApprovalPolicy:
        return cls(ApprovalRequirement.OWNER, approver=approver, reason=reason)

    @classmethod
    def standard(cls, reason: str = "") -> ApprovalPolicy:
        return cls(ApprovalRequirement.STANDARD, reason=reason)

    @classmethod
    def executive(cls, approver: str = "ceo", reason: str = "") -> ApprovalPolicy:
        return cls(ApprovalRequirement.EXECUTIVE, approver=approver, reason=reason)


@runtime_checkable
class RemediationStrategy(Protocol):
    """A pluggable way to resolve a problem. ``applies_to`` decides whether it fits the problem's
    context (so several strategies can serve one mission type); ``approval_for`` derives approval
    from the Strategy + severity; ``instruction_for`` is the remediation step's instruction."""

    id: str

    def applies_to(self, signal: ProblemSignal) -> bool: ...

    def approval_for(self, signal: ProblemSignal) -> ApprovalPolicy: ...

    def instruction_for(self, signal: ProblemSignal) -> str: ...


@dataclass(frozen=True)
class RemediationPlan:
    """The remediation chosen for a problem: which strategy, what the step does, and the approval it
    needs. ``consequential`` is the engine gate flag — a step gates iff its approval requires it."""

    strategy_id: str
    instruction: str
    approval: ApprovalPolicy

    @property
    def consequential(self) -> bool:
        return self.approval.requires_gate


class StrategyRegistry:
    """The registered strategies (the plugin seam, CLAUDE.md §17). ``select`` returns the first
    whose ``applies_to`` matches — several may serve one mission type, context chooses. Order =
    priority."""

    def __init__(self) -> None:
        self._strategies: list[RemediationStrategy] = []

    def register(self, strategy: RemediationStrategy) -> None:
        self._strategies.append(strategy)

    def strategies(self) -> tuple[RemediationStrategy, ...]:
        return tuple(self._strategies)

    def select(self, signal: ProblemSignal) -> RemediationStrategy | None:
        for strategy in self._strategies:
            if strategy.applies_to(signal):
                return strategy
        return None


class RemediationPlanner:
    """Turn a problem into a remediation plan by selecting a strategy (Mission → Strategy).
    Returns ``None`` when no strategy applies — the problem needs a human, not an automated fix."""

    def __init__(self, registry: StrategyRegistry) -> None:
        self._registry = registry

    def plan(self, signal: ProblemSignal) -> RemediationPlan | None:
        strategy = self._registry.select(signal)
        if strategy is None:
            return None
        return RemediationPlan(
            strategy_id=strategy.id,
            instruction=strategy.instruction_for(signal),
            approval=strategy.approval_for(signal),
        )
