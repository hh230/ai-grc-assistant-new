"""Value objects for the Policy Hunter matching engine.

Deliberately independent of ``grc_regulatory_intelligence`` and ``grc_persistence_web`` types
— the Tools in ``tools.py`` translate their concrete records into these at the boundary
(CLAUDE.md §15), which is what keeps ``matching.py`` a pure function of plain data.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .enums import GapCategory


@dataclass(frozen=True)
class ObligationSummary:
    """One confirmed regulatory obligation, with enough of its source's provenance to cite."""

    obligation_id: str
    obligation_text: str
    obligation_type: str
    control_domain: str
    severity: str
    suggested_policy_title: str
    classification_confidence: float
    source_id: str
    source_url: str
    source_document_fetched_at: datetime

    def __post_init__(self) -> None:
        if not self.obligation_id.strip():
            raise ValueError("ObligationSummary.obligation_id must not be empty")
        if not self.obligation_text.strip():
            raise ValueError("ObligationSummary.obligation_text must not be empty")
        if self.source_document_fetched_at.tzinfo is None:
            raise ValueError("ObligationSummary.source_document_fetched_at must be tz-aware")


@dataclass(frozen=True)
class PolicySummary:
    """One tenant policy, as seen by the matching engine."""

    policy_id: str
    title: str
    summary: str | None
    status: str
    updated_at: datetime

    def __post_init__(self) -> None:
        if not self.policy_id.strip():
            raise ValueError("PolicySummary.policy_id must not be empty")
        if not self.title.strip():
            raise ValueError("PolicySummary.title must not be empty")
        if self.updated_at.tzinfo is None:
            raise ValueError("PolicySummary.updated_at must be timezone-aware")


@dataclass(frozen=True)
class GapFinding:
    """One coverage gap, with the evidence CLAUDE.md §19 requires: a source regulation, a
    citation, a confidence score, and the matched policy (if any)."""

    obligation_id: str
    gap_category: GapCategory
    source_id: str
    source_url: str
    citation: str
    confidence: float
    matched_policy_id: str | None
    matched_policy_title: str | None
    rationale: str

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("GapFinding.confidence must be within [0, 1]")


@dataclass(frozen=True)
class CoverageScanResult:
    """The complete output of one coverage scan."""

    findings: tuple[GapFinding, ...]
    obligations_scanned: int
    policies_considered: int
