/**
 * Vector store behind a port, backed by PostgreSQL + pgvector (`document_chunks` table,
 * `vector(3072)` column — see lib/db/migrations/0005_document_chunks.sql). Retrieval uses
 * the `<=>` cosine-distance operator (`score = 1 - distance`), which is exact search —
 * numerically equivalent to the brute-force cosine similarity the file-based adapter it
 * replaces used to compute in JS. Strictly tenant-scoped. Node-only.
 */

import { getPool } from "@/lib/db/pool";
import type { StoredChunk } from "./types";

export interface SearchHit {
  documentId: string;
  fileName: string;
  chunk: StoredChunk;
  score: number;
}

interface DocumentVectors {
  documentId: string;
  tenantId: string;
  fileName: string;
  embeddingProvider: string;
  chunks: StoredChunk[];
}

export interface VectorStore {
  put(vectors: DocumentVectors): Promise<void>;
  delete(tenantId: string, documentId: string): Promise<void>;
  search(
    tenantId: string,
    queryVector: number[],
    topK: number,
    options?: { documentId?: string },
  ): Promise<SearchHit[]>;
}

/** pgvector accepts a bracketed literal, e.g. "[0.1,0.2,...]", cast with `::vector`. */
function toVectorLiteral(vector: number[]): string {
  return `[${vector.join(",")}]`;
}

interface SearchRow {
  document_id: string;
  file_name: string;
  chunk_index: number;
  chunk_text: string;
  char_start: number;
  char_end: number;
  score: number;
}

class PostgresVectorStore implements VectorStore {
  async put(vectors: DocumentVectors): Promise<void> {
    const client = await getPool().connect();
    try {
      await client.query("BEGIN");
      await client.query(`DELETE FROM document_chunks WHERE tenant_id = $1 AND document_id = $2`, [
        vectors.tenantId,
        vectors.documentId,
      ]);
      for (const chunk of vectors.chunks) {
        await client.query(
          `INSERT INTO document_chunks (
             tenant_id, document_id, chunk_index, file_name, embedding_provider, chunk_text,
             char_start, char_end, embedding
           ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::vector)`,
          [
            vectors.tenantId,
            vectors.documentId,
            chunk.index,
            vectors.fileName,
            vectors.embeddingProvider,
            chunk.text,
            chunk.charStart,
            chunk.charEnd,
            toVectorLiteral(chunk.embedding),
          ],
        );
      }
      await client.query("COMMIT");
    } catch (error) {
      await client.query("ROLLBACK");
      throw error;
    } finally {
      client.release();
    }
  }

  async delete(tenantId: string, documentId: string): Promise<void> {
    await getPool().query(`DELETE FROM document_chunks WHERE tenant_id = $1 AND document_id = $2`, [
      tenantId,
      documentId,
    ]);
  }

  async search(
    tenantId: string,
    queryVector: number[],
    topK: number,
    options: { documentId?: string } = {},
  ): Promise<SearchHit[]> {
    const literal = toVectorLiteral(queryVector);
    const params: unknown[] = [literal, tenantId];
    let documentFilter = "";
    if (options.documentId) {
      params.push(options.documentId);
      documentFilter = `AND document_id = $${params.length}`;
    }
    params.push(topK);

    const { rows } = await getPool().query<SearchRow>(
      `SELECT document_id, file_name, chunk_index, chunk_text, char_start, char_end,
              1 - (embedding <=> $1::vector) AS score
       FROM document_chunks
       WHERE tenant_id = $2 ${documentFilter}
       ORDER BY embedding <=> $1::vector ASC
       LIMIT $${params.length}`,
      params,
    );

    return rows.map((row) => ({
      documentId: row.document_id,
      fileName: row.file_name,
      // The embedding itself is not needed by any caller of search() — omit it to avoid
      // shipping 3072 floats per hit over the wire for nothing.
      chunk: {
        index: row.chunk_index,
        text: row.chunk_text,
        charStart: row.char_start,
        charEnd: row.char_end,
        embedding: [],
      },
      score: row.score,
    }));
  }
}

export const vectorStore: VectorStore = new PostgresVectorStore();
