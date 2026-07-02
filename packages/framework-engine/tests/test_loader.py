"""Unit tests for the Framework Engine loader/validator (data -> domain aggregates)."""
from __future__ import annotations

from typing import Any

import pytest
from grc_domain.frameworks import (
    FrameworkStatus,
    MappingRelation,
)
from grc_domain.frameworks.events import FrameworkImported
from grc_domain.shared.identifiers import FrameworkControlId
from grc_framework_engine import (
    FrameworkValidationError,
    load_framework,
    load_mapping_set,
)


def framework_data(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": "framework:nca_ecc",
        "name": "NCA Essential Cybersecurity Controls",
        "version": "2.0",
        "region": "SA",
        "languages": ["ar", "en"],
        "controls": [
            {
                "id": "nca_ecc:1-1-1",
                "code": "1-1-1",
                "title": "Cybersecurity Strategy",
                "domain": "Governance",
                "requirements": [
                    {"code": "1-1-1-1", "text": "A cybersecurity strategy must be defined."}
                ],
                "evidence_expectations": [{"description": "Approved strategy document."}],
            },
            {
                "id": "nca_ecc:1-1-2",
                "code": "1-1-2",
                "title": "Cybersecurity Governance",
                "domain": "Governance",
            },
        ],
    }
    data.update(overrides)
    return data


def mapping_data(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": "map:iso_to_nca",
        "source_framework": "framework:iso_27001",
        "target_framework": "framework:nca_ecc",
        "correspondences": [
            {
                "source_control": "iso:A.5.1",
                "target_control": "nca_ecc:1-1-1",
                "relation": "equivalent",
            }
        ],
    }
    data.update(overrides)
    return data


# --- framework loading ---------------------------------------------------------------------
def test_loads_a_valid_framework_into_an_aggregate() -> None:
    framework = load_framework(framework_data())

    assert str(framework.id) == "framework:nca_ecc"
    assert framework.name == "NCA Essential Cybersecurity Controls"
    assert str(framework.version) == "2.0"
    assert framework.region == "SA"
    assert framework.languages == ("ar", "en")
    assert framework.status is FrameworkStatus.DRAFT
    assert len(framework.controls) == 2


def test_loaded_framework_preserves_control_detail() -> None:
    framework = load_framework(framework_data())
    control = framework.control(FrameworkControlId("nca_ecc:1-1-1"))

    assert control.code == "1-1-1"
    assert control.domain == "Governance"
    assert control.requirements[0].code == "1-1-1-1"
    assert control.evidence_expectations[0].description == "Approved strategy document."


def test_import_records_a_domain_event() -> None:
    framework = load_framework(framework_data())
    assert any(isinstance(event, FrameworkImported) for event in framework.pending_events)


def test_optional_fields_default_when_absent() -> None:
    framework = load_framework(framework_data(region=None, languages=None))
    assert framework.region is None
    assert framework.languages == ()


# --- framework validation ------------------------------------------------------------------
def test_missing_required_field_raises() -> None:
    data = framework_data()
    del data["name"]
    with pytest.raises(FrameworkValidationError, match="framework.name"):
        load_framework(data)


def test_empty_controls_list_raises() -> None:
    with pytest.raises(FrameworkValidationError, match="controls must not be empty"):
        load_framework(framework_data(controls=[]))


def test_duplicate_control_ids_raise() -> None:
    duplicate = framework_data()["controls"][0]
    with pytest.raises(FrameworkValidationError, match="duplicate"):
        load_framework(framework_data(controls=[duplicate, duplicate]))


def test_non_string_field_raises() -> None:
    with pytest.raises(FrameworkValidationError, match="framework.version"):
        load_framework(framework_data(version=2.0))


# --- mapping-set loading -------------------------------------------------------------------
def test_loads_a_valid_mapping_set() -> None:
    mapping_set = load_mapping_set(mapping_data())

    assert str(mapping_set.id) == "map:iso_to_nca"
    assert str(mapping_set.source_framework_id) == "framework:iso_27001"
    correspondence = mapping_set.correspondences[0]
    assert correspondence.relation is MappingRelation.EQUIVALENT
    assert str(correspondence.source.framework_control_id) == "iso:A.5.1"
    assert str(correspondence.target.framework_id) == "framework:nca_ecc"


def test_unknown_relation_raises() -> None:
    data = mapping_data()
    data["correspondences"][0]["relation"] = "sort_of_related"
    with pytest.raises(FrameworkValidationError, match="is not one of"):
        load_mapping_set(data)
