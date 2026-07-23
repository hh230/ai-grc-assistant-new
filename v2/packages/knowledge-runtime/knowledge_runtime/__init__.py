"""Rasheed V2 Knowledge Runtime — runtime, per-tenant ingestion of customer documents (roadmap P1).

`ingest_document(kb, text, …)` chunks a customer document (consuming the frozen `knowledge-importer`
chunker) into tenant-scoped, citable `CorpusChunk`s and adds them to a `TenantKnowledgeBase` — so
the platform's retrieval/search find the **customer's own data**, tenant-isolated. The in-memory
base is swappable for pgvector in production (same provider interface).
"""

from knowledge_runtime.ingest import DEFAULT_CATEGORY, ingest_document
from knowledge_runtime.tenant_kb import TenantKnowledgeBase

__all__ = ["TenantKnowledgeBase", "ingest_document", "DEFAULT_CATEGORY"]
