/**
 * Pure assembly of a single document's detail view from its manifest, its chunks, and the
 * embedding artifacts. No I/O — the page loads the raw data via the repository and passes
 * it here.
 */

import type {
  ChunkRecord,
  DocumentManifest,
  EmbeddingManifest,
} from "@/lib/types/artifacts";
import type {
  ChunkStatistics,
  CitationSample,
  DocumentDetail,
  EmbeddingStatistics,
} from "@/lib/types/view";
import { documentHasWarnings } from "@/lib/services/libraryService";

const MAX_CITATION_SAMPLES = 12;

export function buildChunkStatistics(chunks: ChunkRecord[]): ChunkStatistics | null {
  if (chunks.length === 0) return null;

  const byContentType: Record<string, number> = {};
  const byStructureProfile: Record<string, number> = {};
  let withPageNumbers = 0;
  let fallbackWindows = 0;
  let totalChars = 0;
  let largest = Number.NEGATIVE_INFINITY;
  let smallest = Number.POSITIVE_INFINITY;

  for (const chunk of chunks) {
    byContentType[chunk.content_type] = (byContentType[chunk.content_type] ?? 0) + 1;
    byStructureProfile[chunk.structure_profile] =
      (byStructureProfile[chunk.structure_profile] ?? 0) + 1;
    if (chunk.page_start !== null) withPageNumbers += 1;
    if (chunk.structure_profile === "fallback_window") fallbackWindows += 1;
    totalChars += chunk.character_count;
    largest = Math.max(largest, chunk.character_count);
    smallest = Math.min(smallest, chunk.character_count);
  }

  return {
    total: chunks.length,
    byContentType,
    byStructureProfile,
    withPageNumbers,
    fallbackWindows,
    averageCharacters: Math.round(totalChars / chunks.length),
    largestChunkChars: largest,
    smallestChunkChars: smallest,
  };
}

export function buildCitationSamples(chunks: ChunkRecord[]): CitationSample[] {
  return chunks
    .filter((c) => c.code !== null || c.title !== null)
    .slice(0, MAX_CITATION_SAMPLES)
    .map((c) => ({
      code: c.code,
      title: c.title,
      headingPath: c.path,
      pageStart: c.page_start,
      pageEnd: c.page_end,
    }));
}

function buildEmbeddingStats(
  embeddingCount: number,
  embeddingManifest: EmbeddingManifest | null,
): EmbeddingStatistics {
  return {
    embedded: embeddingCount > 0,
    count: embeddingCount,
    provider: embeddingManifest?.provider ?? null,
    model: embeddingManifest?.model ?? null,
    dimensions: embeddingManifest?.dimensions ?? null,
    version: embeddingManifest?.embedding_version ?? null,
  };
}

function collectWarnings(m: DocumentManifest): string[] {
  const warnings: string[] = [];
  if (!m.parsed) warnings.push(`Parsing failed: ${m.failure_reason ?? m.error ?? "unknown error"}`);
  if (m.parsed && !m.chunked) {
    warnings.push(`Chunking did not complete: ${m.chunking_error ?? "unknown error"}`);
  }
  if (m.parser_fallback) {
    const failedBackends = m.parser_attempts.filter((a) => !a.ok).map((a) => a.backend);
    warnings.push(
      `Parser fallback used — primary backend(s) failed: ${failedBackends.join(", ") || "unknown"}`,
    );
  }
  if (m.document_profile === null) {
    warnings.push("No Document Profile assigned (category has no profile mapping).");
  }
  return warnings;
}

export function buildDocumentDetail(
  manifest: DocumentManifest,
  chunks: ChunkRecord[],
  embeddingCount: number,
  embeddingManifest: EmbeddingManifest | null,
): DocumentDetail {
  return {
    documentId: manifest.document_id,
    general: {
      name: manifest.filename,
      category: manifest.category.trim(),
      documentProfile: manifest.document_profile,
      profileAssignmentSource: manifest.profile_assignment_source,
      extension: manifest.extension,
      sizeBytes: manifest.size_bytes,
      relativePath: manifest.relative_path,
      language: /[؀-ۿ]/.test(manifest.filename) ? "ar" : "en",
      checksum: manifest.checksum_sha256,
    },
    pipelineStatus: {
      stagesCompleted: manifest.stages_completed,
      status: manifest.status,
      parsed: manifest.parsed,
      chunked: manifest.chunked,
      embedded: embeddingCount > 0,
    },
    parsing: {
      parser: manifest.parser,
      parserUsed: manifest.parser_used,
      parserFallback: manifest.parser_fallback,
      pageCount: manifest.page_count,
      characterCount: manifest.character_count,
      extractionDuration: manifest.extraction_duration,
      parsedAt: manifest.parsed_at,
    },
    parserAttempts: manifest.parser_attempts,
    chunkStats: buildChunkStatistics(chunks),
    embeddingStats: buildEmbeddingStats(embeddingCount, embeddingManifest),
    citations: buildCitationSamples(chunks),
    warnings: collectWarnings(manifest),
    manifest: manifest as unknown as Record<string, unknown>,
  };
}

export { documentHasWarnings };
