import { describe, expect, it } from "vitest";

import type {
  ChunkRecord,
  DocumentManifest,
  EmbeddingIndex,
  EmbeddingManifest,
} from "@/lib/types/artifacts";
import {
  buildDocumentRows,
  buildFilterOptions,
  buildOverview,
  documentHasWarnings,
  filterDocuments,
} from "@/lib/services/libraryService";
import { buildChunkStatistics, buildDocumentDetail } from "@/lib/services/documentService";
import { buildPipelineHistory } from "@/lib/services/pipelineHistoryService";

function manifest(overrides: Partial<DocumentManifest> = {}): DocumentManifest {
  return {
    manifest_version: "1.3",
    document_id: "iso--iso-27001.pdf",
    filename: "ISO 27001.pdf",
    extension: ".pdf",
    category: "ISO",
    relative_path: "ISO/ISO 27001.pdf",
    size_bytes: 1000,
    last_modified: "2026-07-12T00:00:00+00:00",
    checksum_sha256: "abc",
    discovered_at: "2026-07-12T10:00:00+00:00",
    stages_completed: ["intake", "parsing", "profile_assignment", "chunking"],
    status: "parsed",
    parsed: true,
    parser: "pdf",
    parser_used: "pypdf",
    parser_fallback: false,
    parser_attempts: [{ backend: "pypdf", ok: true, error: null }],
    failure_reason: null,
    page_count: 26,
    character_count: 5000,
    extraction_duration: 0.5,
    parsed_at: "2026-07-12T10:01:00+00:00",
    error: null,
    document_profile: "iso_standard",
    profile_assignment_source: "category_default",
    chunked: true,
    chunk_count: 167,
    structure_profile_used: "standard_clause",
    recognizer_confidence: 1.0,
    chunking_duration: 0.2,
    chunked_at: "2026-07-12T10:02:00+00:00",
    chunking_error: null,
    ...overrides,
  };
}

const embeddingIndex: EmbeddingIndex = {
  document_count: 2,
  total_embeddings: 200,
  counts: { "iso--iso-27001.pdf": 167, "laws--x.pdf": 33 },
};

const embeddingManifest: EmbeddingManifest = {
  provider: "local",
  model: "local-deterministic-hash-v1",
  dimensions: 1536,
  embedding_version: "v1",
  documents_total: 2,
  documents_processed: 2,
  documents_failed: 0,
  total_chunks: 200,
  total_embeddings: 200,
  created: 200,
  regenerated: 0,
  skipped: 0,
  failed: 0,
  duration_seconds: 12.3,
  generated_at: "2026-07-12T11:00:00+00:00",
  failures: [],
};

describe("buildOverview", () => {
  it("aggregates totals and computes staged success rates", () => {
    const manifests = [
      manifest(),
      manifest({ document_id: "laws--x.pdf", filename: "law.pdf", category: "Laws", page_count: 10, chunk_count: 33, document_profile: "law" }),
      manifest({ document_id: "iso--broken.pdf", filename: "broken.pdf", parsed: false, chunked: false, page_count: null, chunk_count: null, document_profile: "iso_standard", status: "parse_failed", failure_reason: "boom" }),
    ];
    const overview = buildOverview(manifests, embeddingIndex, embeddingManifest);

    expect(overview.totalDocuments).toBe(3);
    expect(overview.totalPages).toBe(36); // 26 + 10 + 0
    expect(overview.totalChunks).toBe(200); // 167 + 33
    expect(overview.totalEmbeddings).toBe(200);
    expect(overview.totalDocumentProfiles).toBe(2); // iso_standard, law
    expect(overview.parsedCount).toBe(2);
    expect(overview.chunkedCount).toBe(2);
    expect(overview.embeddedCount).toBe(2);
    expect(overview.parsingSuccessRate).toBeCloseTo(2 / 3);
    expect(overview.chunkingSuccessRate).toBeCloseTo(2 / 2); // of parsed
    expect(overview.embeddingSuccessRate).toBeCloseTo(2 / 2); // of chunked
    expect(overview.lastPipelineRun).toBe("2026-07-12T10:02:00+00:00");
  });

  it("never divides by zero on an empty library", () => {
    const overview = buildOverview([], null, null);
    expect(overview.parsingSuccessRate).toBe(0);
    expect(overview.chunkingSuccessRate).toBe(0);
    expect(overview.embeddingSuccessRate).toBe(0);
    expect(overview.totalEmbeddings).toBe(0);
  });
});

