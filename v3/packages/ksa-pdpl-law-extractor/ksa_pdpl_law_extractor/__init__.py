"""Rasheed V3 — KSA PDPL Law Knowledge Extractor.

First Arabic `*KnowledgeExtractor`. Proves the Port is language-independent, that canonical
type follows legal FUNCTION (not node name), and that a structurally-complete artifact can
carry a content-fidelity note. NFKC is a normalization STEP, not logic.
"""
from ksa_pdpl_law_extractor.extractor import KsaPdplLawKnowledgeExtractor, parse_pdpl

__all__ = ["KsaPdplLawKnowledgeExtractor", "parse_pdpl"]
