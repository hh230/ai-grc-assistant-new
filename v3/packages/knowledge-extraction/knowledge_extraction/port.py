"""
Knowledge Extraction Port — the Stage-2 boundary for Rasheed V3.

Contract: ADR 0056 (this Port) + ADR 0057 (the Canonical Extraction Artifact),
conforming to CANONICAL-MODEL.md v1.3 — §2 identity spine, §3 facets, §3.5 entity
types, §10 governance (append-only, provenance, four independent axes).

Owner constraint (ADR 0056): this module is FORMAT- and TOOLING-AGNOSTIC. Its
entire vocabulary is `Source -> Canonical Extraction Artifact`. It must never
import a document library (`fitz`, `openpyxl`, `pypdf`, `docx`, ...). It is pure
stdlib — it *cannot* import fitz because it does not depend on it. HOW a source is
opened and read is the private concern of each `*KnowledgeExtractor` realization
behind this Port. There is no `PDFExtractionPort` and no `ISOParser`.
"""
from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal, get_args

# ---------------------------------------------------------------------------
# Facet vocabularies — the four independent axes (§3). Never inferred from one
# another; inherited onto entities from the Canonical Source Register, not
# re-derived (ADR 0056 guarantee 5).
# ---------------------------------------------------------------------------
Authority = Literal[
    "Normative", "Regulatory", "Interpretive", "Reference", "Example", "Template", "Internal",
]
License = Literal["Public-Domain", "Licensed", "Internal", "Customer", "Unknown"]
Stability = Literal["Stable", "Version-bound", "Living", "Draft", "Volatile"]
Confidence = Literal["100%", "95%", "80%", "Unknown"]
Language = Literal["EN", "AR"]

# The 16 canonical Knowledge Entity Types (§3.5). A realization maps its source's
# NATIVE structure onto exactly these; the source's own node name is retained
# separately as `KnowledgeEntity.native_node_type` (ADR 0056 guarantee 7). A native
# unit with no canonical home is a contract-conflict candidate raised to the owner —
# never a silently invented type.
EntityType = Literal[
    "Domain", "Function", "Category", "Subcategory", "Clause", "Article",
    "Objective", "Principle", "Practice", "Capability", "Requirement",
    "Control", "Subcontrol", "Definition", "Annex", "Mapping-Entry",
]

ENTITY_TYPES: frozenset[str] = frozenset(get_args(EntityType))
CONFIDENCES: frozenset[str] = frozenset(get_args(Confidence))
LANGUAGES: frozenset[str] = frozenset(get_args(Language))


class ExtractionError(ValueError):
    """A realization emitted an artifact that violates the Port contract.

    Raised at the boundary so a malformed artifact never leaves it (§16 —
    fail safe, not open).
    """


# ---------------------------------------------------------------------------
# INPUT — a resolved source (identity + facets from the ratified register).
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class SourceFacets:
    """The ratified readings of a Source (§3) — copied onto entities, not re-derived."""

    authority: Authority
    license: License
    stability: Stability
    genre: str
    grc_domains: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ResolvedSource:
    """The Port's INPUT: a source resolved to `Ready` (§5.0) with its ratified
    identity and facets. `physical_path` is opaque here — only the realization
    opens it, and the Port never inspects the byte format."""

    source_id: str          # permanent anchor, e.g. "ISO-27001" (§2.1)
    version: str            # edition, e.g. "2022"
    language: Language
    variant: str            # e.g. "Official", "Annex", "Tool" (§2.1)
    physical_path: str      # a copy on disk — opaque to the boundary
    sha256: str
    facets: SourceFacets
    state: str = "Ready"    # resolved Source Status (§5.0); precondition = Ready


# ---------------------------------------------------------------------------
# OUTPUT — knowledge entities (the 14 ratified fields + retained native node type).
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class Provenance:
    """Contract-minimum provenance (§10.7). Richer lineage = BL-1 (deferred)."""

    source_id: str
    version: str
    location: str           # e.g. "Annex A / 5.7", "Article 5", "GV.OC-01"


