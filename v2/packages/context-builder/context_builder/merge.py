"""Adjacent merge — stitch fragments of the same clause back together.

Two blocks merge only when they are all of:
  • **same document** (never merge across documents — that would fabricate a citation),
  • **same heading** (identical heading path),
  • **same citation clause** (same source + code + heading, via `clause_key`),
  • **consecutive** (contiguous/overlapping pages, or an unpaged clause — laws/regulations
    that carry a code but no page image).

Merging concatenates the text (dropping a fully-contained fragment), widens the page span,
and reformats the citation to match. The result keeps the strongest score/confidence and
the union of source chunk ids, so nothing about provenance is lost.
"""

from __future__ import annotations

from context_builder.citations import clause_key, respan
from context_builder.deduplicate import containment, content_hash, token_set
from context_builder.models import ContextBlock


def _consecutive(a: ContextBlock, b: ContextBlock) -> bool:
    """`a` then `b` — contiguous or overlapping pages. Unpaged clauses (page_start None on
    either) count as consecutive when they share a clause, since laws/regulations are
    ordered by article, not page."""
    if a.page_end is None or b.page_start is None:
        return True
    return b.page_start <= a.page_end + 1


def _merge_pair(a: ContextBlock, b: ContextBlock) -> ContextBlock:
    ta, tb = token_set(a.text), token_set(b.text)
    if tb and containment(tb, ta) >= 0.99:
        text = a.text  # b is already contained in a
    elif ta and containment(ta, tb) >= 0.99:
        text = b.text
    else:
        text = f"{a.text}\n\n{b.text}"

    pages = [p for p in (a.page_start, b.page_start, a.page_end, b.page_end) if p is not None]
    page_start = min(pages) if pages else None
    page_end = max(pages) if pages else None

    a.text = text
    a.page_start = page_start
    a.page_end = page_end
    a.citation = respan(a.citation, page_start, page_end)
    a.score = max(a.score, b.score)
    a.confidence = max(a.confidence, b.confidence)
    a.source_chunk_ids = tuple(dict.fromkeys((*a.source_chunk_ids, *b.source_chunk_ids)))
    a.content_hash = content_hash(text)
    return a


def merge_adjacent(blocks: list[ContextBlock]) -> tuple[list[ContextBlock], int]:
    """Merge consecutive same-clause blocks. Returns (merged blocks, number of blocks
    absorbed). Order within a clause is by page then heading; the relative order of distinct
    clauses is preserved so downstream ordering still sees them."""
    # Group by clause, remembering first-seen order for a stable result.
    order: list[str] = []
    groups: dict[str, list[ContextBlock]] = {}
    for b in blocks:
        key = clause_key(b.citation)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(b)

    result: list[ContextBlock] = []
    merged_count = 0
    for key in order:
        group = groups[key]
        if len(group) == 1:
            result.append(group[0])
            continue
        # sort within the clause by page, then heading depth, for correct stitching
        group.sort(key=lambda b: (b.page_start if b.page_start is not None else 1 << 30, b.heading_path))
        current = group[0]
        for nxt in group[1:]:
            if current.document_id == nxt.document_id and _consecutive(current, nxt):
                current = _merge_pair(current, nxt)
                merged_count += 1
            else:
                result.append(current)
                current = nxt
        result.append(current)
    return result, merged_count
