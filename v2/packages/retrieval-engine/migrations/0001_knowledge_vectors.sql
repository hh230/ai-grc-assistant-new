-- Rasheed V2 — Retrieval Engine — pgvector vector store (Phase 9B)
-- Applied to an ISOLATED database (default: rasheed_v2). Does not touch V1's `aigrc`.
--
-- Design: the table stores ONLY what vector search + metadata filtering + incremental
-- import need — the vector, the provenance keys (model/version/checksum), and the columns
-- the Filter predicate uses. It deliberately does NOT duplicate the chunk text, title,
-- heading path, or page numbers: those live in the generated chunk artifacts and are
-- resolved into the result payload by chunk_id. The vector table is the index, not a copy
-- of the corpus.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS knowledge_vectors (
    chunk_id           text        PRIMARY KEY,
    document_id        text        NOT NULL,
    embedding          vector(1536) NOT NULL,
    embedding_model    text        NOT NULL,
    embedding_version  text        NOT NULL,
    chunk_checksum     text        NOT NULL,
    -- metadata required for the Filter predicate (see providers/interfaces.py::Filter)
    document_profile   text,
    structure_profile  text,
    category           text,
    language           text,
    code               text,
    content_type       text,
    updated_at         timestamptz NOT NULL DEFAULT now()
);

-- Filter indexes: equality/IN predicates the retrieval Filter applies before ANN.
CREATE INDEX IF NOT EXISTS kv_document_profile_idx  ON knowledge_vectors (document_profile);
CREATE INDEX IF NOT EXISTS kv_category_idx          ON knowledge_vectors (category);
CREATE INDEX IF NOT EXISTS kv_language_idx          ON knowledge_vectors (language);
CREATE INDEX IF NOT EXISTS kv_structure_profile_idx ON knowledge_vectors (structure_profile);
CREATE INDEX IF NOT EXISTS kv_document_id_idx       ON knowledge_vectors (document_id);
CREATE INDEX IF NOT EXISTS kv_code_idx              ON knowledge_vectors (code text_pattern_ops);

-- ── Vector ANN index ──────────────────────────────────────────────────────────
-- HNSW (not IVFFlat) — see the operational docs for the rationale. Cosine ops, since the
-- embeddings are L2-normalized at generation time. 1536 dims fits under pgvector's 2000-dim
-- HNSW cap (the exact reason the Knowledge Library chose 1536).
CREATE INDEX IF NOT EXISTS kv_embedding_hnsw_idx
    ON knowledge_vectors
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
