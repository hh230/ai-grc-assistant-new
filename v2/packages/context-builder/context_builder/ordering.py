"""Ordering & sectioning — impose a workflow-appropriate structure; never echo retrieval
order blindly.

Two levels:

1. **Section order (workflow priority).** Each workflow arranges *roles* differently:
   compliance review leads with evidence, gap assessment leads with requirements, policy
   review is policy-then-regulation, comparison splits into the two sides being compared,
   lookup collapses to the single smallest context, document analysis is the attachment
   only. This is the "different workflows need different context strategies" rule.

2. **Order within a section.** By retrieval score first, then document hierarchy (documents
   grouped, strongest first), then heading path and page — i.e. near-equal hits fall into
   natural reading order, and an expanded parent sits just above its child.
"""

from __future__ import annotations

# The per-workflow ordering policies are intent behaviour, so they live in the shared
# Intent Registry (pipeline_contracts.intent_registry) — one source of truth. This module
# keeps the ordering *algorithm* plus the historic `OrderingPolicy` / `POLICIES` /
# `policy_for` names.
from pipeline_contracts import OrderingPolicy
from pipeline_contracts.intent_registry import ORDERING_POLICIES as POLICIES

from context_builder.models import BlockRole, ContextBlock, ContextSection, WorkflowPolicy

__all__ = ["OrderingPolicy", "POLICIES", "policy_for", "order_into_sections"]


def policy_for(workflow: WorkflowPolicy) -> OrderingPolicy:
    return POLICIES.get(workflow, POLICIES[WorkflowPolicy.GENERAL])


def _within_section_key(block: ContextBlock, doc_rank: dict[str, int]) -> tuple:
    """Score first (rounded so an expanded parent ties with its child), then document
    hierarchy, then reading order (heading path, page), parent just above child."""
    page = block.page_start if block.page_start is not None else 1 << 30
    return (
        -round(block.score, 4),
        doc_rank.get(block.document_id, 1 << 30),
        block.document_id,
        block.heading_path,
        page,
        not block.is_parent,
        block.block_id,
    )


def _document_ranks(blocks: list[ContextBlock]) -> dict[str, int]:
    """Rank documents by their strongest block, so 'document hierarchy' means most-relevant
    document first while keeping each document's blocks together."""
    best: dict[str, float] = {}
    for b in blocks:
        best[b.document_id] = max(best.get(b.document_id, float("-inf")), b.score)
    ordered = sorted(best, key=lambda d: best[d], reverse=True)
    return {doc: i for i, doc in enumerate(ordered)}


def _sort_blocks(blocks: list[ContextBlock]) -> list[ContextBlock]:
    ranks = _document_ranks(blocks)
    return sorted(blocks, key=lambda b: _within_section_key(b, ranks))


def _side_title(blocks: list[ContextBlock]) -> str:
    return blocks[0].citation.source_filename or blocks[0].document_id


def order_into_sections(
    blocks: list[ContextBlock],
    workflow: WorkflowPolicy,
    *,
    attachment_document_ids: tuple[str, ...] = (),
) -> list[ContextSection]:
    policy = policy_for(workflow)

    if policy.attachment_only:
        if attachment_document_ids:
            blocks = [b for b in blocks if b.document_id in attachment_document_ids]
        # with no explicit attachment ids, fall back to the single strongest document
        elif blocks:
            ranks = _document_ranks(blocks)
            top_doc = min(ranks, key=lambda d: ranks[d])
            blocks = [b for b in blocks if b.document_id == top_doc]

    ordered = _sort_blocks(blocks)
    if policy.max_blocks is not None:
        ordered = ordered[: policy.max_blocks]

    if policy.split_by_document:
        return _comparison_sections(ordered)

    if policy.single_section:
        return [ContextSection(title=policy.single_title, role=BlockRole.GENERAL, blocks=ordered)] if ordered else []

    # role-grouped sections in the workflow's priority order
    sections: list[ContextSection] = []
    for role in policy.role_order:
        role_blocks = [b for b in ordered if b.role == role]
        if role_blocks:
            sections.append(ContextSection(title=role.title, role=role, blocks=role_blocks))
    return sections


def _comparison_sections(ordered: list[ContextBlock]) -> list[ContextSection]:
    """Two sides: the two documents with the strongest blocks become Side A / Side B; any
    remaining documents fold into a third 'Other Sources' section. Balanced filling is the
    budget stage's job (the policy sets `balanced=True`)."""
    ranks = _document_ranks(ordered)
    by_doc: dict[str, list[ContextBlock]] = {}
    for b in ordered:
        by_doc.setdefault(b.document_id, []).append(b)
    docs_by_rank = sorted(by_doc, key=lambda d: ranks[d])

    sections: list[ContextSection] = []
    for doc in docs_by_rank[:2]:
        sections.append(ContextSection(title=_side_title(by_doc[doc]), role=by_doc[doc][0].role, blocks=by_doc[doc]))
    rest = [b for doc in docs_by_rank[2:] for b in by_doc[doc]]
    if rest:
        sections.append(ContextSection(title="Other Sources", role=BlockRole.GENERAL, blocks=rest))
    return sections
