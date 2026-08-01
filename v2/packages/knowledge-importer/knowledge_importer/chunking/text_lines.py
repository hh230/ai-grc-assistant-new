"""The generic engine every recognizer's boundaries flow through: turns a flat, ordered
list of `Boundary` objects into a real parent/child chunk tree, page-tagged, with
oversized leaves sub-windowed in place (architecture doc §4, §5, §6, §7). No recognizer
builds a chunk itself — this module is the only place that does, so tree-building,
page-tracking, and windowing behave identically no matter which recognizer produced the
boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass

from knowledge_importer.chunking.chunk_models import Chunk
from knowledge_importer.chunking.fallback_window import build_windows
# ChunkContext is re-exported here for backward compatibility — it historically lived in
# this module; the finalization stamps now live in `finalize.py` (one implementation).
from knowledge_importer.chunking.finalize import ChunkContext, finalize_chunk, make_chunk_id
from knowledge_importer.chunking.recognizers.base import Boundary
from knowledge_importer.chunking.text_utils import normalize_whitespace


def split_into_lines(full_text: str) -> list[tuple[int, str]]:
    """Returns (page_number, line_text) for every line, 1-indexed pages. Phase 2's `\\f`
    page-break markers are consumed here (and nowhere else needs to know about them)."""
    lines: list[tuple[int, str]] = []
    for page_index, page_text in enumerate(full_text.split("\f"), start=1):
        for line in page_text.split("\n"):
            lines.append((page_index, line))
    return lines


@dataclass
class _Draft:
    code: str | None
    title: str | None
    level: int
    parent_index: int | None
    content_type: str
    path: tuple[str, ...]
    own_lines: list[tuple[int, str]]
    window_index: int | None = None
    window_of_total: int | None = None
    page_end_override: int | None = None


def _join(lines: list[tuple[int, str]]) -> str:
    return "\n".join(line for _page, line in lines)


def _build_drafts(lines: list[tuple[int, str]], boundaries: list[Boundary]) -> list[_Draft]:
    drafts: list[_Draft] = []
    stack: list[tuple[int, int, tuple[str, ...]]] = []  # (level, draft_index, path)

    if boundaries[0].line_index > 0:
        preamble_lines = lines[: boundaries[0].line_index]
        if _join(preamble_lines).strip():
            drafts.append(
                _Draft(
                    code=None,
                    title=None,
                    level=1,
                    parent_index=None,
                    content_type="heading_only",
                    path=(),
                    own_lines=preamble_lines,
                )
            )

    for i, boundary in enumerate(boundaries):
        end = boundaries[i + 1].line_index if i + 1 < len(boundaries) else len(lines)
        own_lines = lines[boundary.line_index : end]

        while stack and stack[-1][0] >= boundary.level:
            stack.pop()
        parent_index = stack[-1][1] if stack else None
        parent_path = stack[-1][2] if stack else ()

        label = boundary.code or boundary.title or f"section-{i}"
        path = (*parent_path, label)

        drafts.append(
            _Draft(
                code=boundary.code,
                title=boundary.title,
                level=boundary.level,
                parent_index=parent_index,
                content_type=boundary.content_type,
                path=path,
                own_lines=own_lines,
            )
        )
        stack.append((boundary.level, len(drafts) - 1, path))

    return drafts


def _expand_oversized_leaves(drafts: list[_Draft], window_chars: int, overlap_chars: int) -> list[_Draft]:
    is_parent = [False] * len(drafts)
    for draft in drafts:
        if draft.parent_index is not None:
            is_parent[draft.parent_index] = True

    result: list[_Draft] = []
    index_map: dict[int, int] = {}

    for old_index, draft in enumerate(drafts):
        result.append(draft)
        new_self_index = len(result) - 1
        index_map[old_index] = new_self_index

        if is_parent[old_index]:
            continue
        own_text_len = len(normalize_whitespace(_join(draft.own_lines)))
        if own_text_len <= window_chars:
            continue

        windows = build_windows(draft.own_lines, window_chars, overlap_chars)
        if len(windows) <= 1:
            continue  # nothing to gain from splitting a unit that doesn't actually span multiple windows

        draft.own_lines = []  # content now lives entirely in the window children below
        for window_index, window in enumerate(windows):
            result.append(
                _Draft(
                    code=None,
                    title=None,
                    level=draft.level + 1,
                    parent_index=new_self_index,
                    content_type="window",
                    path=(*draft.path, f"window-{window_index}"),
                    own_lines=[(window.page_start or 1, window.text)],
                    window_index=window_index,
                    window_of_total=len(windows),
                    page_end_override=window.page_end,
                )
            )

    for draft in result:
        if draft.window_index is None and draft.parent_index is not None:
            draft.parent_index = index_map[draft.parent_index]

    return result


def _finalize(ctx: ChunkContext, drafts: list[_Draft]) -> list[Chunk]:
    chunk_ids: list[str] = []
    chunks: list[Chunk] = []
    all_codes = frozenset(d.code for d in drafts if d.code)

    for index, draft in enumerate(drafts):
        parent_chunk_id = chunk_ids[draft.parent_index] if draft.parent_index is not None else None

        chunk_id = make_chunk_id(ctx.document_id, draft.code or draft.title or f"chunk-{index}", index)
        chunk_ids.append(chunk_id)

        page_start = draft.own_lines[0][0] if draft.own_lines else None
        page_end = (
            draft.page_end_override
            if draft.page_end_override is not None
            else (draft.own_lines[-1][0] if draft.own_lines else None)
        )

        chunks.append(
            finalize_chunk(
                ctx,
                chunk_id=chunk_id,
                position=index,
                content_type=draft.content_type,
                code=draft.code,
                title=draft.title,
                path=draft.path,
                level=draft.level,
                parent_chunk_id=parent_chunk_id,
                raw_text=_join(draft.own_lines),
                page_start=page_start,
                page_end=page_end,
                window_index=draft.window_index,
                window_of_total=draft.window_of_total,
                known_codes=all_codes,
            )
        )

    return chunks


def assemble_chunks(lines: list[tuple[int, str]], boundaries: list[Boundary], ctx: ChunkContext) -> list[Chunk]:
    """Requires `boundaries` to be non-empty — the caller (`engine.py`) is responsible
    for routing a document with no recognized structure to the whole-document fallback
    (`build_fallback_chunks`) instead of calling this."""
    drafts = _build_drafts(lines, boundaries)
    drafts = _expand_oversized_leaves(drafts, ctx.window_chars, ctx.overlap_chars)
    return _finalize(ctx, drafts)


def build_fallback_chunks(lines: list[tuple[int, str]], ctx: ChunkContext) -> list[Chunk]:
    """The whole document has no recognizable structure — window the entire thing."""
    windows = build_windows(lines, ctx.window_chars, ctx.overlap_chars)
    drafts = [
        _Draft(
            code=None,
            title=None,
            level=1,
            parent_index=None,
            content_type="window",
            path=(f"window-{i}",),
            own_lines=[(window.page_start or 1, window.text)],
            window_index=i,
            window_of_total=len(windows),
            page_end_override=window.page_end,
        )
        for i, window in enumerate(windows)
    ]
    return _finalize(ctx, drafts)
