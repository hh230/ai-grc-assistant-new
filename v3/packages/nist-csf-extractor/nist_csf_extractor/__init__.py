"""Rasheed V3 — NIST CSF Knowledge Extractor (the Reference Realization).

A `*KnowledgeExtractor` behind `KnowledgeExtractionPort`. Proves the boundary is
source-independent (Function/Category/Subcategory — no "Clause"). The artifact FORMAT
lives in the shared `artifact-writers` package, not here.
"""
from nist_csf_extractor.extractor import (
    NistCsfKnowledgeExtractor,
    parse_nist_csf,
)

__all__ = ["NistCsfKnowledgeExtractor", "parse_nist_csf"]
