"""Unit tests for the in-memory FrameworkCatalog: lookup, cross-mapping, coverage."""
from __future__ import annotations

import pytest
from grc_domain.shared.identifiers import FrameworkControlId, FrameworkId, FrameworkMappingId
from grc_framework_engine import (
    FrameworkCatalog,
    UnknownFrameworkError,
    UnknownMappingSetError,
    load_framework,
    load_mapping_set,
)

ISO = FrameworkId("framework:iso_27001")
NCA = FrameworkId("framework:nca_ecc")


def iso_data() -> dict[str, object]:
    return {
        "id": "framework:iso_27001",
        "name": "ISO/IEC 27001:2022",
        "version": "2022",
        "controls": [
            {"id": "iso_27001:A.5.1", "code": "A.5.1", "title": "Policies", "domain": "Org"},
            {"id": "iso_27001:A.8.1", "code": "A.8.1", "title": "Endpoints", "domain": "Tech"},
        ],
    }


def nca_data() -> dict[str, object]:
    return {
        "id": "framework:nca_ecc",
        "name": "NCA ECC",
        "version": "2.0",
        "controls": [
            {"id": "nca_ecc:1-1-1", "code": "1-1-1", "title": "Strategy", "domain": "Gov"},
        ],
    }


def mapping_data() -> dict[str, object]:
    return {
        "id": "map:iso_to_nca",
        "source_framework": "framework:iso_27001",
        "target_framework": "framework:nca_ecc",
        "correspondences": [
            {
                "source_control": "iso_27001:A.5.1",
                "target_control": "nca_ecc:1-1-1",
                "relation": "related",
            }
        ],
    }


def populated_catalog() -> FrameworkCatalog:
    catalog = FrameworkCatalog()
    catalog.register_framework(load_framework(iso_data()))
    catalog.register_framework(load_framework(nca_data()))
    catalog.register_mapping_set(load_mapping_set(mapping_data()))
    return catalog


# --- lookup --------------------------------------------------------------------------------
def test_get_framework_by_id_and_version() -> None:
    catalog = populated_catalog()
    assert catalog.get_framework(ISO).name == "ISO/IEC 27001:2022"
    assert catalog.get_framework(ISO, version="2022").version.label == "2022"


def test_unknown_framework_raises() -> None:
    catalog = populated_catalog()
    with pytest.raises(UnknownFrameworkError):
        catalog.get_framework(FrameworkId("framework:does_not_exist"))
    with pytest.raises(UnknownFrameworkError):
        catalog.get_framework(ISO, version="1999")


def test_list_frameworks() -> None:
    assert len(populated_catalog().list_frameworks()) == 2


# --- cross-framework mapping ---------------------------------------------------------------
def test_corresponding_controls_resolves_across_frameworks() -> None:
    catalog = populated_catalog()
    targets = catalog.corresponding_controls(
        FrameworkMappingId("map:iso_to_nca"), FrameworkControlId("iso_27001:A.5.1")
    )
    assert len(targets) == 1
    assert str(targets[0].framework_control_id) == "nca_ecc:1-1-1"
    assert targets[0].framework_id == NCA


def test_unknown_mapping_set_raises() -> None:
    with pytest.raises(UnknownMappingSetError):
        populated_catalog().corresponding_controls(
            FrameworkMappingId("map:absent"), FrameworkControlId("iso_27001:A.5.1")
        )


# --- coverage ------------------------------------------------------------------------------
def test_full_coverage() -> None:
    catalog = populated_catalog()
    satisfied = frozenset(
        {FrameworkControlId("iso_27001:A.5.1"), FrameworkControlId("iso_27001:A.8.1")}
    )
    report = catalog.compute_coverage(ISO, satisfied)
    assert report.total_controls == 2
    assert report.covered_controls == 2
    assert report.gaps == ()
    assert report.percentage == 100.0


def test_partial_coverage_lists_gaps() -> None:
    catalog = populated_catalog()
    satisfied = frozenset({FrameworkControlId("iso_27001:A.5.1")})
    report = catalog.compute_coverage(ISO, satisfied)
    assert report.covered_controls == 1
    assert report.gaps == (FrameworkControlId("iso_27001:A.8.1"),)
    assert report.percentage == 50.0


def test_zero_coverage_when_nothing_satisfied() -> None:
    report = populated_catalog().compute_coverage(ISO, frozenset())
    assert report.covered_controls == 0
    assert report.percentage == 0.0
