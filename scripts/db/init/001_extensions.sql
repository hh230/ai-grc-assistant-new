-- Enable the pgvector extension for RAG embeddings (CLAUDE.md §12).
-- Schema/tables are NOT defined here — migrations own those (no models yet).
CREATE EXTENSION IF NOT EXISTS vector;
