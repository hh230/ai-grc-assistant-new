/**
 * Chunking — split extracted text into overlapping, word-boundary-aligned windows for
 * embedding and retrieval. Overlap preserves context across chunk edges.
 */

import type { Chunk } from "./types";

export interface ChunkOptions {
  maxChars?: number;
  overlap?: number;
}

export function chunkText(text: string, options: ChunkOptions = {}): Chunk[] {
  const maxChars = options.maxChars ?? 1200;
  const overlap = options.overlap ?? 150;
  const clean = text.trim();
  if (!clean) return [];

  const chunks: Chunk[] = [];
  let start = 0;
  while (start < clean.length) {
    let end = Math.min(start + maxChars, clean.length);
    // Prefer a clean break at whitespace rather than mid-word.
    if (end < clean.length) {
      const lastBreak = clean.lastIndexOf(" ", end);
      if (lastBreak > start + maxChars * 0.5) end = lastBreak;
    }
    const slice = clean.slice(start, end).trim();
    if (slice) {
      chunks.push({ index: chunks.length, text: slice, charStart: start, charEnd: end });
    }
    if (end >= clean.length) break;
    start = Math.max(end - overlap, start + 1);
  }
  return chunks;
}
