"""PgVectorProvider — the production vector backend. A **drop-in replacement** for
`InMemoryVectorProvider`: it implements the exact same `VectorSearchProvider.search`
contract, so the Retrieval Engine (engine, planner, fusion, ranking, citation, assembly)
runs unchanged and never learns that vectors now live in PostgreSQL.

Vectors + filter metadata live in the `knowledge_vectors` table (see migrations/); the ANN
happens in pgvector via an HNSW index. The chunk *payload* (text + citation fields) is
resolved from the in-memory corpus by chunk_id — the table intentionally does not duplicate
that data. The query is embedded with the same algorithm as the corpus (Phase 4 hash
embedder), exactly as the in-memory provider does.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from pipeline_contracts import KnowledgeScope

from retrieval_engine.pg.config import DEFAULT_EF_SEARCH, EMBEDDING_DIMENSION, TABLE
from retrieval_engine.pg.config import dsn as default_dsn
from retrieval_engine.providers.corpus import InMemoryCorpus
from retrieval_engine.providers.interfaces import Filter, ScoredHit
from retrieval_engine.providers.vector import hash_embed_query

if TYPE_CHECKING:  # import only for type checkers; never at runtime
    import psycopg

_MISSING_PG = (
    "PgVectorProvider needs the 'psycopg', 'pgvector', and 'numpy' packages. "
    "Install the optional extra: retrieval-engine[pgvector]"
)


def _load_pg() -> tuple[Any, Any]:
    """Import the PostgreSQL SDKs lazily so the core package imports without them."""
    try:
        import psycopg
        from pgvector.psycopg import register_vector
    except ImportError as exc:  # pragma: no cover - exercised only without the extra installed
        raise ImportError(_MISSING_PG) from exc
    return psycopg, register_vector


def _load_numpy() -> Any:
    try:
        import numpy as np
    except ImportError as exc:  # pragma: no cover - exercised only without the extra installed
        raise ImportError(_MISSING_PG) from exc
    return np


def _open(dsn_str: str, ef_search: int) -> psycopg.Connection:
    psycopg, register_vector = _load_pg()
    conn = psycopg.connect(dsn_str, autocommit=True)
    register_vector(conn)
    conn.execute(f"SET hnsw.ef_search = {int(ef_search)}")
    # This connection only ever issues `ORDER BY embedding <=> q LIMIT k` ANN queries. On a
    # small table the planner's cost model can prefer a seq scan (computing every distance),
    # which measured ~40× slower than the HNSW index scan here. Disabling seq scan on this
    # dedicated vector-search connection forces the HNSW index — a standard pgvector
    # deployment pattern; it does not affect any other connection or V1.
    conn.execute("SET enable_seqscan = off")
    return conn


def _where(f: Filter) -> tuple[str, dict[str, object]]:
    """Compile the Filter into a SQL predicate + params. `codes` matches exact-or-prefix via
    LIKE ANY, mirroring the in-memory provider's `passes_filter`."""
    clauses: list[str] = []
    params: dict[str, object] = {}
    # Tenant scope, applied *inside* the store query (ADR 0040 §4). No scope or a GLOBAL scope
    # ⇒ global rows only (fail-safe); an ORGANIZATION scope ⇒ global ∪ that org's rows.
    scope = f.scope
    if scope is None or scope.kind is KnowledgeScope.GLOBAL:
        clauses.append("scope_kind = 'global'")
    else:
        clauses.append(
            "(scope_kind = 'global' "
            "OR (scope_kind = 'organization' AND organization_id = %(scope_org)s))"
        )
        params["scope_org"] = scope.tenant_id
    if f.document_profiles:
        clauses.append("document_profile = ANY(%(profiles)s)")
        params["profiles"] = list(f.document_profiles)
    if f.categories:
        clauses.append("category = ANY(%(categories)s)")
        params["categories"] = list(f.categories)
    if f.structure_profiles:
        clauses.append("structure_profile = ANY(%(structures)s)")
        params["structures"] = list(f.structure_profiles)
    if f.languages:
        clauses.append("language = ANY(%(languages)s)")
        params["languages"] = list(f.languages)
    if f.document_ids:
        clauses.append("document_id = ANY(%(document_ids)s)")
        params["document_ids"] = list(f.document_ids)
    if f.codes:
        clauses.append("code LIKE ANY(%(code_patterns)s)")
        params["code_patterns"] = [c + "%" for c in f.codes]
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


class PgVectorProvider:
    def __init__(
        self,
        corpus: InMemoryCorpus,
        *,
        dsn: str | None = None,
        connection: psycopg.Connection | None = None,
        table: str = TABLE,
        embed_query: Callable[[str, int], list[float]] | None = None,
        ef_search: int = DEFAULT_EF_SEARCH,
        dimension: int = EMBEDDING_DIMENSION,
    ) -> None:
        self._corpus = corpus
        self._table = table
        self._dimension = dimension
        self._embed = embed_query or hash_embed_query
        self._owns_conn = connection is None
        self._conn = connection or _open(dsn or default_dsn(), ef_search)
        _, register_vector = _load_pg()
        register_vector(self._conn)  # idempotent; ensures the vector adapter on any connection

    def search(self, query: str, filter: Filter, top_k: int) -> list[ScoredHit]:
        if top_k <= 0:
            return []
        np = _load_numpy()
        vec = self._embed(query, self._dimension)
        where, params = _where(filter)
        params["q"] = np.asarray(vec, dtype=np.float32)  # numpy array → adapted to ::vector
        params["k"] = top_k
        sql = (
            f"SELECT chunk_id, 1 - (embedding <=> %(q)s) AS score "
            f"FROM {self._table}{where} "
            f"ORDER BY embedding <=> %(q)s LIMIT %(k)s"
        )
        rows = self._conn.execute(sql, params).fetchall()

        hits: list[ScoredHit] = []
        for chunk_id, score in rows:
            chunk = self._corpus.by_id.get(chunk_id)
            if chunk is None:
                continue  # vector present but chunk payload missing — skip rather than surface uncitable
            hits.append(ScoredHit(chunk=chunk, score=float(score), source="vector"))
        return hits

    def close(self) -> None:
        if self._owns_conn:
            self._conn.close()
