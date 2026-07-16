"""Builders for the reused pipeline contracts, so tests read as scenarios not plumbing."""

from __future__ import annotations

from pipeline_contracts import (
    Answer,
    BlockRole,
    Citation,
    ContextBlock,
    ContextPackage,
    ContextSection,
    ResponseContract,
    TokenBudget,
)


def make_citation(n: int) -> Citation:
    return Citation(
        source_filename=f"doc_{n}.pdf",
        category="regulation",
        document_profile="regulation",
        structure_profile="clause",
        code=f"C-{n}",
        title=f"Clause {n}",
        heading_path=(f"Part {n}",),
        page_start=n,
        page_end=n,
        formatted=f"doc_{n}.pdf — C-{n} Clause {n} — p. {n}",
    )


def make_block(n: int) -> ContextBlock:
    return ContextBlock(
        block_id=f"b{n}",
        document_id=f"doc_{n}",
        role=BlockRole.REQUIREMENT,
        text=f"Requirement {n} text.",
        citation=make_citation(n),
        heading_path=(f"Part {n}",),
        page_start=n,
        page_end=n,
        code=f"C-{n}",
        document_profile="regulation",
        score=0.9,
        confidence=0.8,
        token_count=10,
    )


def make_context(block_count: int) -> ContextPackage:
    """A ContextPackage with `block_count` citable blocks (markers [S1]..[S<n>])."""
    section = ContextSection(
        title="Requirements & Regulations",
        role=BlockRole.REQUIREMENT,
        blocks=[make_block(n) for n in range(1, block_count + 1)],
    )
    return ContextPackage(
        query="What does the regulation require?",
        workflow="lookup",
        budget=TokenBudget(max_tokens=4000, used_tokens=block_count * 10),
        sections=[section] if block_count else [],
    )


def make_answer(text: str) -> Answer:
    return Answer(text=text, provider="scripted", model="fake-1", finish_reason="stop",
                  usage={"total_tokens": 42})


def make_contract(
    *,
    required_citations: bool = True,
    required_confidence: bool = False,
    required_sections: tuple[str, ...] = (),
) -> ResponseContract:
    return ResponseContract(
        workflow="lookup",
        required_sections=required_sections,
        required_citations=required_citations,
        citation_style="bracketed markers like [S1]",
        required_formatting=(),
        required_confidence=required_confidence,
        forbidden_outputs=("legal advice",),
    )