describe("buildDocumentRows", () => {
  it("maps manifests to rows and joins embedding counts", () => {
    const rows = buildDocumentRows([manifest()], embeddingIndex);
    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({
      name: "ISO 27001.pdf",
      category: "ISO",
      documentProfile: "iso_standard",
      parserUsed: "pypdf",
      parsed: true,
      chunked: true,
      embedded: true,
      pages: 26,
      chunks: 167,
      embeddings: 167,
      hasWarnings: false,
    });
  });

  it("marks embedded=false when the index has no count", () => {
    const rows = buildDocumentRows([manifest({ document_id: "unindexed.pdf" })], embeddingIndex);
    expect(rows[0].embeddings).toBe(0);
    expect(rows[0].embedded).toBe(false);
  });

  it("trims stray whitespace in category names (real library has ' COBIT')", () => {
    const rows = buildDocumentRows([manifest({ category: " COBIT" })], embeddingIndex);
    expect(rows[0].category).toBe("COBIT");
  });
});

describe("documentHasWarnings", () => {
  it("flags parse failures, unchunked, fallbacks, and errors", () => {
    expect(documentHasWarnings(manifest())).toBe(false);
    expect(documentHasWarnings(manifest({ parsed: false }))).toBe(true);
    expect(documentHasWarnings(manifest({ parsed: true, chunked: false }))).toBe(true);
    expect(documentHasWarnings(manifest({ parser_fallback: true }))).toBe(true);
    expect(documentHasWarnings(manifest({ chunking_error: "x" }))).toBe(true);
  });
});

describe("filterDocuments + buildFilterOptions", () => {
  const rows = buildDocumentRows(
    [
      manifest(),
      manifest({ document_id: "laws--نظام.pdf", filename: "نظام الشركات.pdf", category: "Laws", document_profile: "law", parser_used: "pypdfium2", parser_fallback: true }),
      manifest({ document_id: "iso--broken.pdf", filename: "broken.pdf", parsed: false, chunked: false, document_profile: "iso_standard", failure_reason: "boom" }),
    ],
    embeddingIndex,
  );

  it("derives filter options from the rows", () => {
    const opts = buildFilterOptions(rows);
    expect(opts.categories).toEqual(["ISO", "Laws"]);
    expect(opts.documentProfiles).toEqual(["iso_standard", "law"]);
    expect(opts.parsers).toContain("pypdf");
    expect(opts.parsers).toContain("pypdfium2");
    expect(opts.languages).toEqual(["ar", "en"]);
  });

  it("filters by category", () => {
    const out = filterDocuments(rows, { category: "Laws", documentProfile: null, status: null, parser: null, language: null, search: null });
    expect(out.map((r) => r.category)).toEqual(["Laws"]);
  });

  it("filters by status=warnings and status=parse_failed", () => {
    const warnings = filterDocuments(rows, { category: null, documentProfile: null, status: "warnings", parser: null, language: null, search: null });
    expect(warnings.length).toBe(2); // the fallback doc + the failed doc
    const failed = filterDocuments(rows, { category: null, documentProfile: null, status: "parse_failed", parser: null, language: null, search: null });
    expect(failed.map((r) => r.name)).toEqual(["broken.pdf"]);
  });

  it("filters by language and parser together", () => {
    const out = filterDocuments(rows, { category: null, documentProfile: null, status: null, parser: "pypdfium2", language: "ar", search: null });
    expect(out).toHaveLength(1);
    expect(out[0].parserUsed).toBe("pypdfium2");
  });

  it("searches case-insensitively across name and category", () => {
    expect(filterDocuments(rows, { category: null, documentProfile: null, status: null, parser: null, language: null, search: "27001" })).toHaveLength(1);
    expect(filterDocuments(rows, { category: null, documentProfile: null, status: null, parser: null, language: null, search: "iso" }).length).toBeGreaterThanOrEqual(1);
    expect(filterDocuments(rows, { category: null, documentProfile: null, status: null, parser: null, language: null, search: "nonexistent" })).toHaveLength(0);
  });
});

