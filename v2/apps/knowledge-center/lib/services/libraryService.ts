/**
 * Pure aggregation over document manifests + embedding artifacts. Every function here is
 * a pure transformation of already-loaded data — no filesystem, no I/O — so the UI's
 * business logic is fully unit-testable without a running app. Components import these;
 * they never aggregate anything themselves.
 */

import type { DocumentManifest, EmbeddingIndex, EmbeddingManifest } from "@/lib/types/artifacts";
import type {
  DocumentFilters,
  DocumentRow,
  FilterOptions,
  LibraryOverview,
} from "@/lib/types/view";

function rate(numerator: number, denominator: number): number {
  return denominator === 0 ? 0 : numerator / denominator;
}

function manifestLastUpdated(m: DocumentManifest): string | null {
  return m.chunked_at ?? m.parsed_at ?? m.discovered_at ?? null;
}

export function documentHasWarnings(m: DocumentManifest): boolean {
  return (
    !m.parsed ||
    (m.parsed && !m.chunked) ||
    m.failure_reason !== null ||
    m.chunking_error !== null ||
    m.parser_fallback === true
  );
}

export function buildOverview(
  manifests: DocumentManifest[],
  embeddingIndex: EmbeddingIndex | null,
  embeddingManifest: EmbeddingManifest | null,
): LibraryOverview {
  const totalDocuments = manifests.length;
  const parsedCount = manifests.filter((m) => m.parsed).length;
  const chunkedCount = manifests.filter((m) => m.chunked).length;

  const totalPages = manifests.reduce((sum, m) => sum + (m.page_count ?? 0), 0);
  const totalChunks = manifests.reduce((sum, m) => sum + (m.chunk_count ?? 0), 0);

  const counts = embeddingIndex?.counts ?? {};
  const embeddedCount = manifests.filter((m) => (counts[m.document_id] ?? 0) > 0).length;
  const totalEmbeddings = embeddingIndex?.total_embeddings ?? 0;

  const profiles = new Set(
    manifests.map((m) => m.document_profile).filter((p): p is string => p !== null),
  );

  const lastPipelineRun = manifests
    .map(manifestLastUpdated)
    .filter((t): t is string => t !== null)
    .sort()
    .at(-1) ?? null;

  return {
    totalDocuments,
    totalPages,
    totalChunks,
    totalEmbeddings,
    totalDocumentProfiles: profiles.size,
    lastPipelineRun,
    parsingSuccessRate: rate(parsedCount, totalDocuments),
    // chunking is measured against documents that parsed (only they can be chunked)
    chunkingSuccessRate: rate(chunkedCount, parsedCount),
    // embedding is measured against documents that chunked
    embeddingSuccessRate: rate(embeddedCount, chunkedCount),
    parsedCount,
    chunkedCount,
    embeddedCount,
  };
}

export function buildDocumentRows(
  manifests: DocumentManifest[],
  embeddingIndex: EmbeddingIndex | null,
): DocumentRow[] {
  const counts = embeddingIndex?.counts ?? {};
  return manifests.map((m) => {
    const embeddings = counts[m.document_id] ?? 0;
    return {
      documentId: m.document_id,
      name: m.filename,
      category: m.category.trim(),
      documentProfile: m.document_profile,
      parserUsed: m.parser_used ?? m.parser,
      parsed: m.parsed,
      chunked: m.chunked,
      embedded: embeddings > 0,
      pages: m.page_count,
      chunks: m.chunk_count,
      embeddings,
      language: inferLanguage(m),
      lastUpdated: manifestLastUpdated(m),
      hasWarnings: documentHasWarnings(m),
    };
  });
}

/**
 * A document's language is not on the manifest (chunks carry per-chunk language). For the
 * table we infer a coarse document language from the category/filename script: Arabic
 * when the filename contains Arabic-block characters, else English. This is a display
 * hint only — per-chunk language remains authoritative in the chunk records.
 */
function inferLanguage(m: DocumentManifest): string {
  return /[؀-ۿ]/.test(m.filename) ? "ar" : "en";
}

export function buildFilterOptions(rows: DocumentRow[]): FilterOptions {
  const uniqueSorted = (values: (string | null)[]): string[] =>
    Array.from(new Set(values.filter((v): v is string => !!v))).sort();

  return {
    categories: uniqueSorted(rows.map((r) => r.category)),
    documentProfiles: uniqueSorted(rows.map((r) => r.documentProfile)),
    parsers: uniqueSorted(rows.map((r) => r.parserUsed)),
    languages: uniqueSorted(rows.map((r) => r.language)),
    statuses: ["parsed", "parse_failed", "chunked", "embedded", "warnings"],
  };
}

function matchesStatus(row: DocumentRow, status: string): boolean {
  switch (status) {
    case "parsed":
      return row.parsed;
    case "parse_failed":
      return !row.parsed;
    case "chunked":
      return row.chunked;
    case "embedded":
      return row.embedded;
    case "warnings":
      return row.hasWarnings;
    default:
      return true;
  }
}

/**
 * Applies filters + free-text search. Pure and total: an unset filter matches everything;
 * search is case-insensitive across document name, filename, and category. This is the
 * one function the interactive client component calls — it holds no logic of its own.
 */
export function filterDocuments(rows: DocumentRow[], filters: DocumentFilters): DocumentRow[] {
  const query = filters.search?.trim().toLowerCase() ?? "";
  return rows.filter((row) => {
    if (filters.category && row.category !== filters.category) return false;
    if (filters.documentProfile && row.documentProfile !== filters.documentProfile) return false;
    if (filters.parser && row.parserUsed !== filters.parser) return false;
    if (filters.language && row.language !== filters.language) return false;
    if (filters.status && !matchesStatus(row, filters.status)) return false;
    if (query) {
      const haystack = `${row.name} ${row.category} ${row.documentId}`.toLowerCase();
      if (!haystack.includes(query)) return false;
    }
    return true;
  });
}
