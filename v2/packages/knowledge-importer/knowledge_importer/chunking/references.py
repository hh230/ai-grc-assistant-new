"""Detects candidate in-text cross-reference mentions inside a chunk's own text.
Detection only — never resolved to an actual target chunk here (architecture doc §8).
`scope` is decided by the caller (`engine.py`), which knows the full set of codes
recognized elsewhere in the same document; this module only finds the raw mentions."""

from __future__ import annotations

import re

from knowledge_importer.chunking.chunk_models import ChunkReference

_REFERENCE_CONFIDENCE = 0.6

_PATTERNS = [
    re.compile(r"\bsee\s+Clause\s+([\w.\-]+)", re.IGNORECASE),
    re.compile(r"\bas defined in\s+(?:Clause|Article|Section)\s+([\w.\-()]+)", re.IGNORECASE),
    re.compile(r"\bpursuant to\s+(?:Clause|Article|Section)\s+([\w.\-()]+)", re.IGNORECASE),
    re.compile(r"\bin accordance with\s+[A-Z][\w /:.\-]*?\s+Annex\s+([\w.\-]+)", re.IGNORECASE),
    re.compile(r"\brefer to\s+(?:Clause|Article|Section)\s+([\w.\-()]+)", re.IGNORECASE),
]


def detect_references(text: str) -> tuple[ChunkReference, ...]:
    references: list[ChunkReference] = []
    for pattern in _PATTERNS:
        for match in pattern.finditer(text):
            references.append(
                ChunkReference(
                    raw_text=match.group(0).strip(),
                    target_code=match.group(1).strip(".,;: "),
                    scope="internal",  # refined by the caller once local codes are known
                    confidence=_REFERENCE_CONFIDENCE,
                )
            )
    return tuple(references)


def resolve_scopes(references: tuple[ChunkReference, ...], known_codes: frozenset[str]) -> tuple[ChunkReference, ...]:
    """Re-tags each reference's `scope` as `"internal"` if its target_code matches a code
    recognized elsewhere in the same document, `"external"` otherwise. Still not a
    resolution to an actual chunk_id — only a same-document-or-not classification."""
    return tuple(
        ref if ref.target_code in known_codes else ChunkReference(ref.raw_text, ref.target_code, "external", ref.confidence)
        for ref in references
    )
