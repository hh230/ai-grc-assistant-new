"""Citation validation — the GRC gate. A retrieved chunk may only surface if it resolves
to a live, citable source: a source filename plus at least one locator (a clause code or a
page). Chunks that can't be cited are dropped from the answer set. This is what turns
retrieval into "here is the source, page 12", not "the system said so" (CLAUDE.md §12/§19).

The helpers themselves are pure value-object constructors over the shared `Citation` /
`CorpusChunk` contracts, so they live in `pipeline_contracts.citations` — the single
canonical home for citation formatting and validity. This module re-exports them so every
existing `retrieval_engine.citation` import keeps working.
"""

from __future__ import annotations

from pipeline_contracts.citations import build_citation, format_citation, is_citable

__all__ = ["is_citable", "format_citation", "build_citation"]
