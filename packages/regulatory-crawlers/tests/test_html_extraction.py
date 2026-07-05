"""Unit tests for HTML discovery (link extraction) and normalization (tag stripping)."""

from __future__ import annotations

from grc_regulatory_crawlers import discover_links, html_to_text


def test_discover_links_resolves_relative_urls_and_captures_titles() -> None:
    html = """
    <html><body>
      <h1>Circulars</h1>
      <a href="/circulars/1">Circular 1: Data Protection</a>
      <a href="https://example.gov/circulars/2">Circular 2</a>
      <a href="mailto:info@example.gov"></a>
    </body></html>
    """

    refs = discover_links(html, base_url="https://example.gov/circulars/index")

    urls = [ref.url for ref in refs]
    assert "https://example.gov/circulars/1" in urls
    assert "https://example.gov/circulars/2" in urls
    by_url = {ref.url: ref for ref in refs}
    assert by_url["https://example.gov/circulars/1"].title == "Circular 1: Data Protection"


def test_discover_links_deduplicates_repeated_links() -> None:
    html = '<a href="/a">First</a><a href="/a">First again</a>' '<a href="/b">Second</a>'
    refs = discover_links(html, base_url="https://example.gov")
    assert len(refs) == 2


def test_discover_links_returns_empty_for_no_anchors() -> None:
    assert discover_links("<html><body>No links here.</body></html>", base_url="https://x") == ()


def test_html_to_text_strips_tags_and_script_style_content() -> None:
    html = """
    <html>
      <head><style>body { color: red; }</style></head>
      <body>
        <script>alert('should not appear');</script>
        <h1>Cybersecurity Circular</h1>
        <p>Entities shall encrypt data at rest.</p>
      </body>
    </html>
    """

    text = html_to_text(html)

    assert "color: red" not in text
    assert "should not appear" not in text
    assert "Cybersecurity Circular" in text
    assert "Entities shall encrypt data at rest." in text


def test_html_to_text_drops_blank_lines() -> None:
    text = html_to_text("<p>Line one</p>\n\n\n<p>Line two</p>")
    assert text == "Line one\nLine two"
