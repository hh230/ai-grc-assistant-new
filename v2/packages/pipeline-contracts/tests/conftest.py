"""Fixtures for the contract behaviour tests: the citable shapes the pipeline passes around.

Everything here is a plain value object — the contracts package has no infrastructure to
fake and no engine to drive.
"""

from __future__ import annotations

from pipeline_contracts import Citation, CorpusChunk, build_citation


def make_chunk(
    *,
    chunk_id: str = "c1",
    code: str | None = "5-1",
    title: str | None = "Data Processing",
    heading_path: tuple[str, ...] = ("Chapter 2", "Article 5"),
    page_start: int | None = 3,
    page_end: int | None = 3,
    source_filename: str = "pdpl.pdf",
    document_profile: str | None = "law",
) -> CorpusChunk:
    return CorpusChunk(
        chunk_id=chunk_id,
        document_id="doc-pdpl",
        text="Personal data may only be processed with the consent of the data subject.",
        document_profile=document_profile,
        structure_profile="regulation_article",
        category="laws",
        language="en",
        code=code,
        title=title,
        heading_path=heading_path,
        page_start=page_start,
        page_end=page_end,
        source_filename=source_filename,
        checksum="abc123",
        content_type="application/pdf",
    )


def make_citation(**overrides) -> Citation:
    """A Citation built the way the pipeline builds one: from a chunk, via `build_citation`."""
    return build_citation(make_chunk(**overrides))
