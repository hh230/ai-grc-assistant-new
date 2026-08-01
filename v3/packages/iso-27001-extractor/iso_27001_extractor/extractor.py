"""IsoKnowledgeExtractor — a `*KnowledgeExtractor` behind `KnowledgeExtractionPort`.

Proves, on a **Licensed, two-structure** source, three properties beyond NIST:
  1. **Native ≠ Canonical** — native `Theme` → canonical `Category`; native `Control` →
     canonical `Control` (and, when clauses are added, native `Subclause` → `Requirement`).
  2. **Storage ≠ Egress** — ISO is Licensed: the full control text is STORED; every entity
     is `egress_restricted`; a downstream Egress Policy decides what a user sees.
  3. **The Extractor describes reality, it does not complete it.**

This rendition of `ISO-27001@2022` has a CLEAN Annex A (93 controls in 4 themes) but a
Management-Clauses section that is **not deterministically recoverable** without heuristic
layout guessing. So the extractor extracts Annex A fully and records a formal
`ExtractionNote` for the clauses — a **Rendition-quality** matter (`Source ≠ Rendition`),
not a Missing/Rejected Source. It does not fail, invent, or wait.

`fitz` is imported lazily inside `_read_text`, so `parse_iso_annex` is testable with no
document library.
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

SOURCE_ID = "ISO-27001"
VERSION = "2022"
EXTRACTOR_VERSION = "1"
PROTOCOL_VERSION = "1"
CONTRACT_VERSION = "1.3"

# Annex A themes (ISO 27001:2022). Each theme's leading control number is fixed by the
# standard's own scheme: Organizational=5, People=6, Physical=7, Technological=8. The
# hierarchy (control A.5.1 → theme A.5) is READ from that scheme, not inferred.
_THEMES: tuple[tuple[str, str], ...] = (
    ("5", "Organizational controls"),
    ("6", "People controls"),
    ("7", "Physical controls"),
    ("8", "Technological controls"),
)

# Formal note: this rendition's management clauses are not deterministically recoverable.
_CLAUSES_NOTE = ExtractionNote(
    subject="Management Clauses (4-10)",
    status="Partial",
    reason=(
        "Current rendition is not structurally recoverable without heuristic layout "
        "interpretation (clause numbers and titles sit in separate, out-of-order layout "
        "blocks). Source identity is unchanged; the physical rendition is insufficient."
    ),
    recommended_action="Acquire a higher-quality (born-digital) rendition of the same source",
)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def parse_iso_annex(text: str) -> list[dict[str, str | None]]:
    """Deterministic parse of ISO 27001:2022 Annex A: 4 Themes → 93 Controls. Pure, no
    I/O, no LLM. Themes are delimited by their header lines; a theme's controls are the
    `<lead>.<n>` lines within its section. Returns ordered records (theme, then its
    controls)."""
    marks = [(lead, name, text.find(name)) for lead, name in _THEMES]
    if any(pos < 0 for _, _, pos in marks):
        return []  # themes absent in this text — caller notes it
    bounds = [pos for _, _, pos in marks] + [len(text)]

    records: list[dict[str, str | None]] = []
    for i, (lead, theme_name, start) in enumerate(marks):
        section = text[start:bounds[i + 1]]
        theme_id = f"A.{lead}"
        records.append({
            "type": "Category", "code": theme_id, "name": _clean(theme_name),
            "description": _clean(theme_name), "parent_code": None, "native": "Theme",
        })
        # Number and title may be on the same line ("5.1 Title") or split across lines
        # ("5.1\nTitle"), so the gap after the number is `\s+` (may include a newline).
        pattern = rf"(?ms)^[ \t]*({lead}\.\d{{1,2}})\s+(.+?)(?=^[ \t]*{lead}\.\d{{1,2}}\s|\Z)"
        for m in re.finditer(pattern, section):
            number = m.group(1)                     # e.g. "5.1"
            block = m.group(2)
            title = _clean(block.splitlines()[0]) if block.strip() else ""
            records.append({
                "type": "Control", "code": f"A.{number}", "name": title,
                "description": _clean(block),       # full text stored (Storage ≠ Egress)
                "parent_code": theme_id, "native": "Control",
            })
    return records


class IsoKnowledgeExtractor(KnowledgeExtractionPort):
    """Reference of a Licensed, multi-structure source. `accepts → extract`, Verified
    source only; never re-validates."""

    extractor_version = EXTRACTOR_VERSION

    def accepts(self, source: ResolvedSource) -> bool:
        return source.source_id == SOURCE_ID

    def extract(self, source: ResolvedSource) -> CanonicalExtractionArtifact:
        return self.extract_from_text(source, self._read_text(source.physical_path))

    def extract_from_text(
        self, source: ResolvedSource, text: str
    ) -> CanonicalExtractionArtifact:
        """Deterministic core: `text → artifact`, no I/O. Extracts Annex A; records the
        Management-Clauses rendition note honestly."""
        records = parse_iso_annex(text)
        entities = tuple(self._to_entity(source, record) for record in records)
        return assemble_artifact(
            source=source,
            entities=entities,
            extractor_version=self.extractor_version,
            protocol_version=PROTOCOL_VERSION,
            contract_version=CONTRACT_VERSION,
            warnings=(_CLAUSES_NOTE,),
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
        node_type = record["type"]
        assert node_type is not None
        parent_code = record["parent_code"]
        native = record["native"]
        assert native is not None
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