function chunk(overrides: Partial<ChunkRecord> = {}): ChunkRecord {
  return {
    chunk_id: "c1",
    document_id: "d",
    source_filename: "ISO 27001.pdf",
    category: "ISO",
    document_profile: "iso_standard",
    structure_profile: "standard_clause",
    content_type: "section",
    code: "5.1",
    title: "Leadership",
    path: ["Clause 5", "5.1"],
    level: 2,
    parent_chunk_id: null,
    position: 0,
    text: "body text here",
    character_count: 14,
    page_start: 12,
    page_end: 13,
    window_index: null,
    window_of_total: null,
    references: [],
    language: "en",
    recognizer_confidence: 1,
    chunker_version: "1.0",
    chunked_at: "2026-07-12T10:02:00+00:00",
    checksum_sha256: "sum",
    ...overrides,
  };
}

describe("buildChunkStatistics", () => {
  it("returns null with no chunks", () => {
    expect(buildChunkStatistics([])).toBeNull();
  });

  it("aggregates content-type, structure, page coverage and sizes", () => {
    const stats = buildChunkStatistics([
      chunk({ character_count: 100 }),
      chunk({ content_type: "window", structure_profile: "fallback_window", page_start: null, character_count: 300 }),
    ])!;
    expect(stats.total).toBe(2);
    expect(stats.byContentType).toEqual({ section: 1, window: 1 });
    expect(stats.byStructureProfile).toEqual({ standard_clause: 1, fallback_window: 1 });
    expect(stats.withPageNumbers).toBe(1);
    expect(stats.fallbackWindows).toBe(1);
    expect(stats.averageCharacters).toBe(200);
    expect(stats.largestChunkChars).toBe(300);
    expect(stats.smallestChunkChars).toBe(100);
  });
});

describe("buildDocumentDetail", () => {
  it("assembles a lossless detail view with citations and warnings", () => {
    const detail = buildDocumentDetail(
      manifest({ parser_fallback: true, parser_attempts: [{ backend: "pypdf", ok: false, error: "PdfStreamError" }, { backend: "pypdfium2", ok: true, error: null }] }),
      [chunk()],
      167,
      embeddingManifest,
    );
    expect(detail.pipelineStatus.embedded).toBe(true);
    expect(detail.embeddingStats.count).toBe(167);
    expect(detail.embeddingStats.model).toBe("local-deterministic-hash-v1");
    expect(detail.embeddingStats.dimensions).toBe(1536);
    expect(detail.citations[0]).toMatchObject({ code: "5.1", title: "Leadership" });
    expect(detail.parserAttempts).toHaveLength(2);
    expect(detail.warnings.some((w) => w.includes("fallback"))).toBe(true);
    // manifest is carried verbatim for the raw view
    expect(detail.manifest.document_id).toBe("iso--iso-27001.pdf");
  });

  it("surfaces a parse-failure warning and no chunk stats", () => {
    const detail = buildDocumentDetail(
      manifest({ parsed: false, chunked: false, status: "parse_failed", failure_reason: "PdfStreamError: Stream ended", chunk_count: null }),
      [],
      0,
      embeddingManifest,
    );
    expect(detail.chunkStats).toBeNull();
    expect(detail.embeddingStats.embedded).toBe(false);
    expect(detail.warnings[0]).toContain("Parsing failed");
  });
});

describe("buildPipelineHistory", () => {
  it("reconstructs an import run and an embedding run, newest first", () => {
    const runs = buildPipelineHistory([manifest()], embeddingManifest);
    expect(runs).toHaveLength(2);
    const embedding = runs.find((r) => r.stage === "Embedding")!;
    const importRun = runs.find((r) => r.stage.startsWith("Import"))!;
    expect(embedding.embeddingsGenerated).toBe(200);
    expect(embedding.provider).toBe("local");
    expect(embedding.approximate).toBe(false);
    expect(importRun.chunksGenerated).toBe(167);
    expect(importRun.approximate).toBe(true);
  });

  it("counts parse and chunk failures as run failures", () => {
    const runs = buildPipelineHistory(
      [manifest({ parsed: false, chunked: false }), manifest({ document_id: "b", chunked: false })],
      null,
    );
    const importRun = runs[0];
    expect(importRun.failures).toBe(2);
    expect(runs).toHaveLength(1); // no embedding manifest -> only the import run
  });
});
