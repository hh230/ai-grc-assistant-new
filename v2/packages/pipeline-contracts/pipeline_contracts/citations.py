"""Citations — the one canonical implementation of citation formatting and validity.

A citation is what turns retrieval into "here is the source, page 12" instead of "the
system said so" (CLAUDE.md §12/§19), so its rules cannot be allowed to drift between the
stages that apply them. Everything about a citation lives here: the `Citation` contract
itself, the human-readable format, the two validity gates, the identity keys, and the
page-span widening used by merges. Downstream packages re-export these names; none of them
carries its own copy.

Two gates, deliberately different, both defined here so the difference is a decision rather
than an accident:

- `is_citable` — the **retrieval gate**. A chunk may only enter the answer set if it names
  a source file *and* pins a hard locator: a clause code or a page. A heading alone is not
  enough to send an auditor to a place in a document.
- `citation_is_complete` — the **context gate**. Once retrieval has admitted a chunk, the
  context stage only checks that its citation still resolves somewhere (source plus code,
  page, *or* heading). It is looser on purpose: parent-expansion and adjacent-merge build
  blocks from headings, and re-applying the retrieval gate here would drop citations that
  retrieval already validated.

Both formatters read the same fields, so a `CorpusChunk` and the `Citation` built from it
format identically — that is enforced by the `CitationSource` protocol rather than by two
functions kept in sync by hand.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Protocol

from pipeline_contracts.serialization import dataclass_dict


class CitationSource(Protocol):
    """The facets any citable thing exposes. Structural, so both the retrieval-stage
    `CorpusChunk` and the `Citation` built from it satisfy it without either importing the
    other — which is what lets one formatter serve both."""

    @property
    def source_filename(self) -> str: ...

    @property
    def code(self) -> str | None: ...

    @property
    def title(self) -> str | None: ...

    @property
    def heading_path(self) -> tuple[str, ...]: ...

    @property
    def page_start(self) -> int | None: ...

    @property
    def page_end(self) -> int | None: ...


class ChunkSource(CitationSource, Protocol):
    """A `CitationSource` that also carries the document classification a `Citation` records.
    `CorpusChunk` satisfies it structurally — again, no import either way."""

    @property
    def category(self) -> str: ...

    @property
    def document_profile(self) -> str | None: ...

    @property
    def structure_profile(self) -> str: ...


@dataclass(frozen=True)
class Citation:
    """Where a claim comes from: the document, its classification, and every locator that
    narrows it down to a place a human can open. `formatted` is the rendered string, kept on
    the value object so every consumer shows the same citation text."""

    source_filename: str
    category: str
    document_profile: str | None
    structure_profile: str
    code: str | None
    title: str | None
    heading_path: tuple[str, ...]
    page_start: int | None
    page_end: int | None
    formatted: str  # a ready-to-render citation string

    def to_dict(self) -> dict[str, object]:
        return dataclass_dict(self)


# ── formatting ────────────────────────────────────────────────────────────────
def format_citation(source: CitationSource) -> str:
    """The canonical rendering: `document — locator title — p. N`, where the locator is the
    clause code, falling back to the heading path. Accepts anything citation-shaped, so a
    chunk and its `Citation` always render the same."""
    parts: list[str] = [source.source_filename]
    locator = source.code or (" › ".join(source.heading_path) if source.heading_path else None)
    if locator:
        title = f" {source.title}" if source.title else ""
        parts.append(f"{locator}{title}")
    elif source.title:
        parts.append(source.title)
    if source.page_start is not None:
        if source.page_end is not None and source.page_end != source.page_start:
            parts.append(f"pp. {source.page_start}–{source.page_end}")
        else:
            parts.append(f"p. {source.page_start}")
    return " — ".join(parts)


def build_citation(chunk: ChunkSource) -> Citation:
    """Build the `Citation` value object from a retrieved chunk, formatting included."""
    return Citation(
        source_filename=chunk.source_filename,
        category=chunk.category,
        document_profile=chunk.document_profile,
        structure_profile=chunk.structure_profile,
        code=chunk.code,
        title=chunk.title,
        heading_path=chunk.heading_path,
        page_start=chunk.page_start,
        page_end=chunk.page_end,
        formatted=format_citation(chunk),
    )


# ── validity ──────────────────────────────────────────────────────────────────
def is_citable(chunk: CitationSource) -> bool:
    """The retrieval gate: a source file plus a hard locator (clause code or page).
    Chunks that fail are dropped from the answer set."""
    if not chunk.source_filename:
        return False
    return bool(chunk.code) or chunk.page_start is not None


def citation_is_complete(citation: Citation | None) -> bool:
    """The context gate: the citation still resolves to a real place in a real document —
    a source file plus at least one locator (code, page, *or* heading)."""
    if citation is None:
        return False
    if not citation.source_filename:
        return False
    return bool(citation.code) or citation.page_start is not None or bool(citation.heading_path)


# The facets a GRC citation is expected to carry through the pipeline: document · page ·
# heading · clause · code · profile. Not all are non-null for every document type — a law
# article has no page image, a spreadsheet row has no clause — so completeness requires the
# source plus *at least one* locator, not all six.
REQUIRED_LOCATORS = ("code", "page_start", "heading_path")


def missing_facets(citation: Citation | None) -> list[str]:
    """Diagnostic: which expected facets are absent (for warnings, not for rejection)."""
    if citation is None:
        return ["citation"]
    absent: list[str] = []
    if not citation.source_filename:
        absent.append("document")
    if citation.page_start is None:
        absent.append("page")
    if not citation.heading_path:
        absent.append("heading")
    if not citation.title:
        absent.append("clause")
    if not citation.code:
        absent.append("code")
    if not citation.document_profile:
        absent.append("profile")
    return absent


# ── identity ──────────────────────────────────────────────────────────────────
def citation_key(citation: Citation) -> str:
    """Stable identity of the place a citation points to: document + clause code + heading +
    page span. Two chunks with the same key cite the same location."""
    heading = "›".join(citation.heading_path)
    return "|".join(
        [
            citation.source_filename,
            citation.code or "",
            heading,
            str(citation.page_start if citation.page_start is not None else ""),
            str(citation.page_end if citation.page_end is not None else ""),
        ]
    )


def clause_key(citation: Citation) -> str:
    """Identity of the *clause/section* a citation belongs to, ignoring page span — so two
    consecutive chunks of the same clause share a key even when their pages differ. Drives
    the adjacent-merge decision ("same heading, same citation")."""
    return "|".join(
        [citation.source_filename, citation.code or "", "›".join(citation.heading_path)]
    )


# ── derivation ────────────────────────────────────────────────────────────────
def respan(citation: Citation, page_start: int | None, page_end: int | None) -> Citation:
    """Return a copy of `citation` with a widened page span and a refreshed `formatted`
    string. Every other facet (document, code, heading, title, profile) is preserved."""
    widened = replace(citation, page_start=page_start, page_end=page_end)
    return replace(widened, formatted=format_citation(widened))
