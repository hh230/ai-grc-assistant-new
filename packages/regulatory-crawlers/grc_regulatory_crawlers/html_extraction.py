"""HTML discovery and normalization — stdlib-only (``html.parser.HTMLParser``), no new
third-party HTML dependency for this foundational phase.

``discover_links`` implements the discovery heuristic: a regulator's listing page links to
individual regulation/circular pages or PDFs via ``<a href>``. ``html_to_text`` implements
normalization: strip markup (and script/style content) down to the plain text
``RegulatoryDocumentInput.raw_text`` expects.
"""

from __future__ import annotations

from html.parser import HTMLParser
from urllib.parse import urljoin

from grc_regulatory_intelligence import DiscoveredDocumentRef


class _LinkCollector(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self._base_url = base_url
        self._current_href: str | None = None
        self._current_text: list[str] = []
        self.links: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        href = next((value for name, value in attrs if name == "href" and value), None)
        if href:
            self._current_href = urljoin(self._base_url, href)
            self._current_text = []

    def handle_data(self, data: str) -> None:
        if self._current_href is not None:
            self._current_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._current_href is not None:
            text = "".join(self._current_text).strip()
            self.links.append((self._current_href, text))
            self._current_href = None
            self._current_text = []


def discover_links(html: str, *, base_url: str) -> tuple[DiscoveredDocumentRef, ...]:
    """Find candidate document links on a listing page, resolved to absolute URLs and
    de-duplicated in document order."""
    collector = _LinkCollector(base_url)
    collector.feed(html)
    refs: list[DiscoveredDocumentRef] = []
    seen: set[str] = set()
    for url, text in collector.links:
        if url in seen:
            continue
        seen.add(url)
        refs.append(DiscoveredDocumentRef(url=url, title=text or None))
    return tuple(refs)


class _TextExtractor(HTMLParser):
    _SKIP_TAGS = frozenset({"script", "style"})

    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self.chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self.chunks.append(data)


def html_to_text(html: str) -> str:
    """Strip tags (and script/style content) to plain text, dropping blank lines."""
    extractor = _TextExtractor()
    extractor.feed(html)
    text = "".join(extractor.chunks)
    lines = (line.strip() for line in text.splitlines())
    return "\n".join(line for line in lines if line)
