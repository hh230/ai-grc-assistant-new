/**
 * Types mirroring the JSON artifacts the Knowledge Pipeline generates. These are the
 * exact shapes written by the Python `knowledge-importer` package — the Knowledge Center
 * only ever reads these, never PDFs or any live source.
 *
 * Kept deliberately close to the on-disk schema (snake_case field names) so the mapping
 * from artifact to type is one-to-one and obvious. View models (camelCase, UI-shaped)
 * live in `view.ts` and are produced by the services layer.
 */

/** One document's manifest — `v2/knowledge/manifests/{document_id}.json`. */
export interface DocumentManifest {
  manifest_version: string;
  document_id: string;
  filename: string;
  extension: string;
  category: string;
  relative_path: string;
  size_bytes: number;
  last_modified: string;
  checksum_sha256: string;
  discovered_at: string;
  stages_completed: string[];
  status: string;

  // parsing
  parsed: boolean;
  parser: string | null;
  parser_used: string | null;
  parser_fallback: boolean;
  parser_attempts: ParserAttempt[];
  failure_reason: string | null;
  page_count: number | null;
  character_count: number | null;
  extraction_duration: number | null;
  parsed_at: string | null;
  error: string | null;

  // profile assignment
  document_profile: string | null;
  profile_assignment_source: string | null;

  // chunking
  chunked: boolean;
  chunk_count: number | null;
  structure_profile_used: string | null;
  recognizer_confidence: number | null;
  chunking_duration: number | null;
  chunked_at: string | null;
  chunking_error: string | null;
}

export interface ParserAttempt {
  backend: string;
  ok: boolean;
  error: string | null;
}

/** The combined index — `v2/knowledge/manifests/index.json`. */
export interface ManifestIndex {
  manifest_version: string;
  generated_at: string;
  document_count: number;
  documents: Array<{
    document_id: string;
    filename: string;
    category: string;
    extension: string;
    status: string;
    checksum_sha256: string;
    manifest_path: string;
  }>;
}

/** One chunk — an element of `v2/knowledge/chunks/{document_id}.json`. */
export interface ChunkRecord {
  chunk_id: string;
  document_id: string;
  source_filename: string;
  category: string;
  document_profile: string | null;
  structure_profile: string;
  content_type: string;
  code: string | null;
  title: string | null;
  path: string[];
  level: number;
  parent_chunk_id: string | null;
  position: number;
  text: string;
  character_count: number;
  page_start: number | null;
  page_end: number | null;
  window_index: number | null;
  window_of_total: number | null;
  references: unknown[];
  language: string;
  recognizer_confidence: number;
  chunker_version: string;
  chunked_at: string;
  checksum_sha256: string;
}

/** The embedding run summary — `v2/knowledge/embeddings/embedding_manifest.json`. */
export interface EmbeddingManifest {
  provider: string;
  model: string;
  dimensions: number;
  embedding_version: string;
  documents_total: number;
  documents_processed: number;
  documents_failed: number;
  total_chunks: number;
  total_embeddings: number;
  created: number;
  regenerated: number;
  skipped: number;
  failed: number;
  duration_seconds: number;
  generated_at: string;
  failures: Array<{ chunk_id: string; reason: string }>;
}

/** The per-document embedding count index — `embeddings/embedding_index.json`. */
export interface EmbeddingIndex {
  document_count: number;
  total_embeddings: number;
  counts: Record<string, number>;
}
