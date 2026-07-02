"""Integration tests: load the real seed framework data from /frameworks and query it."""
from __future__ import annotations

from pathlib import Path

import pytest
from grc_domain.shared.identifiers import FrameworkControlId, FrameworkId, FrameworkMappingId
from grc_framework_engine import (
    FrameworkValidationError,
    build_catalog,
    load_framework_file,
)

ROOT = Path(__file__).resolve().parents[3]
FRAMEWORKS = ROOT / "frameworks"


def test_seed_frameworks_load_with_expected_structure() -> None:
    catalog = build_catalog(
        framework_files=[
            FRAMEWORKS / "iso-27001" / "2022" / "definition.json",
            FRAMEWORKS / "nca-ecc" / "v2.0" / "definition.json",
        ],
        mapping_files=[FRAMEWORKS / "mappings" / "iso-27001_to_nca-ecc.json"],
    )

    iso = catalog.get_framework(FrameworkId("framework:iso_27001"))
    assert iso.version.label == "2022"
    assert len(iso.controls) == 2

    nca = catalog.get_framework(FrameworkId("framework:nca_ecc"))
    assert nca.region == "SA"
    assert "ar" in nca.languages


def test_seed_cross_mapping_resolves() -> None:
    catalog = build_catalog(
        framework_files=[
            FRAMEWORKS / "iso-27001" / "2022" / "definition.json",
            FRAMEWORKS / "nca-ecc" / "v2.0" / "definition.json",
        ],
        mapping_files=[FRAMEWORKS / "mappings" / "iso-27001_to_nca-ecc.json"],
    )
    targets = catalog.corresponding_controls(
        FrameworkMappingId("map:iso_27001_to_nca_ecc"),
        FrameworkControlId("iso_27001:A.8.1"),
    )
    assert str(targets[0].framework_control_id) == "nca_ecc:2-1-1"


def test_seed_coverage_computes() -> None:
    catalog = build_catalog(
        framework_files=[FRAMEWORKS / "nca-ecc" / "v2.0" / "definition.json"],
    )
    report = catalog.compute_coverage(
        FrameworkId("framework:nca_ecc"),
        frozenset({FrameworkControlId("nca_ecc:1-1-1")}),
    )
    assert report.total_controls == 2
    assert report.covered_controls == 1
    assert report.percentage == 50.0


def test_unsupported_extension_is_rejected() -> None:
    with pytest.raises(FrameworkValidationError, match="Unsupported"):
        load_framework_file(Path("framework.yaml"))
