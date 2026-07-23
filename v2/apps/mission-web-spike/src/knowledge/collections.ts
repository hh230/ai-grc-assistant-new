// The Evidence Collection vocabulary + grouping — the heart of "Knowledge = Evidence Collections".
// Grouping a flat document list into collections is PRESENTATION (owner's rule): the API returns
// documents; the UI turns them into named collections (`Policies (12)`). Mirrors the backend
// EvidenceKind, in the same display order — the collection, not the file, is the unit the user sees.

import type { DocumentItem } from "../api/client";

export interface EvidenceKindDef {
  kind: string;
  label: string;
}

// The six product evidence kinds, in display order (matches document_read_model.KIND_ORDER). The
// `other` kind DISPLAYS as "Unclassified" — a basket for evidence not yet classified, never a
// first-class Evidence Collection (owner, S4 review). The wire value stays "other" (product language
// ≠ implementation language): only the label changes, so the REST contract is untouched. Empty
// collections are never shown, so "Unclassified" appears (last) only when something is unclassified.
export const EVIDENCE_KINDS: EvidenceKindDef[] = [
  { kind: "policy", label: "Policies" },
  { kind: "procedure", label: "Procedures" },
  { kind: "standard", label: "Standards" },
  { kind: "soc_report", label: "SOC Reports" },
  { kind: "risk_register", label: "Risk Registers" },
  { kind: "other", label: "Unclassified" },
];

// The kinds a user may CHOOSE when uploading. "Unclassified" is deliberately excluded (#3): it is the
// system's bin for what it couldn't classify — a display bucket, never an author's choice. It stays in
// EVIDENCE_KINDS (so documents the backend marks "other" still group and display as "Unclassified"),
// just not as something you pick.
export const UPLOAD_KINDS: EvidenceKindDef[] = EVIDENCE_KINDS.filter((def) => def.kind !== "other");

const ORDER = new Map(EVIDENCE_KINDS.map((def, index) => [def.kind, index]));
const LABELS = new Map(EVIDENCE_KINDS.map((def) => [def.kind, def.label]));

export function kindLabel(kind: string): string {
  return LABELS.get(kind) ?? titleCase(kind);
}

export interface EvidenceCollectionVM {
  kind: string;
  label: string;
  count: number;
  documents: DocumentItem[];
}

// Group documents into Evidence Collections, in the product's display order (unknown kinds last).
// Documents keep the API's order (newest-first) within a collection.
export function toCollections(documents: DocumentItem[]): EvidenceCollectionVM[] {
  const byKind = new Map<string, DocumentItem[]>();
  for (const doc of documents) {
    const list = byKind.get(doc.evidence_kind) ?? [];
    list.push(doc);
    byKind.set(doc.evidence_kind, list);
  }
  return [...byKind.entries()]
    .map(([kind, docs]) => ({ kind, label: kindLabel(kind), count: docs.length, documents: docs }))
    .sort((a, b) => sortKey(a.kind) - sortKey(b.kind));
}

function sortKey(kind: string): number {
  return ORDER.get(kind) ?? EVIDENCE_KINDS.length; // unknown kinds after the known ones
}

function titleCase(value: string): string {
  return value.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
