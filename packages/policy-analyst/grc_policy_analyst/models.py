"""Value objects for the Policy Analyst quality engine.

Deliberately independent of ``grc_persistence_web``/``grc_regulatory_intelligence`` types —
the Tool in ``tools.py`` translates concrete records into these at the boundary (CLAUDE.md
§15), which is what keeps ``quality_engine.py`` a pure function of plain data.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .enums import FindingType, Severity


@dataclass(frozen=True)
class PolicyDocument:
    """The policy under review."""

    policy_id: str
    title: str
    summary: str | None
    body: str | None
    status: str
    owner_name: str
    updated_at: datetime

    def __post_init__(self) -> None:
        if not self.policy_id.strip():
            raise ValueError("PolicyDocument.policy_id must not be empty")
        if not self.title.strip():
            raise ValueError("PolicyDocument.title must not be empty")
        if self.updated_at.tzinfo is None:
            raise ValueError("PolicyDocument.updated_at must be timezone-aware")


@dataclass(frozen=True)
class RelatedObligation:
    """One confirmed regulatory obligation, candidate for being "about" the policy under
    review — the engine itself decides relevance (see ``quality_engine._is_relevant``)."""

    obligation_id: str
    obligation_text: str
    suggested_policy_title: str
    control_domain: str
    source_id: str
    source_url: str
    source_document_fetched_at: datetime

    def __post_init__(self) -> None:
        if not self.obligation_id.strip():
            raise ValueError("RelatedObligation.obligation_id must not be empty")
        if not self.obligation_text.strip():
            raise ValueError("RelatedObligation.obligation_text must not be empty")
        if self.source_document_fetched_at.tzinfo is None:
            raise ValueError("RelatedObligation.source_document_fetched_at must be tz-aware")


@dataclass(frozen=True)
class QualityFinding:
    """One quality issue, with the evidence CLAUDE.md §19 requires: what was found, where it
    comes from, how confident the check is, and a concrete recommendation — never a bare
    assertion."""

    finding_type: FindingType
    severity: Severity
    evidence: str
    citation: str
    recommendation: str
    confidence: float
    related_obligation_id: str | None = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("QualityFinding.confidence must be within [0, 1]")
        if not self.evidence.strip():
            raise ValueError("QualityFinding.evidence must not be empty")
        if not self.recommendation.strip():
            raise ValueError("QualityFinding.recommendation must not be empty")


@dataclass(frozen=True)
class PolicyQualityReport:
    """The complete output of one policy's quality review."""

    policy_id: str
    findings: tuple[QualityFinding, ...]
    obligations_considered: int
