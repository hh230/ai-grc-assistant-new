from __future__ import annotations

import json
from pathlib import Path

import pytest

from knowledge_importer.chunking.profiles import load_profile_catalog


def _write_catalog(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "profiles": {
                    "iso_standard": {
                        "display_name": "ISO Standard",
                        "description": "d",
                        "recognizer": "standard_clause",
                        "skeleton": {"kind": "fixed_iso"},
                        "language_handling": "monolingual",
                        "fallback_windowing": {"window_chars": 1200, "overlap_chars": 150},
                    },
                    "procedure": {
                        "display_name": "Procedure",
                        "description": "d",
                        "recognizer": "policy_procedure",
                        "skeleton": {"kind": "step_sequence", "mode": "procedure"},
                        "language_handling": "monolingual",
                        "fallback_windowing": {"window_chars": 1200, "overlap_chars": 150},
                    },
                    "spreadsheet": {
                        "display_name": "Spreadsheet",
                        "description": "d",
                        "recognizer": "tabular",
                        "skeleton": {"kind": "tabular"},
                        "language_handling": "monolingual",
                        "fallback_windowing": {"window_chars": 1200, "overlap_chars": 150},
                    },
                },
                "category_defaults": {"ISO": "iso_standard", "COBIT": "iso_standard"},
                "format_overrides": {"xlsx": "spreadsheet"},
                "explicit_overrides": {"internal-audit--incident-response-procedure.docx": "procedure"},
            }
        ),
        encoding="utf-8",
    )


@pytest.fixture
def catalog(tmp_path: Path):
    path = tmp_path / "document_profiles.json"
    _write_catalog(path)
    return load_profile_catalog(path)


def test_category_default_resolves(catalog) -> None:
    assignment = catalog.resolve(document_id="iso--iso-27001.pdf", category="ISO", extension=".pdf")
    assert assignment.profile_id == "iso_standard"
    assert assignment.source == "category_default"


def test_category_matching_is_whitespace_insensitive(catalog) -> None:
    assignment = catalog.resolve(document_id="cobit--framework.pdf", category=" COBIT", extension=".pdf")
    assert assignment.profile_id == "iso_standard"
    assert assignment.source == "category_default"


def test_format_override_wins_over_category_default(catalog) -> None:
    assignment = catalog.resolve(document_id="iso--matrix.xlsx", category="ISO", extension=".xlsx")
    assert assignment.profile_id == "spreadsheet"
    assert assignment.source == "format_override"


def test_explicit_override_wins_over_format_and_category(catalog) -> None:
    assignment = catalog.resolve(
        document_id="internal-audit--incident-response-procedure.docx", category="Internal Audit", extension=".docx"
    )
    assert assignment.profile_id == "procedure"
    assert assignment.source == "explicit"


def test_unmapped_category_falls_through(catalog) -> None:
    assignment = catalog.resolve(document_id="unknown--doc.pdf", category="Some New Category", extension=".pdf")
    assert assignment.profile_id is None
    assert assignment.source == "unmapped"
