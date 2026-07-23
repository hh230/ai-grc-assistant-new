"""The read-side data the Knowledge view needs — nothing more (V1 Execution Slice S4).

These are **read models**, not a Core aggregate: the frozen Core stores no Document at all — a
Document record is a Domain-Model §3 gap this slice fills. The projection carries exactly what the
Knowledge view shows, in the product's language:

- **`DocumentItem`** — one document as the view lists it: its filename, the **`evidence_kind`** it
  was classified under at upload, its ingestion **`status`** snapshot, when it was uploaded, and its
  `size`. It exposes **no chunk ids, embeddings, or pgvector detail** — those stay
  `knowledge-runtime`'s concern (Design rule: *Knowledge = Evidence, not a File Manager*).
- **`EvidenceCollection`** — the **unit the user works with**: a named group of evidence (one
  `evidence_kind`) plus its `count`. The Knowledge view lists collections first (`Policies (12)`),
  and the user opens one to see the documents inside. Modelling the collection now — not the file —
  lets revisions / versions / many files per control grow *inside* a collection without a UI
  redesign (Design rule 1).

`status` is a snapshot of the Document's ingestion lifecycle at projection time. The read model is
where these product concepts become queryable; ingestion (the chunks) stays behind it in
`knowledge-runtime`.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DocumentItem:
    """One document in the Knowledge view — a tenant's piece of evidence as the view lists it.

    `evidence_kind` and `status` are stored as plain strings (a snapshot), so the read model is
    storage-agnostic and never rejects a value; the API boundary validates them against the product
    vocabulary (`EvidenceKind` / `DocumentStatus`). `size` is the file size in bytes."""

    document_id: str
    tenant_id: str
    filename: str
    evidence_kind: str
    status: str
    uploaded_at: float
    size: int


@dataclass(frozen=True)
class EvidenceCollection:
    """One Evidence Collection — the unit the Knowledge view is built around: a named group of
    evidence (`evidence_kind`) and how many documents it holds (`count`). This is the overview row;
    opening it lists the collection's `DocumentItem`s. It deliberately does not carry the documents:
    the overview needs the count; contents are fetched (filtered) when a collection is opened."""

    evidence_kind: str
    count: int
