"""A rule-based, in-memory document adapter (implements ``DocumentAdapterPort``).

Turns a plain-text / Markdown source into a uniform ``ParsedDocument`` by reading the text held
for its ``StorageLocator`` in an injected corpus — no object store, OCR, or parsing library. A
production adapter (PDF/DOCX) implements the same port; this keeps the engine runnable and
testable end to end without external dependencies. (CLAUDE.md §12: parsing is infrastructure
behind a port.)
"""
from __future__ import annotations

from collections.abc import Mapping

from grc_domain.extraction import RawDocumentDescriptor
from grc_domain.knowledge import DocumentFormat
from grc_extraction import DocumentAdapterPort, LayoutBlock, ParsedDocument

from .exceptions import DocumentNotAvailableError

_SUPPORTED_FORMATS: frozenset[DocumentFormat] = frozenset(
    {DocumentFormat.TXT, DocumentFormat.MARKDOWN, DocumentFormat.HTML}
)


class InMemoryTextDocumentAdapter(DocumentAdapterPort):
    """Parses text held in memory, keyed by storage locator URI, into ``LayoutBlock``s."""

    def __init__(
        self,
        corpus: Mapping[str, str],
        *,
        name: str = "in-memory-text",
        version: str = "1.0.0",
    ) -> None:
        self._corpus = dict(corpus)
        self._name = name
        self._version = version

    def supports(self, document_format: DocumentFormat) -> bool:
        return document_format in _SUPPORTED_FORMATS

    async def parse(self, document: RawDocumentDescriptor) -> ParsedDocument:
        uri = document.storage_locator.uri
        text = self._corpus.get(uri)
        if text is None:
            raise DocumentNotAvailableError(f"No document content registered for {uri}")
        blocks = tuple(
            LayoutBlock(text=line, page_number=1, order=order)
            for order, line in enumerate(_nonempty_lines(text))
        )
        return ParsedDocument(
            blocks=blocks,
            document_format=document.declared_format,
            language=document.declared_language,
            page_count=1,
            parser_name=self._name,
            parser_version=self._version,
        )


def _nonempty_lines(text: str) -> list[str]:
    return [stripped for line in text.splitlines() if (stripped := line.strip())]
