-- RAG retrieval store: one row per indexed document chunk, embedding stored as a native
-- pgvector column (OpenAI text-embedding-3-large is 3072-dim). Retrieval uses the `<=>`
-- cosine-distance operator directly (`ORDER BY embedding <=> query LIMIT k`), matching the
-- exact-search semantics of the file-based adapter it replaces.
--
-- No ANN index (ivfflat/hnsw) is created: pgvector caps indexed dimensions at 2000 for the
-- `vector` type, and 3072 exceeds that. Sequential-scan cosine search is exact and fine at
-- current tenant data volumes; if corpus size later demands sub-linear search, re-encode the
-- column as `halfvec(3072)` (pgvector >= 0.7, index cap 4000) and add an HNSW index — a data
-- migration, not an architecture change.
CREATE TABLE IF NOT EXISTS document_chunks (
  tenant_id text NOT NULL,
  document_id text NOT NULL,
  chunk_index integer NOT NULL,
  file_name text NOT NULL,
  embedding_provider text NOT NULL,
  chunk_text text NOT NULL,
  char_start integer NOT NULL,
  char_end integer NOT NULL,
  embedding vector(3072) NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS document_chunks_tenant_id_idx ON document_chunks (tenant_id);
CREATE INDEX IF NOT EXISTS document_chunks_tenant_document_idx ON document_chunks (tenant_id, document_id);
