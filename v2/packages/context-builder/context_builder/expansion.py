"""Parent expansion — give an orphaned child chunk its heading context.

Retrieval often returns a deep sub-clause ("A.5.15.2") without the section it lives under.
For a GRC reader (and a later LLM) the parent heading is what makes the fragment
interpretable. This stage, *when useful*, pulls in the immediate parent section.

Dependency inversion: the builder depends only on the `ParentResolver` **port**; it never
knows whether parents come from the in-memory corpus, PostgreSQL, or anything else. A
corpus-backed adapter is provided for tests/benchmarks. With no resolver, expansion is a
clean no-op — the builder still produces a valid package.

Guardrails: expand only children with a real parent heading (depth ≥ 2); never add a parent
already present; cap the number of expansions; and let the budget stage drop any that don't
fit — expansion never forces the package over budget.
"""

from __future__ import annotations

from typing import Protocol

from context_builder.deduplicate import content_hash
from context_builder.models import ContextBlock, role_for_profile
from pipeline_contracts.retrieval import CorpusChunk, build_citation

DEFAULT_MAX_EXPANSIONS = 8


class ParentResolver(Protocol):
    """Resolve the parent section block for a child. Returns None when there is no distinct
    parent (top-level content, or the parent is not in the source)."""

    def parent_block(self, document_id: str, heading_path: tuple[str, ...]) -> ContextBlock | None: ...


def _block_from_corpus_chunk(chunk: CorpusChunk, *, score: float) -> ContextBlock:
    citation = build_citation(chunk)
    return ContextBlock(
        block_id=chunk.chunk_id,
        document_id=chunk.document_id,
        role=role_for_profile(chunk.document_profile),
        text=chunk.text,
        citation=citation,
        heading_path=chunk.heading_path,
        page_start=chunk.page_start,
        page_end=chunk.page_end,
        code=chunk.code,
        document_profile=chunk.document_profile,
        score=score,
        confidence=0.0,
        is_parent=True,
        source_chunk_ids=(chunk.chunk_id,),
        content_hash=content_hash(chunk.text),
    )


class CorpusParentResolver:
    """Corpus-backed `ParentResolver`. Indexes chunks by (document_id, heading_path) so the
    parent of a child is the earliest-page chunk sitting *exactly* at the parent heading —
    the section's own intro text, not a sibling sub-clause."""

    def __init__(self, corpus) -> None:  # InMemoryCorpus (duck-typed to avoid a hard import)
        self._by_heading: dict[tuple[str, tuple[str, ...]], list[CorpusChunk]] = {}
        for chunk in corpus.chunks:
            key = (chunk.document_id, tuple(chunk.heading_path))
            self._by_heading.setdefault(key, []).append(chunk)
        for chunks in self._by_heading.values():
            chunks.sort(key=lambda c: (c.page_start if c.page_start is not None else 1 << 30, c.chunk_id))

    def parent_block(self, document_id: str, heading_path: tuple[str, ...]) -> ContextBlock | None:
        if len(heading_path) < 2:
            return None  # top-level content has no parent heading to add
        parent_path = tuple(heading_path[:-1])
        candidates = self._by_heading.get((document_id, parent_path))
        if not candidates:
            return None
        return _block_from_corpus_chunk(candidates[0], score=0.0)


def expand_parents(
    blocks: list[ContextBlock],
    resolver: ParentResolver | None,
    *,
    max_expansions: int = DEFAULT_MAX_EXPANSIONS,
) -> tuple[list[ContextBlock], int]:
    """Append parent blocks for child blocks that lack their heading context. Returns
    (blocks, expansions added). No-op when `resolver` is None."""
    if resolver is None:
        return blocks, 0

    present_ids = {b.block_id for b in blocks}
    present_hashes = {b.content_hash for b in blocks}
    added: list[ContextBlock] = []
    added_ids: set[str] = set()

    # Expand the strongest children first, so if the cap bites we spend it on the best hits.
    for child in sorted(blocks, key=lambda b: b.score, reverse=True):
        if len(added) >= max_expansions:
            break
        parent = resolver.parent_block(child.document_id, child.heading_path)
        if parent is None:
            continue
        if parent.block_id in present_ids or parent.block_id in added_ids:
            continue
        if parent.content_hash in present_hashes:
            continue  # parent text already in the set under a different id
        # A parent is contextual scaffolding for its child; score it just below the child so
        # real hits always outrank it and the budget stage trims parents before evidence.
        parent.score = child.score - 1e-6
        parent.confidence = child.confidence
        added.append(parent)
        added_ids.add(parent.block_id)

    return blocks + added, len(added)
