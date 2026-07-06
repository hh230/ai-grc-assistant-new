"""The Research Planner — pure, deterministic, no LLM (the same design choice ADR-0025 made
for the Knowledge Gap Detector: CLAUDE.md §1 prefers a reproducible, reviewable decision over
a model's judgment wherever one is sufficient).

"Decide where trustworthy information may exist" is answered here as a curated allowlist
match, never an open-ended guess: a source is only ever a candidate if it already appears in
the ``/trusted-sources`` catalog *and* declares the question's domain among the ones it
covers. Candidates are then ordered by a fixed authority ranking, so a law/regulation or a
government regulator is checked before an official guidance document addressing the same
domain.
"""

from __future__ import annotations

from collections.abc import Sequence

from grc_knowledge_intelligence import KnowledgeQuestion, TrustedSourceType

from .models import CatalogedSource, ResearchPlan, ResearchStep

# Lower rank is checked first. A source's own text carries no signal about how binding it is —
# this ordering is a deliberate, reviewable editorial judgment call, not a computed property.
_AUTHORITY_RANK: dict[TrustedSourceType, int] = {
    TrustedSourceType.LAW_REGULATION: 0,
    TrustedSourceType.GOVERNMENT_REGULATOR: 1,
    TrustedSourceType.STANDARDS_BODY: 2,
    TrustedSourceType.OFFICIAL_FRAMEWORK: 3,
    TrustedSourceType.OFFICIAL_GUIDANCE: 4,
}


def build_research_plan(
    question: KnowledgeQuestion, catalog: Sequence[CatalogedSource]
) -> ResearchPlan:
    """Filter the curated catalog to sources tagged for this question's domain, ordered by
    authority. A question whose domain matches nothing in the catalog yields a plan with zero
    steps — a legitimate "nothing trustworthy is cataloged for this yet" outcome, not an
    error; the coordinator reports that as insufficient evidence rather than guessing."""
    matches = [cataloged for cataloged in catalog if question.domain in cataloged.domains]
    ranked = sorted(matches, key=lambda cataloged: _AUTHORITY_RANK[cataloged.source.source_type])
    steps = tuple(
        ResearchStep(source=cataloged, rank=rank) for rank, cataloged in enumerate(ranked)
    )
    return ResearchPlan(question=question, steps=steps)
