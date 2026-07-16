"""Decision contracts — the shapes that flow into and out of the Decision Engine.

`UserRequest` is the pipeline's entry value object; `DecisionPlan` is the structured,
fully explainable description of *how* a request should be handled (classify → select
workflow → route → budget → govern → emit plan). These are contracts only: the rules that
*produce* a plan live in the decision-engine package.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from pipeline_contracts.serialization import dataclass_dict
from pipeline_contracts.tenancy import TenantContext


class Intent(str, Enum):
    """The request class — the task the user wants done, not a search strategy.

    The thirteen core GRC classes from the architecture, plus the two first-class
    non-answer outcomes (`AMBIGUOUS`, `UNSUPPORTED`) — a GRC platform must know when to ask
    and when to decline, rather than guess."""

    LOOKUP = "lookup"
    EXPLANATION = "explanation"
    COMPARISON = "comparison"
    COMPLIANCE_REVIEW = "compliance_review"
    POLICY_REVIEW = "policy_review"
    OBLIGATION_EXTRACTION = "obligation_extraction"
    RISK_ANALYSIS = "risk_analysis"
    GAP_ASSESSMENT = "gap_assessment"
    CONTROL_MAPPING = "control_mapping"
    CROSS_FRAMEWORK_MAPPING = "cross_framework_mapping"
    SUMMARIZATION = "summarization"
    DOCUMENT_ANALYSIS = "document_analysis"
    CONVERSATION = "conversation"
    # first-class non-answer outcomes
    AMBIGUOUS = "ambiguous"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class UserRequest:
    """The pipeline's entry contract. `query` is the raw user text (Arabic or English).
    `has_document` flags that an attachment accompanies the request (drives document-analysis
    routing).

    `tenant` is **required** (ADR 0040 §4): a request must name the tenant it serves, and the
    tenant enters here — from the verified identity, never from the payload (§3). It is carried
    downstream, never re-derived or widened."""

    query: str
    tenant: TenantContext
    has_document: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, object], *, tenant: TenantContext) -> UserRequest:
        """Build from a plain payload plus a `TenantContext` supplied by the trusted caller.
        The tenant is a **separate, required argument** — it is never read from `data`, because
        the request body is untrusted input and may not name a tenant (ADR 0040 §3)."""
        return cls(
            query=str(data.get("query", "")),
            tenant=tenant,
            has_document=bool(data.get("has_document", False)),
        )


@dataclass(frozen=True)
class DecisionPlan:
    """The output — a structured, explainable plan. `reason` and the `detected_frameworks`
    / `matched_cues` fields make every decision traceable to the rules that produced it.

    `intent` (and `secondary_intents`) carry the typed `Intent` enum through the whole
    pipeline; string inputs are coerced on construction for compatibility, and
    serialization to plain strings happens only at the JSON boundary (`to_dict`)."""

    intent: Intent
    workflow: str
    requires_retrieval: bool
    requires_document: bool
    requires_reranker: bool
    requires_human_gate: bool
    multi_step: bool
    retrieval_passes: int
    context_budget: int
    target_profiles: list[str]
    confidence: float
    reason: str
    # explainability extras
    detected_frameworks: list[str] = field(default_factory=list)
    secondary_intents: list[Intent] = field(default_factory=list)
    matched_cues: list[str] = field(default_factory=list)
    language: str = "en"

    def __post_init__(self) -> None:
        # Best-effort coercion so callers constructing from plain strings (JSON, tests,
        # older code) still yield a typed plan; unknown values pass through unchanged.
        object.__setattr__(self, "intent", _as_intent(self.intent))
        object.__setattr__(
            self, "secondary_intents", [_as_intent(s) for s in self.secondary_intents]
        )

    def to_dict(self) -> dict[str, object]:
        return dataclass_dict(self)


def _as_intent(value: Intent | str) -> Intent | str:
    if isinstance(value, Intent):
        return value
    try:
        return Intent(str(value))
    except ValueError:
        return value
