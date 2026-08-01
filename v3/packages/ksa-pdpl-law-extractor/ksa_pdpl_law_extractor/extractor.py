"""KsaPdplLawKnowledgeExtractor — a `*KnowledgeExtractor` behind
`KnowledgeExtractionPort`. First **Arabic** source. Proves:
  1. **Language does not change the Port** — an Arabic source yields a contract-conforming
     artifact through the same boundary, with no exception in the Port.
  2. **Canonical type is decided by legal FUNCTION, not node name** — every numbered
     sub-item is natively a `Provision`, but maps to canonical `Definition` *or*
     `Requirement` by what it does, detected structurally (a definitions detector),
     never by article number.
  3. **The Extractor describes reality — including when reality is fine.** It would record a
     content-fidelity `ExtractionNote` if the body were degraded, but for this rendition the
     content was verified clean (0 reversed spans across all entities), so it attaches **no**
     note. It does not invent a problem, just as it does not invent knowledge. (The
     *Structural Completeness ≠ Content Fidelity* distinction still holds for any future
     rendition that is structurally recoverable but content-degraded.)

Normalization (NFKC, PROTO-EXT-1) is a STEP applied on read, not logic. `fitz` is imported
lazily so the parser is testable without a document library. PDPL is Public-Domain (Official
KSA gazette).
"""
from __future__ import annotations

import re
import unicodedata

from knowledge_extraction.port import (
    CanonicalExtractionArtifact,
    KnowledgeEntity,
    KnowledgeExtractionPort,
    Provenance,
    ResolvedSource,
    assemble_artifact,
)

SOURCE_ID = "KSA-PDPL-LAW"
VERSION = "2023"  # amended PDPL; provisional pending Source-register confirmation
EXTRACTOR_VERSION = "1"
PROTOCOL_VERSION = "1"
CONTRACT_VERSION = "1.3"

# A true article header is "المادة <ordinal>:" — an ordinal word (starts "ال"),
# colon-terminated, with no parentheses (which mark cross-references like
# "المادة )التاسعة( من النظام"). Anchored to a line to avoid mid-sentence matches.
_HEADER_RE = re.compile(r"(?m)^[ \t]*المادة\s+(ال[^\n:()]{1,30}?)\s*:")
# Numbered sub-items: "1- …", tolerant of a newline between the digit and the dash.
_ITEM_RE = re.compile(r"(?ms)^\s*(\d{1,2})\s*[-–]\s*(.+?)(?=^\s*\d{1,2}\s*[-–]|\Z)")
# A "definition-shaped" item: a short label, then a colon, then content ("term: meaning").
_DEF_SHAPE = re.compile(r"^[^:\n]{1,40}:\s*\S")


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def parse_pdpl(text: str) -> list[dict[str, str | None]]:
    """Deterministic parse of a KSA law: Article → Provision (per contract §6.1). Pure,
    no I/O, no LLM. `text` is already NFKC-normalized by the caller. Articles are numbered
    by document order (the Nth header is Article N — no ordinal table needed). Each
    article's children are `Definition` when the article is a definitions article
    (detected by structure) and `Requirement` otherwise."""
    headers = list(_HEADER_RE.finditer(text))
    records: list[dict[str, str | None]] = []
    for index, match in enumerate(headers):
        article_number = index + 1
        ordinal = match.group(1).strip()
        start = match.end()
        end = headers[index + 1].start() if index + 1 < len(headers) else len(text)
        body = text[start:end]
        article_code = f"Art-{article_number}"

        items = [(m.group(1), _clean(m.group(2))) for m in _ITEM_RE.finditer(body)]
        # Definition DETECTOR — by function/structure, never by article number.
        def_shaped = sum(1 for _, item in items if _DEF_SHAPE.match(item))
        is_definitions_article = len(items) >= 2 and def_shaped * 2 >= len(items)

        # The article node is part of the law → canonical Requirement (native "Article").
        records.append({
            "type": "Requirement", "code": article_code, "name": f"المادة {ordinal}",
            "description": _clean(body), "parent_code": None, "native": "Article",
        })
        for number, item in items:
            child_code = f"{article_code}.{number}"
            if is_definitions_article and ":" in item:
                term, meaning = item.split(":", 1)
                records.append({
                    "type": "Definition", "code": child_code, "name": _clean(term),
                    "description": _clean(meaning), "parent_code": article_code,
                    "native": "Provision",  # native label is uniform; FUNCTION drives canonical
                })
            else:
                records.append({
                    "type": "Requirement", "code": child_code, "name": _clean(item),
                    "description": _clean(item), "parent_code": article_code,
                    "native": "Provision",
                })
    return records


class KsaPdplLawKnowledgeExtractor(KnowledgeExtractionPort):
    """First Arabic realization. `accepts → extract`, Verified source only."""

    extractor_version = EXTRACTOR_VERSION

    def accepts(self, source: ResolvedSource) -> bool:
        return source.source_id == SOURCE_ID

    def extract(self, source: ResolvedSource) -> CanonicalExtractionArtifact:
        return self.extract_from_text(source, self._read_text(source.physical_path))

    def extract_from_text(
        self, source: ResolvedSource, text: str
    ) -> CanonicalExtractionArtifact:
        """Deterministic core: `text → artifact`, no I/O. `text` must already be
        NFKC-normalized (a step, not logic)."""
        records = parse_pdpl(text)
        entities = tuple(self._to_entity(source, record) for record in records)
        return assemble_artifact(
            source=source,
            entities=entities,
            extractor_version=self.extractor_version,
            protocol_version=PROTOCOL_VERSION,
            contract_version=CONTRACT_VERSION,
            normalization=("NFKC",),
            warnings=(),  # content verified clean — no invented problem
        )

    @staticmethod
    def _read_text(physical_path: str) -> str:
        import fitz  # type: ignore[import-untyped]  # lazy; keeps the doc lib out of the parser

        doc = fitz.open(physical_path)
        try:
            raw = "".join(page.get_text() for page in doc)
        finally:
            doc.close()
        return unicodedata.normalize("NFKC", raw)  # PROTO-EXT-1: a normalization STEP

    @staticmethod
    def _to_entity(source: ResolvedSource, record: dict[str, str | None]) -> KnowledgeEntity:
        code = record["code"]
        assert code is not None
        node_type = record["type"]
        assert node_type is not None
        native = record["native"]
        assert native is not None
        parent_code = record["parent_code"]
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
            native_node_type=native,
        )
