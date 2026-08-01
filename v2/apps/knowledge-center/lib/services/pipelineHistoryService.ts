/**
 * Reconstructs pipeline run history from the generated artifacts. The pipeline does not
 * (yet) persist an append-only run log, so history is derived from what the artifacts
 * record: the import (parse + chunk) run is reconstructed from the document manifests'
 * timestamps and counts, and the embedding run comes straight from the embedding
 * manifest. Reconstructed runs are flagged `approximate` where a field (e.g. the import
 * run's wall-clock duration) isn't persisted and can only be estimated from timestamps.
 *
 * A persistent multi-run history log is a natural future addition; until then this shows
 * the real, current state honestly rather than inventing history.
 */

import type { DocumentManifest, EmbeddingManifest } from "@/lib/types/artifacts";
import type { PipelineRun } from "@/lib/types/view";

function estimateImportDuration(manifests: DocumentManifest[]): number | null {
  const starts = manifests.map((m) => m.discovered_at).filter(Boolean);
  const ends = manifests
    .map((m) => m.chunked_at ?? m.parsed_at)
    .filter((t): t is string => !!t);
  if (starts.length === 0 || ends.length === 0) return null;
  const start = Math.min(...starts.map((t) => Date.parse(t)));
  const end = Math.max(...ends.map((t) => Date.parse(t)));
  const seconds = (end - start) / 1000;
  return Number.isFinite(seconds) && seconds >= 0 ? seconds : null;
}

export function buildPipelineHistory(
  manifests: DocumentManifest[],
  embeddingManifest: EmbeddingManifest | null,
): PipelineRun[] {
  const runs: PipelineRun[] = [];

  if (manifests.length > 0) {
    const parseFailures = manifests.filter((m) => !m.parsed).length;
    const chunkFailures = manifests.filter((m) => m.parsed && !m.chunked).length;
    const totalChunks = manifests.reduce((sum, m) => sum + (m.chunk_count ?? 0), 0);
    const startTime = manifests
      .map((m) => m.discovered_at)
      .filter(Boolean)
      .sort()
      .at(0) ?? null;

    runs.push({
      id: "import-latest",
      stage: "Import — parse + chunk",
      startTime,
      durationSeconds: estimateImportDuration(manifests),
      documentsProcessed: manifests.length,
      chunksGenerated: totalChunks,
      embeddingsGenerated: null,
      failures: parseFailures + chunkFailures,
      provider: null,
      approximate: true,
    });
  }

  if (embeddingManifest) {
    runs.push({
      id: "embedding-latest",
      stage: "Embedding",
      startTime: embeddingManifest.generated_at || null,
      durationSeconds: embeddingManifest.duration_seconds,
      documentsProcessed: embeddingManifest.documents_processed,
      chunksGenerated: null,
      embeddingsGenerated: embeddingManifest.total_embeddings,
      failures: embeddingManifest.failed,
      provider: embeddingManifest.provider,
      approximate: false,
    });
  }

  // newest first by start time
  return runs.sort((a, b) => (b.startTime ?? "").localeCompare(a.startTime ?? ""));
}
