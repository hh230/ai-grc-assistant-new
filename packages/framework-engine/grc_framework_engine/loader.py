"""Load and validate framework definition *data* into domain aggregates.

This is the Framework Engine's anti-corruption layer (CLAUDE.md §13, §15): it translates
parsed, untrusted framework definition data (from YAML/JSON under ``/frameworks``) into clean
``Framework`` / ``FrameworkMappingSet`` domain aggregates, validating it against the canonical
schema first. No framework name is ever hardcoded into control flow — adding a regulator is a
data change, not a code change.

Canonical framework schema (a parsed mapping)::

    id: "framework:nca_ecc"          # required, stable id
    name: "NCA Essential Cybersecurity Controls"
    version: "2.0"                   # required; assessments pin this
    region: "SA"                     # optional
    languages: ["ar", "en"]          # optional
    controls:                        # required, non-empty
      - id: "nca_ecc:1-1-1"          # required, unique within the framework
        code: "1-1-1"                # required, unique within the framework
        title: "Cybersecurity Strategy"
        domain: "Governance"         # the control family
        requirements:                # optional
          - { code: "1-1-1-1", text: "A strategy must be defined." }
        evidence_expectations:       # optional
          - { description: "Approved strategy document." }

Canonical mapping-set schema::

    id: "map:iso_to_nca"
    source_framework: "framework:iso_27001"
    target_framework: "framework:nca_ecc"
    correspondences:
      - { source_control: "iso:A.5.1", target_control: "nca_ecc:1-1-1", relation: "equivalent" }
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence

from grc_domain.frameworks import (
    ControlCorrespondence,
    EvidenceExpectation,
    Framework,
    FrameworkControl,
    FrameworkControlRef,
    FrameworkMappingSet,
    FrameworkVersion,
    MappingRelation,
    Requirement,
)
from grc_domain.shared.identifiers import (
    FrameworkControlId,
    FrameworkId,
    FrameworkMappingId,
)

from .exceptions import FrameworkValidationError


def load_framework(data: Mapping[str, object]) -> Framework:
    """Validate and translate a framework definition mapping into a ``Framework`` aggregate."""
    location = "framework"
    control_data = _mapping_sequence(data, "controls", location, required=True)
    if not control_data:
        raise FrameworkValidationError("framework.controls must not be empty")
    controls = tuple(
        _load_control(item, f"framework.controls[{index}]")
        for index, item in enumerate(control_data)
    )
    _ensure_unique([str(control.id) for control in controls], "framework.controls[].id")
    _ensure_unique([control.code for control in controls], "framework.controls[].code")
    return Framework.import_definition(
        id=FrameworkId(_require_str(data, "id", location)),
        name=_require_str(data, "name", location),
        version=FrameworkVersion(_require_str(data, "version", location)),
        controls=controls,
        region=_optional_str(data, "region", location),
        languages=_string_tuple(data, "languages", location),
    )


def load_mapping_set(data: Mapping[str, object]) -> FrameworkMappingSet:
    """Validate and translate a cross-framework mapping mapping into a ``FrameworkMappingSet``."""
    location = "mapping_set"
    source_framework = FrameworkId(_require_str(data, "source_framework", location))
    target_framework = FrameworkId(_require_str(data, "target_framework", location))
    correspondence_data = _mapping_sequence(data, "correspondences", location, required=True)
    correspondences = tuple(
        _load_correspondence(
            item, source_framework, target_framework, f"mapping_set.correspondences[{index}]"
        )
        for index, item in enumerate(correspondence_data)
    )
    return FrameworkMappingSet(
        id=FrameworkMappingId(_require_str(data, "id", location)),
        source_framework_id=source_framework,
        target_framework_id=target_framework,
        correspondences=correspondences,
    )


def _load_control(data: Mapping[str, object], location: str) -> FrameworkControl:
    requirements = tuple(
        Requirement(
            code=_require_str(item, "code", f"{location}.requirements[{index}]"),
            text=_require_str(item, "text", f"{location}.requirements[{index}]"),
        )
        for index, item in enumerate(
            _mapping_sequence(data, "requirements", location, required=False)
        )
    )
    evidence_expectations = tuple(
        EvidenceExpectation(
            description=_require_str(
                item, "description", f"{location}.evidence_expectations[{index}]"
            )
        )
        for index, item in enumerate(
            _mapping_sequence(data, "evidence_expectations", location, required=False)
        )
    )
    return FrameworkControl(
        id=FrameworkControlId(_require_str(data, "id", location)),
        code=_require_str(data, "code", location),
        title=_require_str(data, "title", location),
        domain=_require_str(data, "domain", location),
        requirements=requirements,
        evidence_expectations=evidence_expectations,
    )


def _load_correspondence(
    data: Mapping[str, object],
    source_framework: FrameworkId,
    target_framework: FrameworkId,
    location: str,
) -> ControlCorrespondence:
    return ControlCorrespondence(
        source=FrameworkControlRef(
            framework_id=source_framework,
            framework_control_id=FrameworkControlId(_require_str(data, "source_control", location)),
        ),
        target=FrameworkControlRef(
            framework_id=target_framework,
            framework_control_id=FrameworkControlId(_require_str(data, "target_control", location)),
        ),
        relation=_load_relation(data, location),
    )


def _load_relation(data: Mapping[str, object], location: str) -> MappingRelation:
    raw = _require_str(data, "relation", location)
    try:
        return MappingRelation(raw)
    except ValueError as exc:
        valid = ", ".join(relation.value for relation in MappingRelation)
        raise FrameworkValidationError(
            f"{location}.relation {raw!r} is not one of: {valid}"
        ) from exc


# --- validation primitives -----------------------------------------------------------------
def _require_str(data: Mapping[str, object], key: str, location: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise FrameworkValidationError(f"{location}.{key} must be a non-empty string")
    return value


def _optional_str(data: Mapping[str, object], key: str, location: str) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise FrameworkValidationError(f"{location}.{key} must be a non-empty string when present")
    return value


def _string_tuple(data: Mapping[str, object], key: str, location: str) -> tuple[str, ...]:
    value = data.get(key)
    if value is None:
        return ()
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise FrameworkValidationError(f"{location}.{key} must be a list of strings")
    items: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise FrameworkValidationError(f"{location}.{key}[{index}] must be a non-empty string")
        items.append(item)
    return tuple(items)


def _mapping_sequence(
    data: Mapping[str, object], key: str, location: str, *, required: bool
) -> list[Mapping[str, object]]:
    value = data.get(key)
    if value is None:
        if required:
            raise FrameworkValidationError(f"{location}.{key} is required")
        return []
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise FrameworkValidationError(f"{location}.{key} must be a list")
    items: list[Mapping[str, object]] = []
    for index, item in enumerate(value):
        if not isinstance(item, Mapping):
            raise FrameworkValidationError(f"{location}.{key}[{index}] must be a mapping")
        items.append(item)
    return items


def _ensure_unique(values: list[str], location: str) -> None:
    seen: set[str] = set()
    for value in values:
        if value in seen:
            raise FrameworkValidationError(f"{location} has a duplicate value: {value!r}")
        seen.add(value)
