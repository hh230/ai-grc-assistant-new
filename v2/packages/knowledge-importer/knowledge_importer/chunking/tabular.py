"""TabularRecognizer — sheet/row/column structure for the `spreadsheet` Document
Profile. Structure is already explicit from Phase 2's `ExcelParser` convention (`\\f`
between sheets, tab-separated cells) — this module's job is chunk *sizing*, not boundary
discovery: group rows into bounded chunks, repeating the header row at the top of every
group so a chunk retrieved in isolation never loses its column context.

Bypasses the generic boundary/tree assembler (`text_lines.py`) entirely, since sheet/row
grouping isn't a flat list of leveled headings — it builds chunks directly through the
shared finalization helper (`finalize.py`), so the stamps (checksum, references, language)
are the same single implementation every producer uses."""

from __future__ import annotations

from knowledge_importer.chunking.chunk_models import Chunk
from knowledge_importer.chunking.finalize import ChunkContext, finalize_chunk, make_chunk_id

ROWS_PER_CHUNK = 40


def _make_chunk(
    ctx: ChunkContext,
    *,
    chunk_id: str,
    position: int,
    content_type: str,
    title: str | None,
    path: tuple[str, ...],
    level: int,
    parent_chunk_id: str | None,
    raw_text: str,
    page: int,
) -> Chunk:
    return finalize_chunk(
        ctx,
        chunk_id=chunk_id,
        position=position,
        content_type=content_type,
        code=None,
        title=title,
        path=path,
        level=level,
        parent_chunk_id=parent_chunk_id,
        raw_text=raw_text,
        page_start=page,
        page_end=page,
    )


def build_tabular_chunks(full_text: str, ctx: ChunkContext) -> list[Chunk]:
    sheets = full_text.split("\f")
    chunks: list[Chunk] = []
    position = 0

    for sheet_index, sheet_text in enumerate(sheets, start=1):
        rows = sheet_text.split("\n")
        while rows and rows[-1].strip() == "":
            rows.pop()
        if not rows:
            continue

        header, data_rows = rows[0], rows[1:]
        sheet_path = (f"sheet-{sheet_index}",)
        sheet_chunk_id = make_chunk_id(ctx.document_id, f"sheet-{sheet_index}", position)
        chunks.append(
            _make_chunk(
                ctx,
                chunk_id=sheet_chunk_id,
                position=position,
                content_type="heading_only",
                title=f"Sheet {sheet_index}",
                path=sheet_path,
                level=1,
                parent_chunk_id=None,
                raw_text=header,
                page=sheet_index,
            )
        )
        position += 1

        for group_start in range(0, len(data_rows), ROWS_PER_CHUNK):
            group_rows = data_rows[group_start : group_start + ROWS_PER_CHUNK]
            group_index = group_start // ROWS_PER_CHUNK
            group_text = "\n".join([header, *group_rows])
            chunk_id = make_chunk_id(ctx.document_id, f"sheet-{sheet_index}-rows-{group_index}", position)
            chunks.append(
                _make_chunk(
                    ctx,
                    chunk_id=chunk_id,
                    position=position,
                    content_type="table",
                    title=None,
                    path=(*sheet_path, f"rows-{group_index}"),
                    level=2,
                    parent_chunk_id=sheet_chunk_id,
                    raw_text=group_text,
                    page=sheet_index,
                )
            )
            position += 1

    return chunks
