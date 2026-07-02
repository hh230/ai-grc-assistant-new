/**
 * Global Search domain types (V2-P3 Milestone 6). Search runs client-side today, over the
 * same real per-entity queries the rest of the workspace already uses (`useDocuments`,
 * `useAnalyses`, `usePolicies`, `useRisks`, `useEvidence`) plus the static report catalog —
 * there is no separate search index or backend endpoint yet. `SearchResultItem` is the
 * shape a future `search_workspace.v1` Tool (CLAUDE.md §9/§10 of the design proposal) would
 * return, so swapping the client-side filter for a real API call later is a drop-in change
 * behind `useGlobalSearch`, not a UI rewrite.
 */

export const SEARCH_ENTITY_TYPES = [
  "document",
  "analysis",
  "policy",
  "risk",
  "evidence",
  "report",
] as const;
export type SearchEntityType = (typeof SEARCH_ENTITY_TYPES)[number];

export interface SearchResultItem {
  id: string;
  type: SearchEntityType;
  title: string;
  subtitle?: string;
  href: string;
}