@dataclass(frozen=True, slots=True)
class KnowledgeEntity:
    """One knowledge unit (§1). The 14 ratified fields plus `native_node_type` —
    the source's own name for this node (ADR 0056 guarantee 7): part of the source's
    semantic identity, not a mere label. Immutable — append-only (§10.11)."""

    source_id: str
    version: str
    entity_id: str          # version-pinned (§2.2): "ISO-27001@2022::A.5.7"
    parent: str | None
    type: EntityType        # canonical §3.5
    name: str
    number: str | None      # native numbering: "5.7" / "GV.OC-01" / "5"
    description: str
    language: Language
    authority: Authority
    license: License
    stability: Stability
    confidence: Confidence
    provenance: Provenance
    native_node_type: str   # source's own node name (guarantee 7): canonical
    #                         `Requirement` ↔ native `Clause`; `Control` ↔ `Enhancement`

    @property
    def egress_restricted(self) -> bool:
        """A MARKER, not a redaction (Storage ≠ Egress): the `description` is always
        stored in full — even for Licensed sources — and a downstream Egress Policy
        decides what a user is shown. §10.6: only Public-Domain content may leave the
        system unrestricted."""
        return self.license != "Public-Domain"


# ---------------------------------------------------------------------------
# OUTPUT — the artifact's OWN identity (ADR 0057), distinct from provenance.
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class ArtifactIdentity:
    """Identity of the ARTIFACT itself. Lets a future diff be attributed: did the
    SOURCE change or did the EXTRACTOR evolve? `generated_at` is metadata only —
    excluded from `content_hash` and `artifact_id`, so a reproducible re-run stays
    byte-identical (ADR 0056 guarantee 1; ADR 0057)."""

    artifact_id: str
    source_id: str
    source_version: str
    extractor_version: str
    protocol_version: str
    contract_version: str
    content_hash: str
    generated_at: str


@dataclass(frozen=True, slots=True)
class StructuralRelationship:
    """A relationship the EXTRACTOR emits because the SOURCE's own structure states
    it — e.g. NIST's identifier scheme makes GV *contain* GV.OC. This is STRUCTURE and
    lives in the Artifact; it is NOT a Tier-2 *semantic* relationship (those are the
    Graph Builder's later output — canonical model §4). Separating the two keeps
    'structure' with the source and 'semantics' with the graph. `type` is `contains`
    for a parent→child edge; both ends are version-pinned entity ids."""

    type: str
    source: str   # parent entity_id
    target: str   # child entity_id


@dataclass(frozen=True, slots=True)
class ExtractionNote:
    """A FORMAL note the extractor records to *describe* a limitation of reality — it
    never fails, invents, or waits; it states what it could and could not recover, and
    why. Example: a physical rendition that is not deterministically recoverable
    without heuristic layout guessing (a Rendition-quality matter — `Source ≠
    Rendition` — not a Missing/Rejected Source)."""

    subject: str             # what the note is about, e.g. "Management Clauses"
    status: str              # e.g. "Partial", "Skipped"
    reason: str              # why
    recommended_action: str  # what would resolve it, e.g. "Acquire higher-quality rendition"


@dataclass(frozen=True, slots=True)
class ArtifactSummary:
    """A compact, self-describing header (owner ask): a consumer or agent learns what
    the artifact holds without reading every entity. Derived data only — no new facts."""

    entities: int
    structural_relationships: int
    warnings: int
    unknown: int
    counts_by_type: Mapping[str, int]
    state: str
    language: Language
    normalization: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CanonicalExtractionArtifact:
    """The Port's OUTPUT (ADR 0057). Canonical, not temporary: retained and reused for
    rebuild, regression, cross-version diff, debugging, and embedding re-generation.
    Four self-sufficient parts — identity, summary, entities, structural_relationships
    — so no later stage must infer structure from code names."""

    identity: ArtifactIdentity
    summary: ArtifactSummary
    entities: tuple[KnowledgeEntity, ...]
    structural_relationships: tuple[StructuralRelationship, ...]
    warnings: tuple[ExtractionNote, ...]


# ---------------------------------------------------------------------------
# Reproducibility — deterministic content hash + attributable artifact id.
# ---------------------------------------------------------------------------
def _entity_payload(e: KnowledgeEntity) -> dict[str, object]:
    """Canonical, hashable view of an entity. `egress_restricted` is derived, so
    it is omitted; every persisted field participates in the hash."""
    return {
        "source_id": e.source_id, "version": e.version, "entity_id": e.entity_id,
        "parent": e.parent, "type": e.type, "name": e.name, "number": e.number,
        "description": e.description, "language": e.language,
        "authority": e.authority, "license": e.license, "stability": e.stability,
        "confidence": e.confidence, "native_node_type": e.native_node_type,
        "provenance": {
            "source_id": e.provenance.source_id, "version": e.provenance.version,
            "location": e.provenance.location,
        },
    }


def _rel_payload(r: StructuralRelationship) -> dict[str, object]:
    return {"type": r.type, "source": r.source, "target": r.target}


