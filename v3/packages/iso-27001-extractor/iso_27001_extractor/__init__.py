"""Rasheed V3 — ISO/IEC 27001 Knowledge Extractor.

A `*KnowledgeExtractor` behind `KnowledgeExtractionPort`. First **Licensed**,
**multi-structure** source: extracts Annex A (4 Themes → 93 Controls) and records a formal
`ExtractionNote` for the partial Management-Clauses rendition — it describes reality, it
does not complete it.
"""
from iso_27001_extractor.extractor import IsoKnowledgeExtractor, parse_iso_annex

__all__ = ["IsoKnowledgeExtractor", "parse_iso_annex"]
