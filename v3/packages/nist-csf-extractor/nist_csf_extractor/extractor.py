"""NistCsfKnowledgeExtractor — the **Reference Realization** behind
`KnowledgeExtractionPort` (ADR 0056).

Its job is to *prove the boundary*: a Verified NIST-CSF source becomes a Canonical
Extraction Artifact **deterministically, with zero runtime human decisions and zero
invented knowledge**. NIST CSF 2.0 is Public-Domain (US Gov).

A document library (`fitz`) lives HERE and is imported *lazily* inside `_read_text`,
so the deterministic parser is testable with no document library at all — and the
Port, of course, imports none.

NIST CSF 2.0 native structure (the source's own identifier scheme encodes the
hierarchy — reading it is not inference):

    Function     GV          "GOVERN (GV): <description>"
    Category     GV.OC       "• Organizational Context (GV.OC): <description>"
    Subcategory  GV.OC-01    "o GV.OC-01: <statement>"
"""
from __future__ import annotations

import re

from knowledge_extraction.port import (
    CanonicalExtractionArtifact,
    ExtractionNote,
    KnowledgeEntity,
    KnowledgeExtractionPort,
    Provenance,
    ResolvedSource,
    assemble_artifact,
)

SOURCE_ID = "NIST-CSF"
VERSION = "2.0"
EXTRACTOR_VERSION = "1"
PROTOCOL_VERSION = "1"
CONTRACT_VERSION = "1.3"

_FUNCTION_CODES: tuple[str, ...] = ("GV", "ID", "PR", "DE", "RS", "RC")

# A "next unit begins" boundary: the next subcategory, the next category bullet, a
# function header, or end-of-text. Used to bound each unit's description.
_NEXT = r"(?=\s+o\s+[A-Z]{2}\.[A-Z]{2}-\d{2}:|\s+•|\s+[A-Z]{4,}\s+\([A-Z]{2}\):|\Z)"
_FUNC_RE = re.compile(
    r"([A-Z]{4,})\s+\((" + "|".join(_FUNCTION_CODES) + r")\):\s*(.+?)"
    r"(?=\s+•|\s+[A-Z]{4,}\s+\([A-Z]{2}\):|\Z)",
    re.S,
)
_CAT_RE = re.compile(
    r"•\s*([A-Za-z][A-Za-z ,/&+-]+?)\s+\(([A-Z]{2}\.[A-Z]{2})\):\s*(.+?)" + _NEXT, re.S
)
_SUB_RE = re.compile(r"o\s+([A-Z]{2}\.[A-Z]{2}-\d{2}):\s*(.+?)" + _NEXT, re.S)


def _clean(text: str) -> str:
    """Collapse the PDF's mid-sentence line wraps into single-spaced text."""
    return re.sub(r"\s+", " ", text).strip()


def parse_nist_csf(text: str) -> tuple[list[dict[str, str | None]], list[ExtractionNote]]:
    """Deterministic, pure parse of NIST CSF Core text into ordered records.

    No I/O, no LLM, no human decision. Returns `(records, difficulties)`. Records are
    ordered Functions (canonical order) → Categories (by code) → Subcategories (by
    code) so the artifact's content hash is stable across runs.
    """
    functions: dict[str, tuple[str, str]] = {}
    for name, code, desc in _FUNC_RE.findall(text):
        functions.setdefault(code, (_clean(name), _clean(desc)))
    categories: dict[str, tuple[str, str]] = {}
    for name, code, desc in _CAT_RE.findall(text):
        categories.setdefault(code, (_clean(name), _clean(desc)))
    subcategories: dict[str, str] = {}
    for code, statement in _SUB_RE.findall(text):
        subcategories.setdefault(code, _clean(statement))

    difficulties: list[ExtractionNote] = []
    records: list[dict[str, str | None]] = []
    for code in _FUNCTION_CODES:
        if code not in functions:
            continue  # a partial source need not contain every function — not a defect
        name, desc = functions[code]
        records.append(
            {"type": "Function", "code": code, "name": name,
             "description": desc, "parent_code": None}
        )
    for code in sorted(categories):
        name, desc = categories[code]
        parent = code[:2]
        if parent not in functions:
            difficulties.append(ExtractionNote(
                subject=code, status="Orphan",
                reason=f"Category references unknown Function {parent}",
                recommended_action="verify source structure",
            ))
        records.append(
            {"type": "Category", "code": code, "name": name,
             "description": desc, "parent_code": parent}
        )
    for code in sorted(subcategories):
        parent = code.split("-")[0]
        if parent not in categories:
            difficulties.append(ExtractionNote(
                subject=code, status="Orphan",
                reason=f"Subcategory references unknown Category {parent}",
                recommended_action="verify source structure",
            ))
        statement = subcategories[code]
        records.append(
            {"type": "Subcategory", "code": code, "name": statement,
             "description": statement, "parent_code": parent}
        )
    return records, difficulties


class NistCsfKnowledgeExtractor(KnowledgeExtractionPort):
    """Reference Realization. `accepts(source) → extract(source) → Artifact`, on a
    Verified source only (the Port asserts `Ready`); it never re-validates the source."""

    extractor_version = EXTRACTOR_VERSION

    def accepts(self, source: ResolvedSource) -> bool:
        return source.source_id == SOURCE_ID

    def extract(self, source: ResolvedSource) -> CanonicalExtractionArtifact:
        return self.extract_from_text(source, self._read_text(source.physical_path))

    def extract_from_text(
        self, source: ResolvedSource, text: str
    ) -> CanonicalExtractionArtifact:
        """The deterministic core: `text → artifact`, no I/O. Tests exercise this
        directly, proving the boundary without any document library."""
        records, difficulties = parse_nist_csf(text)
        entities = tuple(self._to_entity(source, record) for record in records)
        return assemble_artifact(
            source=source,
            entities=entities,
            extractor_version=self.extractor_version,
            protocol_version=PROTOCOL_VERSION,
            contract_version=CONTRACT_VERSION,
            warnings=tuple(difficulties),
        )

    @staticmethod
    def _read_text(physical_path: str) -> str:
        import fitz  # type: ignore[import-untyped]  # lazy; keeps the doc lib out of the parser

        doc = fitz.open(physical_path)
        try:
            return "".join(page.get_text() for page in doc)
        finally:
            doc.close()

    @staticmethod
    def _to_entity(source: ResolvedSource, record: dict[str, str | None]) -> KnowledgeEntity:
        code = record["code"]
        assert code is not None
        parent_code = record["parent_code"]
        node_type = record["type"]
        assert node_type is not None
        return KnowledgeEntity(
            source_id=SOURCE_ID,
            version=VERSION,
            entity_id=f"{SOURCE_ID}@{VERSION}::{code}",
            parent=f"{SOURCE_ID}@{VERSION}::{parent_code}" if parent_code else None,
            type=node_type,  # type: ignore[arg-type]  # validated by the Port
            name=record["name"] or "",
            number=code,
            description=record["description"] or "",
            language=source.language,
            authority=source.facets.authority,
            license=source.facets.license,
            stability=source.facets.stability,
            confidence="100%",
            provenance=Provenance(SOURCE_ID, VERSION, f"{node_type} {code}"),
            native_node_type=node_type,
        )
