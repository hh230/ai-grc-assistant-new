"""The **Result** View Models (Slice S3) — what the "Result" page renders (the domain calls it a
Deliverable; the user never sees that word). Framework-agnostic dataclasses.

**`ResultView` is stable; `ResultContent` is polymorphic.** The Trust Bar and header/metadata are
always the same shape; the *content* changes per mission type (a Gap Assessment carries coverage +
gaps, a Policy Review will carry something else). So `ResultView` never becomes a God DTO: a new
result type adds a new `ResultContent`, not a field on `ResultView` — "Result adapts to the mission"
in the types themselves. Confidence lives **on each section**, not the Trust Bar.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TrustBar:
    """The universal trust strip — the same for every result, shown first (evidence-first)."""

    evidence_count: int
    human_review: str  # Not required | Pending | Approved | Rejected
    updated_at: float


@dataclass(frozen=True)
class ResultSectionView:
    heading: str
    body: str
    citations: tuple[str, ...]
    confidence: float | None = None  # per-section — shown inside the section, not the Trust Bar


@dataclass(frozen=True)
class GapRowView:
    control_code: str
    control_title: str
    covered: bool
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class CoverageView:
    framework: str
    coverage: float  # share of controls with supporting evidence (Evidence Mapping, not attest.)
    covered_count: int
    total: int
    gaps: tuple[GapRowView, ...]


# --- polymorphic content: one per result family ----------------------------------------


@dataclass(frozen=True)
class GenericContent:
    """The content every mission type can produce: narrative sections + their citations."""

    sections: tuple[ResultSectionView, ...]
    kind: str = "generic"  # discriminator for the client


@dataclass(frozen=True)
class GapAssessmentContent:
    """A Gap Assessment's content: the narrative sections plus the coverage / gaps block."""

    sections: tuple[ResultSectionView, ...]
    coverage: CoverageView
    kind: str = "gap_assessment"


# The union grows as result families are added (VendorAssessmentContent, PolicyReviewContent, …) —
# adding one never touches `ResultView`.
ResultContent = GenericContent | GapAssessmentContent


@dataclass(frozen=True)
class ResultView:
    """Stable shell: identity + Trust Bar + the polymorphic content."""

    mission_id: str
    title: str
    trust: TrustBar
    content: ResultContent
