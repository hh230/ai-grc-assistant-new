"""The Mission Detail **View Model** (Slice S2, constraint 2) — framework-agnostic dataclasses.

These carry only what the Work Surface shows, and deliberately omit every implementation detail:
`PlanStep.instruction`/`tool`/`consequential`, `StepResult.source_ids`/`latency_ms`/cost, the
pipeline, and internal state. Plain dataclasses (no Pydantic) so the Application layer stays
free of any web framework; the HTTP host serializes them at the edge.

Each field answers one tab's question: plan → *what will it do?* · findings → *what did it
discover?* (with citations = *why?* and confidence = honesty) · approval → *what decision now?*
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlanStepView:
    id: str
    description: str


@dataclass(frozen=True)
class FindingView:
    step_id: str
    title: str
    summary: str
    citations: tuple[str, ...]
    confidence: float | None = None


@dataclass(frozen=True)
class ApprovalView:
    id: str
    proposed_action: str
    status: str  # "pending" | "approved" | "rejected"


@dataclass(frozen=True)
class MissionDetailView:
    id: str
    type: str
    scope: str
    status: str
    plan: tuple[PlanStepView, ...]
    findings: tuple[FindingView, ...]
    approval: ApprovalView | None
    created_at: float
    updated_at: float
