"""The library loader: the bundled ISO 27001:2022 catalog is complete and correct, malformed
definitions fail loud, and — the §13 payoff — a new framework is added as *data*, not code."""

from __future__ import annotations

import json

import pytest
from framework_library import (
    FrameworkLibrary,
    FrameworkNotFound,
    InvalidFrameworkDefinition,
    framework_from_dict,
)
from framework_library.library import framework_from_file


def test_bundled_iso_27001_is_complete_and_themed(library: FrameworkLibrary) -> None:
    fw = library.get("framework:iso_27001")
    assert fw.name == "ISO/IEC 27001:2022"
    assert len(fw.controls) == 93                        # the full Annex A
    by_theme = {d: len(fw.by_domain(d)) for d in fw.domains}
    assert by_theme == {
        "Organizational": 37, "People": 8, "Physical": 14, "Technological": 34,
    }


def test_known_controls_resolve_by_code(library: FrameworkLibrary) -> None:
    fw = library.get("framework:iso_27001")
    assert fw.get("A.8.5").title == "Secure authentication"
    assert fw.get("A.5.1").title == "Policies for information security"
    assert fw.get("A.8.5").id == "iso_27001:A.8.5"


def test_control_ids_and_codes_are_unique(library: FrameworkLibrary) -> None:
    controls = library.get("framework:iso_27001").controls
    assert len({c.id for c in controls}) == len(controls)
    assert len({c.code for c in controls}) == len(controls)


def test_missing_framework_fails_loud(library: FrameworkLibrary) -> None:
    with pytest.raises(FrameworkNotFound) as exc:
        library.get("framework:does_not_exist")
    assert "framework:iso_27001" in exc.value.available


def test_a_new_framework_is_added_as_data_not_code(tmp_path) -> None:
    # CLAUDE.md §13: dropping a definition file in makes a new framework loadable — no code change.
    definition = {
        "id": "framework:nist_csf",
        "name": "NIST CSF",
        "version": "2.0",
        "controls": [{"id": "nist:GV.OC", "code": "GV.OC", "title": "Organizational Context",
                      "domain": "Govern"}],
    }
    (tmp_path / "nist_csf.json").write_text(json.dumps(definition), encoding="utf-8")
    lib = FrameworkLibrary.from_dir(tmp_path)
    assert lib.has("framework:nist_csf")
    assert lib.get("framework:nist_csf").get("GV.OC").title == "Organizational Context"


def test_malformed_definition_fails_loud() -> None:
    with pytest.raises(InvalidFrameworkDefinition):
        framework_from_dict({"id": "x", "name": "X"})  # no 'controls'
    with pytest.raises(InvalidFrameworkDefinition):
        framework_from_dict({"id": "x", "name": "X", "controls": [{"code": "A.1"}]})  # no id


def test_from_file_rejects_non_json(tmp_path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("not json", encoding="utf-8")
    with pytest.raises(InvalidFrameworkDefinition):
        framework_from_file(bad)
