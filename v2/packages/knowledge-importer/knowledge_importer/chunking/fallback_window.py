"""Sentence/paragraph-boundary-aware sliding window — the floor of the recognizer
cascade (architecture doc §3.6) and the mechanism used when one structure-aware leaf is
too large to embed as a single chunk (§7). Window size/overlap default to the one number
already validated in production (`apps/web`'s 1200 characters / 150-character overlap),
sourced from the assigned Document Profile's `fallback_windowing` (never re-invented per
document type).

Never applies overlap between structure-aware chunks — this module is only ever called
either (a) for a whole document with no recognizable structure, or (b) for the text
*inside* one already-recognized structural unit that is too large — never across a
structural boundary."""

from __future__ import annotations

from dataclasses import dataclass

from knowledge_importer.chunking.text_utils import find_break_point


@dataclass(frozen=True)
class WindowSpan:
    text: str
    page_start: int | None
    page_end: int | None


def build_windows(lines: list[tuple[int, str]], window_chars: int, overlap_chars: int) -> list[WindowSpan]:
    """`lines`: page-tagged lines (as produced by `text_lines.split_into_lines`, or a
    sub-span of them for the oversized-leaf case). Returns overlapping windows with
    page bounds resolved from the lines each window actually spans."""
    if not lines:
        return []

    joined_parts: list[str] = []
    line_starts: list[tuple[int, int]] = []  # (char offset where this line starts, page)
    offset = 0
    for page, line_text in lines:
        line_starts.append((offset, page))
        joined_parts.append(line_text)
        offset += len(line_text) + 1  # +1 for the "\n" joiner below
    joined_text = "\n".join(joined_parts)

    def page_at(pos: int) -> int:
        page = line_starts[0][1]
        for start, pg in line_starts:
            if start <= pos:
                page = pg
            else:
                break
        return page

    total = len(joined_text)
    if total == 0:
        return []

    windows: list[WindowSpan] = []
    start = 0
    while start < total:
        target_end = min(total, start + window_chars)
        end = target_end if target_end >= total else find_break_point(joined_text, target_end)
        if end <= start:
            end = target_end
        windows.append(
            WindowSpan(
                text=joined_text[start:end],
                page_start=page_at(start),
                page_end=page_at(max(start, end - 1)),
            )
        )
        if end >= total:
            break
        start = max(start + 1, end - overlap_chars)

    return windows
