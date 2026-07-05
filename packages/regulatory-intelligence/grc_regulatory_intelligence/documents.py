"""Value objects for crawler discovery/fetch output, and the anti-corruption translation
(CLAUDE.md §15) into the engine's ``RawRegulatoryDocument``.

A crawler adapter is responsible for extracting plain text from whatever a source served
(HTML/PDF/text) *before* constructing a ``RegulatoryDocumentInput`` — this package only ever
sees normalized text, never raw bytes or a parsing library.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from .artifacts import RawRegulatoryDocument


class DocumentContentType(str, Enum):
    """The source format a document was served in, before normalization to text."""

    HTML = "html"
    PDF = "pdf"
    TEXT = "text"


@dataclass(frozen=True)
class DiscoveredDocumentRef:
    """One candidate document a crawler's discovery step found, before its content is
    fetched."""

    url: str
    title: str | None = None
    published_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.url.strip():
            raise ValueError("DiscoveredDocumentRef.url must not be empty")


@dataclass(frozen=True)
class RegulatoryDocumentInput:
    """A fetched-and-normalized document, ready to become a ``RawRegulatoryDocument``."""

    source_id: str
    url: str
    raw_text: str
    content_type: DocumentContentType
    discovered_at: datetime
    title: str | None = None
    published_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.source_id.strip():
            raise ValueError("RegulatoryDocumentInput.source_id must not be empty")
        if not self.url.strip():
            raise ValueError("RegulatoryDocumentInput.url must not be empty")
        if not self.raw_text.strip():
            raise ValueError("RegulatoryDocumentInput.raw_text must not be empty")
        if self.discovered_at.tzinfo is None:
            raise ValueError("RegulatoryDocumentInput.discovered_at must be timezone-aware")

    def to_raw_regulatory_document(self) -> RawRegulatoryDocument:
        """The anti-corruption translation into the engine's input type — computes the same
        sha256 content hash ``RawRegulatoryDocument.content_hash`` is defined as."""
        return RawRegulatoryDocument(
            source_id=self.source_id,
            url=self.url,
            fetched_at=self.discovered_at,
            content_hash=_content_hash(self.raw_text),
            raw_text=self.raw_text,
        )


def _content_hash(raw_text: str) -> str:
    return hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
