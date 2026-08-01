/**
 * The only layer that touches the filesystem. It reads the generated JSON artifacts the
 * Knowledge Pipeline produced — manifests, chunks, embedding manifest, embedding index —
 * and returns them as typed data. It never reads a PDF or any live source, and it holds
 * no aggregation logic (that lives in the pure services, which take this data as input
 * and are unit-tested without a filesystem).
 *
 * The knowledge directory defaults to `v2/knowledge` relative to this app and can be
 * overridden with the `KNOWLEDGE_DIR` environment variable.
 */

import { promises as fs } from "node:fs";
import path from "node:path";

import type {
  ChunkRecord,
  DocumentManifest,
  EmbeddingIndex,
  EmbeddingManifest,
  ManifestIndex,
} from "@/lib/types/artifacts";

function knowledgeDir(): string {
  if (process.env.KNOWLEDGE_DIR) return process.env.KNOWLEDGE_DIR;
  // this file: v2/apps/knowledge-center/lib/services -> up 4 to v2, then knowledge
  return path.resolve(process.cwd(), "..", "..", "knowledge");
}

async function readJson<T>(filePath: string): Promise<T | null> {
  try {
    const raw = await fs.readFile(filePath, "utf-8");
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

export async function loadManifestIndex(): Promise<ManifestIndex | null> {
  return readJson<ManifestIndex>(path.join(knowledgeDir(), "manifests", "index.json"));
}

export async function loadAllManifests(): Promise<DocumentManifest[]> {
  const dir = path.join(knowledgeDir(), "manifests");
  let entries: string[];
  try {
    entries = await fs.readdir(dir);
  } catch {
    return [];
  }
  const files = entries.filter((f) => f.endsWith(".json") && f !== "index.json");
  const manifests = await Promise.all(
    files.map((f) => readJson<DocumentManifest>(path.join(dir, f))),
  );
  return manifests
    .filter((m): m is DocumentManifest => m !== null)
    .sort((a, b) => a.filename.localeCompare(b.filename));
}

export async function loadManifest(documentId: string): Promise<DocumentManifest | null> {
  return readJson<DocumentManifest>(
    path.join(knowledgeDir(), "manifests", `${documentId}.json`),
  );
}

export async function loadChunks(documentId: string): Promise<ChunkRecord[]> {
  const data = await readJson<ChunkRecord[]>(
    path.join(knowledgeDir(), "chunks", `${documentId}.json`),
  );
  return data ?? [];
}

export async function loadEmbeddingManifest(): Promise<EmbeddingManifest | null> {
  return readJson<EmbeddingManifest>(
    path.join(knowledgeDir(), "embeddings", "embedding_manifest.json"),
  );
}

export async function loadEmbeddingIndex(): Promise<EmbeddingIndex | null> {
  return readJson<EmbeddingIndex>(
    path.join(knowledgeDir(), "embeddings", "embedding_index.json"),
  );
}
