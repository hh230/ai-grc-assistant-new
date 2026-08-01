"""The messages agents exchange — the collaboration protocol's payloads (ADR 0061).

Design rule (owner): start from the messages, not the agent classes; reuse the frozen Core, never
duplicate it. Every payload here is a thin, agent-facing value object that maps onto an existing
Core contract at the engine seam (see ``devteam_protocol.mapping``):

- ``AgentRequest``  is built from a mission-engine ``StepRequest`` (the dispatched step).
- ``AgentResult``   folds down to a ``StepResult``; the richer layer (findings / artifacts /
  decision / handoff) travels the collaboration layer + audit, not the engine seam.
- ``AgentHandoff``  is the typed form of ``StepRequest.prior_results`` (ADR 0051).
- ``AgentDecision`` may make a step consequential → a human ``ApprovalRequest`` (ADR 0044).
- ``AgentFinding``  is ``devteam_contracts.AgentFinding`` (the one finding concept, reused).

``AgentDecision`` is a *machine verdict* — NOT the Core's ``ApprovalDecision`` (a human's gate
resolution, ADR 0044) nor ``DecisionPlan`` (the pipeline's request classification). Three distinct
concepts; this one is the agent's recommendation, which a policy may turn into a human gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from devteam_contracts import AgentFinding
from pipeline_contracts import TenantContext, dataclass_dict

from devteam_protocol.roles import AgentRole


@dataclass(frozen=True)
class AgentArtifact:
    """A work-product an agent produces and hands on: a diff, a report, a test log, or a scan.
    Rich by design (the Core's ``StepResult.output`` is a plain string); the upstream form the v2
    ``deliverables`` package later turns into an exportable deliverable — not a duplicate of it."""

    kind: str
    title: str
    content: str = ""
    media_type: str = "text/plain"
    produced_by: AgentRole | None = None
    source_ids: tuple[str, ...] = ()
    refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.kind or not self.kind.strip():
            raise ValueError("an AgentArtifact must have a non-empty kind")
        object.__setattr__(self, "source_ids", tuple(self.source_ids))
        object.__setattr__(self, "refs", tuple(self.refs))

    def to_dict(self) -> dict[str, object]:
        return dataclass_dict(self)


class AgentVerdict(str, Enum):
    """A machine verdict an agent can reach on the work in hand. A ``BLOCK``/``ESCALATE`` (or any
    consequential recommendation) is what a policy turns into the Core's human gate — the agent
    never self-authorizes a consequential action (CLAUDE.md §9)."""

    PROCEED = "proceed"
    APPROVE = "approve"
    REQUEST_CHANGES = "request_changes"
    BLOCK = "block"
    ESCALATE = "escalate"
    ABSTAIN = "abstain"


@dataclass(frozen=True)
class AgentDecision:
    """An agent's verdict on the work in hand, with its reason — the Reviewer requests changes,
    Security blocks, the Foreman escalates. A recommendation, not an authorization: the Mission
    Engine's human gate (ADR 0044) remains the only thing that authorizes a consequential action."""

    verdict: AgentVerdict
    by_role: AgentRole
    rationale: str = ""
    confidence: float | None = None
    refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "refs", tuple(self.refs))

    def to_dict(self) -> dict[str, object]:
        return dataclass_dict(self)


@dataclass(frozen=True)
class AgentHandoff:
    """One agent passing work to the next — the typed form of what ADR 0051's
    ``StepRequest.prior_results`` carries between steps. The Foreman composes handoffs into an
    ordered Plan; the engine transports each step's output to the next. Carries the artifacts,
    findings, and optional decision the receiving agent needs to continue."""

    from_role: AgentRole
    to_role: AgentRole
    reason: str = ""
    artifacts: tuple[AgentArtifact, ...] = ()
    findings: tuple[AgentFinding, ...] = ()
    decision: AgentDecision | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "artifacts", tuple(self.artifacts))
        object.__setattr__(self, "findings", tuple(self.findings))

    def to_dict(self) -> dict[str, object]:
        return dataclass_dict(self)


@dataclass(frozen=True)
class AgentRequest:
    """A unit of work handed to an agent. Built from the Core ``StepRequest`` the engine dispatched
    (``mapping.agent_request_from_step``), reusing the mission's tenant and identity — never
    re-derived (ADR 0040). ``inbox`` is what a prior agent handed in; ``finding`` is the triggering
    observation; ``consequential`` mirrors the step's gate flag (ADR 0042 §5)."""

    role: AgentRole
    intent: str
    tenant: TenantContext
    mission_id: str = ""
    step_id: str = ""
    consequential: bool = False
    finding: AgentFinding | None = None
    inbox: AgentHandoff | None = None

    def to_dict(self) -> dict[str, object]:
        return dataclass_dict(self)


@dataclass(frozen=True)
class AgentResult:
    """The outcome of an agent's work. Folds down to a Core ``StepResult`` at the engine seam
    (``ok`` / ``output`` / ``source_ids`` / ``confidence`` / ``warnings``, see
    ``mapping.agent_result_to_step``). The richer layer (findings / artifacts / decision /
    handoff) travels agent-to-agent under the Foreman and into the audit trail, never squeezed
    into ``StepResult``."""

    ok: bool = True
    output: str = ""
    findings: tuple[AgentFinding, ...] = ()
    artifacts: tuple[AgentArtifact, ...] = ()
    decision: AgentDecision | None = None
    handoff: AgentHandoff | None = None
    source_ids: tuple[str, ...] = ()
    confidence: float | None = None
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(self, "artifacts", tuple(self.artifacts))
        object.__setattr__(self, "source_ids", tuple(self.source_ids))
        object.__setattr__(self, "warnings", tuple(self.warnings))

    def to_dict(self) -> dict[str, object]:
        return dataclass_dict(self)
