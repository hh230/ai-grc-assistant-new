-- Saudi Regulations Ingestion Pipeline (KI-P7, ADR-0031): embeddings are generated only after
-- an admin approves a regulation version (never on ingestion) — these columns hold the result.
-- Written by the Python side (apps/api) via a `::vector` text-cast, the same pgvector column
-- shape apps/web's own document_chunks (0005_document_chunks.sql) already established for
-- OpenAI text-embedding-3-large (3072-dim). No index: same 2000-dim pgvector index cap noted
-- there, and this task deliberately does not wire these embeddings into any retrieval path
-- (see ADR-0032 for the deferred internal-DB retrieval-priority follow-up).
ALTER TABLE regulation_sections
  ADD COLUMN IF NOT EXISTS embedding vector(3072),
  ADD COLUMN IF NOT EXISTS embedding_model text,
  ADD COLUMN IF NOT EXISTS embedded_at timestamptz;
