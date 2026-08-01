"""Tests for the NIST CSF Reference Realization.

The Definition of Done is PROOF of the boundary, not entity count. These tests assert
exactly the five DoD properties the owner set:
  1. the extractor conforms to the Port,
  2. the artifact satisfies the contract,
  3. re-running yields the same content_hash,
  4. no human decision at runtime (deterministic),
  5. no invented knowledge (every entity traces to source text).
"""
from __future__ import annotations

import glob
from dataclasses import replace

import pytest

from knowledge_extraction.port import (
    CanonicalExtractionArtifact,
    KnowledgeExtractionPort,
    ResolvedSource,
    SourceFacets,
)
from nist_csf_extractor import NistCsfKnowledgeExtractor, parse_nist_csf

# A small, real (Public-Domain) slice of the NIST CSF 2.0 Core — 2 Functions,
# 3 Categories, 4 Subcategories — enough to prove all three levels + parent linking.
FIXTURE = (
    "GOVERN (GV): The organization's cybersecurity risk management strategy, "
    "expectations, and policy are established, communicated, and monitored \n"
    "• Organizational Context (GV.OC): The circumstances surrounding the "
    "organization's cybersecurity risk management decisions are understood \n"
    "o GV.OC-01: The organizational mission is understood and informs "
    "cybersecurity risk management \n"
    "o GV.OC-02: Internal and external stakeholders are understood \n"
    "• Risk Management Strategy (GV.RM): The organization's priorities, "
    "constraints, and risk tolerance are established \n"
    "o GV.RM-01: Risk management objectives are established and agreed to by "
    "stakeholders \n"
    "IDENTIFY (ID): The organization's current cybersecurity risks are understood \n"
    "• Asset Management (ID.AM): Assets that enable the organization to achieve "
    "business purposes are managed \n"
    "o ID.AM-01: Inventories of hardware managed by the organization are maintained \n"
)


def _nist_source() -> ResolvedSource:
    return ResolvedSource(
        source_id="NIST-CSF", version="2.0", language="EN", variant="Official",
        physical_path="/opaque/does-not-matter.pdf", sha256="n/a",
        facets=SourceFacets(
            authority="Normative", license="Public-Domain", stability="Version-bound",
            genre="Framework", grc_domains=("CYB", "GOV", "RSK", "ISEC"),
        ),
    )


def _artifact() -> CanonicalExtractionArtifact:
    return NistCsfKnowledgeExtractor().extract_from_text(_nist_source(), FIXTURE)


# --- DoD 4: deterministic parse, no human decision -------------------------
def test_parse_is_deterministic() -> None:
    assert parse_nist_csf(FIXTURE) == parse_nist_csf(FIXTURE)


def test_parse_counts_and_hierarchy() -> None:
    records, difficulties = parse_nist_csf(FIXTURE)
    assert difficulties == []
    by_type = [r["type"] for r in records]
    assert by_type.count("Function") == 2
    assert by_type.count("Category") == 3
    assert by_type.count("Subcategory") == 4
    codes = {r["code"]: r["parent_code"] for r in records}
    assert codes["GV.OC"] == "GV" and codes["ID.AM"] == "ID"          # cat → function
    assert codes["GV.OC-01"] == "GV.OC" and codes["ID.AM-01"] == "ID.AM"  # sub → category


# --- DoD 1: conforms to the Port -------------------------------------------
def test_extractor_conforms_to_port() -> None:
    extractor = NistCsfKnowledgeExtractor()
    assert isinstance(extractor, KnowledgeExtractionPort)
    assert extractor.accepts(_nist_source()) is True
    # accepts is family-scoped — it declines a source it does not handle:
    assert extractor.accepts(replace(_nist_source(), source_id="ISO-27001")) is False


# --- DoD 2: the artifact satisfies the contract ----------------------------
def test_artifact_satisfies_contract() -> None:
    art = _artifact()
    assert art.summary.counts_by_type == {"Function": 2, "Category": 3, "Subcategory": 4}
    assert art.summary.entities == 9
    assert art.summary.unknown == 0
    # 9 entities, 2 Functions have no parent → 7 `contains` structural relationships
    assert art.summary.structural_relationships == 7
    assert len(art.structural_relationships) == 7
    assert all(r.type == "contains" for r in art.structural_relationships)
    assert art.identity.source_id == "NIST-CSF" and art.identity.source_version == "2.0"
    assert art.identity.artifact_id.startswith("NIST-CSF@2.0~x1~p1~c1.3~")


# --- DoD 3: re-run → identical content_hash --------------------------------
def test_reproducible_content_hash() -> None:
    a1, a2 = _artifact(), _artifact()
    assert a1.identity.content_hash == a2.identity.content_hash
    assert a1.identity.artifact_id == a2.identity.artifact_id


# --- DoD 5: no invented knowledge ------------------------------------------
def test_no_invented_knowledge() -> None:
    art = _artifact()
    cleaned_source = " ".join(FIXTURE.split())
    for entity in art.entities:
        assert entity.number is not None and entity.number in FIXTURE  # code is in source
        assert entity.provenance.location.endswith(entity.number)       # traceable
        assert entity.description in cleaned_source                       # text is from source
        assert entity.egress_restricted is False                         # NIST is Public-Domain


def test_every_parent_resolves_to_an_emitted_entity() -> None:
    art = _artifact()
    ids = {e.entity_id for e in art.entities}
    for entity in art.entities:
        if entity.parent is not None:
            assert entity.parent in ids  # referential integrity of the hierarchy


# --- Integration: the real corpus PDF (skips where absent) -----------------
def _real_pdf() -> str | None:
    base = "/Users/mohamedalsayyar/Documents/قاعدة بيانات مشروع Ai GRC/NIST/NIST CSF"
    hits = glob.glob(base + "/*.pdf")
    return hits[0] if hits else None


@pytest.mark.skipif(_real_pdf() is None, reason="NIST CSF corpus PDF not present")
def test_real_nist_csf_full_counts() -> None:
    try:
        import fitz  # noqa: F401
    except ImportError:
        pytest.skip("fitz not available")
    source = replace(_nist_source(), physical_path=_real_pdf() or "")
    art = NistCsfKnowledgeExtractor().extract(source)
    assert art.summary.counts_by_type == {"Function": 6, "Category": 22, "Subcategory": 106}
    assert art.summary.structural_relationships == 128  # 134 − 6 top-level Functions
    # reproducible against the real document too
    assert art.identity.content_hash == NistCsfKnowledgeExtractor().extract(source).identity.content_hash
