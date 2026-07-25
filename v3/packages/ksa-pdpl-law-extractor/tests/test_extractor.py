"""Tests for the KSA PDPL extractor. DoD = PROOF of three new properties:
  1. Language does not change the Port (an Arabic source → contract-conforming artifact),
  2. Canonical type follows legal FUNCTION, not node name (same native `Provision` →
     `Definition` or `Requirement`), and the definitions detector is structural, never by
     article number,
  3. Structural Completeness ≠ Content Fidelity (a formal content note, no algorithmic fix).

Fixtures use short synthetic Arabic — the real (Public-Domain) document is exercised by the
skippable integration test.
"""
from __future__ import annotations

import glob
import unicodedata
from dataclasses import replace

import pytest

from knowledge_extraction.port import KnowledgeExtractionPort, ResolvedSource, SourceFacets
from ksa_pdpl_law_extractor import KsaPdplLawKnowledgeExtractor, parse_pdpl

# Article 1 = definitions ("term: meaning"); Article 2 = obligations.
FIXTURE = (
    "المادة الأولى:\n"
    "1- النظام: نظام حماية البيانات الشخصية.\n"
    "2- اللائحة: اللائحة التنفيذية للنظام.\n"
    "المادة الثانية:\n"
    "1- يهدف النظام إلى حماية خصوصية الأفراد.\n"
    "2- تسري أحكام النظام على البيانات الشخصية.\n"
)
# Definitions live in Article 2 here — proves detection is by STRUCTURE, not number.
FIXTURE_DEFS_IN_ART2 = (
    "المادة الأولى:\n"
    "1- يهدف هذا النظام إلى تنظيم المعالجة.\n"
    "المادة الثانية:\n"
    "1- النظام: تعريف النظام.\n"
    "2- البيانات: تعريف البيانات الشخصية.\n"
)


def _source() -> ResolvedSource:
    return ResolvedSource(
        source_id="KSA-PDPL-LAW", version="2023", language="AR", variant="Official",
        physical_path="/opaque/pdpl.pdf", sha256="x",
        facets=SourceFacets(
            authority="Regulatory", license="Public-Domain", stability="Living",
            genre="Law", grc_domains=("PRIV", "CMP", "LEG", "GOV"),
        ),
    )


def _artifact(text: str = FIXTURE):
    return KsaPdplLawKnowledgeExtractor().extract_from_text(_source(), text)


def test_parse_is_deterministic() -> None:
    assert parse_pdpl(FIXTURE) == parse_pdpl(FIXTURE)


# --- Property 1: language does not change the Port --------------------------
def test_language_independent_conforms_to_port() -> None:
    extractor = KsaPdplLawKnowledgeExtractor()
    assert isinstance(extractor, KnowledgeExtractionPort)
    assert extractor.accepts(_source()) is True                       # Arabic source
    assert extractor.accepts(replace(_source(), source_id="ISO-27001")) is False
    art = _artifact()
    assert art.summary.language == "AR"
    assert art.identity.artifact_id.startswith("KSA-PDPL-LAW@2023~")   # same Port, no exception


# --- Property 2: canonical by FUNCTION, detector not by number --------------
def test_canonical_type_follows_function_not_name() -> None:
    art = _artifact()
    articles = [e for e in art.entities if e.native_node_type == "Article"]
    provisions = [e for e in art.entities if e.native_node_type == "Provision"]
    assert all(a.type == "Requirement" for a in articles)             # article node = Requirement
    # Article 1's provisions are Definitions; Article 2's are Requirements — SAME native label:
    defs = [e for e in provisions if e.type == "Definition"]
    reqs = [e for e in provisions if e.type == "Requirement"]
    assert len(defs) == 2 and len(reqs) == 2
    assert all(e.native_node_type == "Provision" for e in defs + reqs)  # native identical…
    # …canonical differs by function. A definition splits into term (name) + meaning (desc):
    nizam = next(e for e in defs if e.entity_id.endswith("Art-1.1"))
    assert nizam.name == "النظام" and nizam.description != ""


def test_definition_detector_is_structural_not_positional() -> None:
    art = _artifact(FIXTURE_DEFS_IN_ART2)
    # definitions are in Article 2 here; the detector must still find them there
    art2_children = [e for e in art.entities if e.entity_id.startswith("KSA-PDPL-LAW@2023::Art-2.")]
    art1_children = [e for e in art.entities if e.entity_id.startswith("KSA-PDPL-LAW@2023::Art-1.")]
    assert all(e.type == "Definition" for e in art2_children)
    assert all(e.type == "Requirement" for e in art1_children)


# --- Property 3: describe reality — including when it is clean --------------
def test_normalization_recorded_and_no_invented_note() -> None:
    art = _artifact()
    assert art.summary.normalization == ("NFKC",)          # NFKC is a STEP, recorded
    # content is clean → the extractor invents no problem (no false note)
    assert art.summary.warnings == 0
    assert art.warnings == ()


# --- DoD: contract, hierarchy, reproducibility, Public-Domain egress -------
def test_contract_hierarchy_and_reproducibility() -> None:
    art = _artifact()
    assert art.summary.counts_by_type == {"Requirement": 4, "Definition": 2}
    assert art.summary.structural_relationships == 4       # 4 provisions → their articles
    assert all(e.egress_restricted is False for e in art.entities)  # PDPL is Public-Domain
    ids = {e.entity_id for e in art.entities}
    for e in art.entities:
        if e.parent is not None:
            assert e.parent in ids
    assert _artifact().identity.content_hash == art.identity.content_hash


# --- Integration: the real Arabic corpus PDF (skips where absent) ----------
def _real_pdf() -> str | None:
    base = "/Users/mohamedalsayyar/Documents/قاعدة بيانات مشروع Ai GRC/Laws"
    hits = glob.glob(base + "/نظام حماية البيانات الشخصية.pdf")
    return hits[0] if hits else None


@pytest.mark.skipif(_real_pdf() is None, reason="PDPL corpus PDF not present")
def test_real_pdpl_structure() -> None:
    try:
        import fitz  # noqa: F401
    except ImportError:
        pytest.skip("fitz not available")
    source = replace(_source(), physical_path=_real_pdf() or "")
    art = KsaPdplLawKnowledgeExtractor().extract(source)
    counts = art.summary.counts_by_type
    assert counts.get("Requirement", 0) >= 40          # ~43 articles + provisions
    assert counts.get("Definition", 0) >= 15           # Article-1 style definitions detected
    assert art.summary.warnings == 0                    # content verified clean → no invented note
    assert art.summary.normalization == ("NFKC",)
    assert all(e.egress_restricted is False for e in art.entities)  # Public-Domain
    assert art.identity.content_hash == KsaPdplLawKnowledgeExtractor().extract(source).identity.content_hash
