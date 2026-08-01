/**
 * View models — the UI-shaped types the services layer produces from the raw artifacts
 * (`artifacts.ts`). Components receive only these; they never see a raw manifest, and
 * they never compute anything. All aggregation lives in the services.
 */

export interface LibraryOverview {
  totalDocuments: number;
  totalPages: number;
  totalChunks: number;
  totalEmbeddings: number;
  totalDocumentProfiles: number;
  lastPipelineRun: string | null;
  parsingSuccessRate: number; // 0..1
  chunkingSuccessRate: number; // 0..1
  embeddingSuccessRate: number; // 0..1
  parsedCount: number;
  chunkedCount: number;
  embeddedCount: number;
}

export type PipelineFlag = boolean;

export interface DocumentRow {
  documentId: string;
  name: string;
  category: string;
  documentProfile: string | null;
  parserUsed: string | null;
  parsed: PipelineFlag;
  chunked: PipelineFlag;
  embedded: PipelineFlag;
  pages: number | null;
  chunks: number | null;
  embeddings: number;
  language: string;
  lastUpdated: string | null;
  hasWarnings: boolean;
}

export interface DocumentFilters {
  category: string | null;
  documentProfile: string | null;
  status: string | null; // "parsed" | "parse_failed" | "chunked" | "embedded" | "warnings"
  parser: string | null;
  language: string | null;
  search: string | null;
}

export interface FilterOptions {
  categories: string[];
  documentProfiles: string[];
  parsers: string[];
  languages: string[];
  statuses: string[];
}

export interface ChunkStatistics {
  total: number;
  byContentType: Record<string, number>;
  byStructureProfile: Record<string, number>;
  withPageNumbers: number;
  fallbackWindows: number;
  averageCharacters: number;
  largestChunkChars: number;
  smallestChunkChars: number;
}

export interface EmbeddingStatistics {
  embedded: boolean;
  count: number;
  provider: string | null;
  model: string | null;
  dimensions: number | null;
  version: string | null;
}

export interface CitationSample {
  code: string | null;
  title: string | null;
  headingPath: string[];
  pageStart: number | null;
  pageEnd: number | null;
}

export interface DocumentDetail {
  documentId: string;
  general: {
    name: string;
    category: string;
    documentProfile: string | null;
    profileAssignmentSource: string | null;
    extension: string;
    sizeBytes: number;
    relativePath: string;
    language: string;
    checksum: string;
  };
  pipelineStatus: {
    stagesCompleted: string[];
    status: string;
    parsed: boolean;
    chunked: boolean;
    embedded: boolean;
  };
  parsing: {
    parser: string | null;
    parserUsed: string | null;
    parserFallback: boolean;
    pageCount: number | null;
    characterCount: number | null;
    extractionDuration: number | null;
    parsedAt: string | null;
  };
  parserAttempts: Array<{ backend: string; ok: boolean; error: string | null }>;
  chunkStats: ChunkStatistics | null;
  embeddingStats: EmbeddingStatistics;
  citations: CitationSample[];
  warnings: string[];
  manifest: Record<string, unknown>;
}

export interface PipelineRun {
  id: string;
  stage: string; // "Import (parse + chunk)" | "Embedding"
  startTime: string | null;
  durationSeconds: number | null;
  documentsProcessed: number;
  chunksGenerated: number | null;
  embeddingsGenerated: number | null;
  failures: number;
  provider: string | null;
  approximate: boolean;
}
