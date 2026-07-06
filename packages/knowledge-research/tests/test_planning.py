"""Unit tests for ``build_research_plan``: pure domain-tag matching, ordered by a fixed
authority ranking, no LLM, no I/O."""

from __future__ import annotations

from grc_knowledge_intelligence import (
    KnowledgeDomain,
    KnowledgeQuestion,
    TrustedSource,
    TrustedSourceType,
)
from grc_knowledge_research import CatalogedSource, build_research_plan

_QUESTION = KnowledgeQuestion(
    question_id="vendor_management.contract_clauses",
    question="What clauses should exist in a vendor contract?",
    domain=KnowledgeDomain.VENDOR_MANAGEMENT,
    category="contract_requirements",
)


def _source(source_id: str, source_type: TrustedSourceType) -> TrustedSource:
    return TrustedSource(
        source_id=source_id,
        name=source_id,
        source_type=source_type,
        url=f"https://{source_id}.example.gov",
        jurisdiction="SA",
    )


def test_build_research_plan_excludes_sources_not_tagged_for_the_question_domain() -> None:
    catalog = (
        CatalogedSource(
            source=_source("sa-nca", TrustedSourceType.GOVERNMENT_REGULATOR),
            domains=(KnowledgeDomain.CYBERSECURITY_GOVERNANCE,),
        ),
    )

    plan = build_research_plan(_QUESTION, catalog)

    assert plan.steps == ()


def test_build_research_plan_orders_matches_by_authority_rank() -> None:
    guidance = CatalogedSource(
        source=_source("official-guidance", TrustedSourceType.OFFICIAL_GUIDANCE),
        domains=(KnowledgeDomain.VENDOR_MANAGEMENT,),
    )
    law = CatalogedSource(
        source=_source("the-law", TrustedSourceType.LAW_REGULATION),
        domains=(KnowledgeDomain.VENDOR_MANAGEMENT,),
    )
    regulator = CatalogedSource(
        source=_source("the-regulator", TrustedSourceType.GOVERNMENT_REGULATOR),
        domains=(KnowledgeDomain.VENDOR_MANAGEMENT,),
    )
    # Deliberately cataloged out of authority order, to prove the plan re-sorts them.
    catalog = (guidance, law, regulator)

    plan = build_research_plan(_QUESTION, catalog)

    assert [step.source.source.source_id for step in plan.steps] == [
        "the-law",
        "the-regulator",
        "official-guidance",
    ]
    assert [step.rank for step in plan.steps] == [0, 1, 2]


def test_build_research_plan_is_empty_for_an_empty_catalog() -> None:
    plan = build_research_plan(_QUESTION, ())

    assert plan.question == _QUESTION
    assert plan.steps == ()
