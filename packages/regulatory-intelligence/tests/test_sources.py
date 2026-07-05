"""Unit tests for RegulatorySource/RegulatorySourceRegistry and the local JSON config loader
(PI-P2: regulatory sources as configuration, not hardcoded logic)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from grc_regulatory_intelligence import (
    PollingFrequency,
    RegulatorySource,
    RegulatorySourceRegistry,
    SourceType,
    build_registry,
    load_source,
    load_source_file,
)


def _source(source_id: str = "sa-sama", enabled: bool = True) -> RegulatorySource:
    return RegulatorySource(
        source_id=source_id,
        regulator_name="Saudi Central Bank (SAMA)",
        jurisdiction="SA",
        language="ar",
        base_url="https://www.sama.gov.sa",
        source_type=SourceType.WEBSITE,
        polling_frequency=PollingFrequency.WEEKLY,
        enabled=enabled,
    )


def test_registry_lists_only_enabled_sources() -> None:
    registry = RegulatorySourceRegistry(
        (_source("sa-sama", enabled=True), _source("sa-nca", enabled=False))
    )

    assert {s.source_id for s in registry.list_all()} == {"sa-sama", "sa-nca"}
    assert [s.source_id for s in registry.list_enabled()] == ["sa-sama"]


def test_registry_rejects_duplicate_source_id() -> None:
    registry = RegulatorySourceRegistry((_source("sa-sama"),))
    with pytest.raises(ValueError, match="already registered"):
        registry.register(_source("sa-sama"))


def test_registry_get_raises_for_unknown_source() -> None:
    registry = RegulatorySourceRegistry()
    with pytest.raises(KeyError, match="no regulatory source registered"):
        registry.get("missing")


def test_source_rejects_empty_base_url() -> None:
    with pytest.raises(ValueError, match="base_url"):
        RegulatorySource(
            source_id="x",
            regulator_name="x",
            jurisdiction="SA",
            language="ar",
            base_url="   ",
            source_type=SourceType.WEBSITE,
            polling_frequency=PollingFrequency.WEEKLY,
        )


def test_load_source_from_mapping() -> None:
    source = load_source(
        {
            "source_id": "sa-nca",
            "regulator_name": "National Cybersecurity Authority (NCA)",
            "jurisdiction": "SA",
            "language": "ar",
            "base_url": "https://nca.gov.sa",
            "source_type": "website",
            "polling_frequency": "weekly",
            "enabled": True,
        }
    )
    assert source.source_type == SourceType.WEBSITE
    assert source.polling_frequency == PollingFrequency.WEEKLY


def test_load_source_rejects_unsupported_source_type() -> None:
    with pytest.raises(ValueError, match="source_type"):
        load_source(
            {
                "source_id": "sa-nca",
                "regulator_name": "NCA",
                "jurisdiction": "SA",
                "language": "ar",
                "base_url": "https://nca.gov.sa",
                "source_type": "carrier_pigeon",
                "polling_frequency": "weekly",
            }
        )


def test_load_source_file_and_build_registry(tmp_path: Path) -> None:
    file_path = tmp_path / "sama.json"
    file_path.write_text(
        json.dumps(
            {
                "source_id": "sa-sama",
                "regulator_name": "Saudi Central Bank (SAMA)",
                "jurisdiction": "SA",
                "language": "ar",
                "base_url": "https://www.sama.gov.sa",
                "source_type": "website",
                "polling_frequency": "weekly",
                "enabled": True,
            }
        ),
        encoding="utf-8",
    )

    source = load_source_file(file_path)
    assert source.source_id == "sa-sama"

    registry = build_registry((file_path,))
    assert registry.get("sa-sama").regulator_name == "Saudi Central Bank (SAMA)"


def test_load_source_file_rejects_non_json_suffix(tmp_path: Path) -> None:
    file_path = tmp_path / "sama.yaml"
    file_path.write_text("source_id: sa-sama", encoding="utf-8")
    with pytest.raises(ValueError, match="Unsupported source config format"):
        load_source_file(file_path)
