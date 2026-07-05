"""Unit tests for the regulatory connectors foundation."""

from __future__ import annotations

import pytest
from grc_regulatory_intelligence_adapters import (
    ConnectorFetchError,
    HttpRegulatoryConnector,
    StaticRegulatoryConnector,
)


async def test_static_connector_fetches_registered_document() -> None:
    connector = StaticRegulatoryConnector({"nca-ecc": "1. Entities shall encrypt data."})

    fetched = await connector.fetch(source_id="nca-ecc", url="https://example.gov/nca-ecc")

    assert fetched.source_id == "nca-ecc"
    assert fetched.raw_text == "1. Entities shall encrypt data."
    assert fetched.fetched_at.tzinfo is not None
    assert len(fetched.content_hash) == 64  # sha256 hex digest


async def test_static_connector_content_hash_is_deterministic() -> None:
    connector = StaticRegulatoryConnector({"src": "same text"})

    first = await connector.fetch(source_id="src", url="https://example.gov")
    second = await connector.fetch(source_id="src", url="https://example.gov")

    assert first.content_hash == second.content_hash


async def test_static_connector_raises_for_unknown_source() -> None:
    connector = StaticRegulatoryConnector({})
    with pytest.raises(ConnectorFetchError, match="no static document"):
        await connector.fetch(source_id="missing", url="https://example.gov")


async def test_http_connector_rejects_non_http_schemes_without_network_access() -> None:
    connector = HttpRegulatoryConnector()
    with pytest.raises(ConnectorFetchError, match="unsupported URL scheme"):
        await connector.fetch(source_id="local-file", url="file:///etc/passwd")
