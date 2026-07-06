"""Unit tests for the trusted-source catalog loader: schema validation (an entry with an
unclassified source_type or no domains fails to load), file-loading, and — mirroring
``grc_knowledge_intelligence/tests/test_question_catalog.py`` — that the real
``/trusted-sources`` directory shipped with the repo loads cleanly."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from grc_knowledge_intelligence import KnowledgeDomain, TrustedSourceType
from grc_knowledge_research_adapters import (
    build_trusted_source_catalog,
    load_cataloged_source,
    load_cataloged_source_file,
)

_VALID = {
    "source_id": "sa-nca",
    "name": "National Cybersecurity Authority (NCA)",
    "source_type": "government_regulator",
    "url": "https://nca.gov.sa",
    "jurisdiction": "SA",
    "domains": ["cybersecurity_governance", "regulatory_obligations"],
}

_TRUSTED_SOURCES_DIR = Path(__file__).resolve().parents[3] / "trusted-sources"


def test_load_cataloged_source_builds_a_source_tagged_with_its_domains() -> None:
    cataloged = load_cataloged_source(_VALID)

    assert cataloged.source.source_id == "sa-nca"
    assert cataloged.source.source_type is TrustedSourceType.GOVERNMENT_REGULATOR
    assert cataloged.domains == (
        KnowledgeDomain.CYBERSECURITY_GOVERNANCE,
        KnowledgeDomain.REGULATORY_OBLIGATIONS,
    )


def test_load_cataloged_source_rejects_an_unclassified_source_type() -> None:
    data = {**_VALID, "source_type": "personal_blog"}

    with pytest.raises(ValueError, match="source_type"):
        load_cataloged_source(data)


def test_load_cataloged_source_rejects_an_unknown_domain() -> None:
    data = {**_VALID, "domains": ["not_a_real_domain"]}

    with pytest.raises(ValueError, match="domain"):
        load_cataloged_source(data)


def test_load_cataloged_source_rejects_empty_domains() -> None:
    data = {**_VALID, "domains": []}

    with pytest.raises(ValueError, match="domains"):
        load_cataloged_source(data)


def test_load_cataloged_source_rejects_a_missing_required_field() -> None:
    data = {key: value for key, value in _VALID.items() if key != "url"}

    with pytest.raises(ValueError, match="url"):
        load_cataloged_source(data)


def test_load_cataloged_source_file_rejects_a_non_json_suffix(tmp_path: Path) -> None:
    path = tmp_path / "source.yaml"
    path.write_text("source_id: sa-nca")

    with pytest.raises(ValueError, match="Unsupported"):
        load_cataloged_source_file(path)


def test_build_trusted_source_catalog_loads_every_given_file(tmp_path: Path) -> None:
    first = tmp_path / "sa-nca.json"
    first.write_text(json.dumps(_VALID))
    second = tmp_path / "sa-sama.json"
    second.write_text(
        json.dumps(
            {
                **_VALID,
                "source_id": "sa-sama",
                "name": "Saudi Central Bank (SAMA)",
                "url": "https://www.sama.gov.sa",
                "domains": ["governance"],
            }
        )
    )

    catalog = build_trusted_source_catalog((first, second))

    assert {cataloged.source.source_id for cataloged in catalog} == {"sa-nca", "sa-sama"}


def test_the_real_trusted_sources_directory_loads_cleanly() -> None:
    files = tuple(sorted(_TRUSTED_SOURCES_DIR.glob("*/*.json")))
    assert files, "expected at least one curated trusted source under /trusted-sources"

    catalog = build_trusted_source_catalog(files)

    assert len(catalog) == len(files)
    source_ids = [cataloged.source.source_id for cataloged in catalog]
    assert len(source_ids) == len(set(source_ids))


def test_every_real_trusted_source_url_is_https() -> None:
    """A minimal, cheap safety check on every curated entry (KI-P3, ADR-0027): a trusted
    source is never onboarded over plain, unencrypted HTTP."""
    files = tuple(sorted(_TRUSTED_SOURCES_DIR.glob("*/*.json")))
    catalog = build_trusted_source_catalog(files)

    for cataloged in catalog:
        assert cataloged.source.url.startswith("https://"), cataloged.source.source_id
