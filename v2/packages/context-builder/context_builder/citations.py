"""Citation preservation.

The Context Builder must never lose a citation. Every `ContextBlock` carries the Retrieval
Engine's own `Citation` object untouched, so preservation is structural — this module adds
only the *checks and identities* around that guarantee:

- `citation_is_complete` — the block still resolves to a real place in a real document
  (a source file plus at least one locator: clause code, page, or heading),
- `citation_key` / `clause_key` — stable identities used by dedup and merge to reason about
  "same place" and "same clause",
- `respan` — widen a citation's page span when a merge joins adjacent chunks.

The rules themselves are pure functions over the shared `Citation` contract, so they live in
`pipeline_contracts.citations` — the single canonical home for citation formatting and
validity. This module re-exports them so every existing `context_builder.citations` import
keeps working.
"""

from __future__ import annotations

from pipeline_contracts.citations import (
    REQUIRED_LOCATORS,
    citation_is_complete,
    citation_key,
    clause_key,
    missing_facets,
    respan,
)

__all__ = [
    "REQUIRED_LOCATORS",
    "citation_is_complete",
    "missing_facets",
    "citation_key",
    "clause_key",
    "respan",
]