def compute_content_hash(
    entities: tuple[KnowledgeEntity, ...],
    structural_relationships: tuple[StructuralRelationship, ...] = (),
) -> str:
    """Order-sensitive SHA-256 over the artifact's knowledge content — entities AND
    structural relationships. Two runs with the same content produce the same hash;
    `generated_at` is not content, so it never affects it (guarantee 1)."""
    blob = json.dumps(
        {
            "entities": [_entity_payload(e) for e in entities],
            "structural_relationships": [_rel_payload(r) for r in structural_relationships],
        },
        sort_keys=True, ensure_ascii=False, separators=(",", ":"),
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _artifact_id(
    source_id: str, source_version: str, extractor_version: str,
    protocol_version: str, contract_version: str, content_hash: str,
) -> str:
    """Deterministic composite so a diff is attributable to source vs extractor vs
    protocol vs contract. Excludes `generated_at` by construction."""
    return (
        f"{source_id}@{source_version}"
        f"~x{extractor_version}~p{protocol_version}~c{contract_version}"
        f"~{content_hash[:12]}"
    )


def _validate(source: ResolvedSource, entities: tuple[KnowledgeEntity, ...]) -> None:
    """Enforce the Port guarantees centrally so no realization can diverge."""
    prefix = f"{source.source_id}@{source.version}::"
    facets = (source.facets.authority, source.facets.license, source.facets.stability)
    for e in entities:
        if e.type not in ENTITY_TYPES:
            raise ExtractionError(f"{e.entity_id}: {e.type!r} is not a canonical §3.5 type")
        if e.confidence not in CONFIDENCES:
            raise ExtractionError(f"{e.entity_id}: confidence {e.confidence!r} invalid")
        if e.language not in LANGUAGES:
            raise ExtractionError(f"{e.entity_id}: language {e.language!r} invalid")
        # Identity spine (§2.2): entity ids are version-pinned under their source.
        if e.source_id != source.source_id or e.version != source.version:
            raise ExtractionError(
                f"{e.entity_id}: does not belong to {source.source_id}@{source.version}"
            )
        if not e.entity_id.startswith(prefix):
            raise ExtractionError(f"{e.entity_id!r}: must be version-pinned as {prefix}…")
        # Guarantee 5: facets are inherited from the register, never re-derived.
        if (e.authority, e.license, e.stability) != facets:
            raise ExtractionError(f"{e.entity_id}: facets must be inherited from the source")
        # Guarantee 7: the source's own node name is retained.
        if not e.native_node_type:
            raise ExtractionError(f"{e.entity_id}: native_node_type must be retained")
    # Structural integrity: every parent must be an emitted entity, so the derived
    # `contains` edges never dangle.
    ids = {e.entity_id for e in entities}
    for e in entities:
        if e.parent is not None and e.parent not in ids:
            raise ExtractionError(f"{e.entity_id}: parent {e.parent!r} is not an emitted entity")


def _derive_structural_relationships(
    entities: tuple[KnowledgeEntity, ...],
    extra: tuple[StructuralRelationship, ...],
) -> tuple[StructuralRelationship, ...]:
    """Materialize the parent hierarchy the extractor *read* as explicit `contains`
    edges (parent → child), then append any extra structural edges the extractor
    supplies. Derived from `entity.parent` (already read from the source) — this
    invents nothing; it makes structure explicit in the Artifact instead of leaving
    the Graph Builder to infer it."""
    contains = tuple(
        StructuralRelationship("contains", e.parent, e.entity_id)
        for e in entities
        if e.parent is not None
    )
    return contains + extra


def _require_verified(source: ResolvedSource) -> None:
    """Precondition — terminal verification (PROTO-EXT-3). Extraction receives a
    source already resolved to `Ready` by Stage-2 verification. An extractor's ONLY
    responsibility is `Verified Source in → Artifact out`; it never re-detects OCR,
    encryption, missing, or rejected — that responsibility ended upstream. This guard
    only catches a caller that violates the contract by passing an unverified source."""
    if source.state != "Ready":
        raise ExtractionError(
            f"{source.source_id}@{source.version}: extraction requires a Verified "
            f"(Ready) source; got state {source.state!r} — verification is terminal"
        )


def assemble_artifact(
    *,
    source: ResolvedSource,
    entities: tuple[KnowledgeEntity, ...],
    extractor_version: str,
    protocol_version: str,
    contract_version: str,
    extra_structural_relationships: tuple[StructuralRelationship, ...] = (),
    normalization: tuple[str, ...] = (),
    warnings: tuple[ExtractionNote, ...] = (),
    generated_at: str | None = None,
) -> CanonicalExtractionArtifact:
    """Build a well-formed, guarantee-enforcing artifact from a realization's
    entities. Every `*KnowledgeExtractor` returns through this factory, so all
    artifacts are identically shaped and hashed — the guarantees live here, not
    scattered across realizations. Structural relationships (`contains` edges) are
    materialized from the entities' parent links. Fails LOUD on any violation (§16)."""
    _require_verified(source)
    _validate(source, entities)
    structural_relationships = _derive_structural_relationships(
        entities, extra_structural_relationships
    )
    content_hash = compute_content_hash(entities, structural_relationships)
    identity = ArtifactIdentity(
        artifact_id=_artifact_id(
            source.source_id, source.version, extractor_version,
            protocol_version, contract_version, content_hash,
        ),
        source_id=source.source_id,
        source_version=source.version,
        extractor_version=extractor_version,
        protocol_version=protocol_version,
        contract_version=contract_version,
        content_hash=content_hash,
        generated_at=generated_at or datetime.now(timezone.utc).isoformat(),
    )
    counts: dict[str, int] = {}
    unknown = 0
    for e in entities:
        counts[e.type] = counts.get(e.type, 0) + 1
        if e.confidence == "Unknown":
            unknown += 1
    summary = ArtifactSummary(
        entities=len(entities),
        structural_relationships=len(structural_relationships),
        warnings=len(warnings),
        unknown=unknown,
        counts_by_type=counts,
        state=source.state,
        language=source.language,
        normalization=normalization,
    )
    return CanonicalExtractionArtifact(
        identity=identity,
        summary=summary,
        entities=entities,
        structural_relationships=structural_relationships,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# The boundary + its collaborators.
# ---------------------------------------------------------------------------
class KnowledgeExtractionPort(ABC):
    """THE boundary. A `*KnowledgeExtractor` has ONE responsibility: turn a
    **Verified** source into a Canonical Extraction Artifact — `Verified Source in →
    Artifact out`. It reads its family's format privately; the Port itself knows no
    format, and it NEVER re-validates the source — OCR / encryption / missing /
    rejected all ended in Stage-2 verification (PROTO-EXT-3). Set `extractor_version`
    so the artifact identity can attribute future diffs to extractor evolution."""

    extractor_version: str

    @abstractmethod
    def accepts(self, source: ResolvedSource) -> bool:
        """Does this extractor handle this source's family? A capability guard —
        dispatch is still DATA via `ExtractorRegistry`; this cross-checks it so a
        mis-registration fails loud rather than mis-extracting."""
        ...

    @abstractmethod
    def extract(self, source: ResolvedSource) -> CanonicalExtractionArtifact:
        """Precondition: `source` is Verified (`state == "Ready"`). Realizations
        build their result through `assemble_artifact`, which enforces that
        precondition and every Port guarantee."""
        ...


class ArtifactWriter(ABC):
    """ADR 0057: the artifact's FORMAT is a replaceable realization. JSON is the
    first writer; it may be swapped for Postgres/Parquet/SQLite without touching
    the Port or any extractor. Writers are append-only (§10.11)."""

    @abstractmethod
    def write(self, artifact: CanonicalExtractionArtifact) -> None:
        ...


class ExtractorRegistry:
    """Selection is DATA, not code (§10 / §17): each `source_id` maps to exactly
    one `*KnowledgeExtractor`. Adding a source family = registering a realization,
    never editing control flow."""

    def __init__(self) -> None:
        self._by_source: dict[str, KnowledgeExtractionPort] = {}

    def register(self, source_ids: Iterable[str], extractor: KnowledgeExtractionPort) -> None:
        for sid in source_ids:
            if sid in self._by_source:
                raise ExtractionError(f"source {sid!r} already has an extractor")
            self._by_source[sid] = extractor

    def resolve(self, source_id: str) -> KnowledgeExtractionPort:
        try:
            return self._by_source[source_id]
        except KeyError:
            raise ExtractionError(f"no extractor registered for source {source_id!r}") from None

    def extract(self, source: ResolvedSource) -> CanonicalExtractionArtifact:
        extractor = self.resolve(source.source_id)
        if not extractor.accepts(source):
            raise ExtractionError(
                f"registered extractor does not accept {source.source_id!r} — "
                f"mis-registration"
            )
        return extractor.extract(source)
