"""The 6 initial Saudi regulatory sources (PI-P2) load as valid configuration — not
hardcoded logic — via the same loader any future jurisdiction/regulator uses."""

from __future__ import annotations

from pathlib import Path

from grc_regulatory_intelligence import SourceType, build_registry

_SOURCES_DIR = Path(__file__).resolve().parents[3] / "regulatory-sources" / "sa"
_EXPECTED_SOURCE_IDS = {"sa-sama", "sa-cma", "sa-nca", "sa-sdaia", "sa-mhrsd", "sa-zatca"}


def test_all_saudi_sources_load_and_are_enabled_websites() -> None:
    files = tuple(sorted(_SOURCES_DIR.glob("*.json")))
    assert len(files) == 6

    registry = build_registry(files)

    assert {source.source_id for source in registry.list_all()} == _EXPECTED_SOURCE_IDS
    for source in registry.list_all():
        assert source.jurisdiction == "SA"
        assert source.source_type == SourceType.WEBSITE
        assert source.enabled is True
        assert source.base_url.startswith("https://")
    assert len(registry.list_enabled()) == 6
