"""Schema DDL + database statistics for the pgvector store. Granular helpers let the import
tool build the HNSW index *after* the initial bulk load (much faster than maintaining it
during a first load), while incremental imports leave the existing index to maintain itself.
The canonical, documented DDL also lives in migrations/0001_knowledge_vectors.sql."""

from __future__ import annotations

import psycopg

from retrieval_engine.pg.config import TABLE

HNSW_INDEX = "kv_embedding_hnsw_idx"

_TABLE_DDL = f"""
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS {TABLE} (
    chunk_id           text PRIMARY KEY,
    document_id        text NOT NULL,
    embedding          vector(1536) NOT NULL,
    embedding_model    text NOT NULL,
    embedding_version  text NOT NULL,
    chunk_checksum     text NOT NULL,
    document_profile   text,
    structure_profile  text,
    category           text,
    language           text,
    code               text,
    content_type       text,
    -- Tenancy classification (ADR 0040 §2). `scope_kind` defaults to 'global', so existing
    -- corpus rows (the shared framework/law/standard library) are GLOBAL automatically;
    -- organization data is written with scope_kind='organization' + an organization_id.
    scope_kind         text NOT NULL DEFAULT 'global',
    organization_id    text,
    updated_at         timestamptz NOT NULL DEFAULT now()
);
"""

_FILTER_INDEXES = [
    f"CREATE INDEX IF NOT EXISTS kv_document_profile_idx  ON {TABLE} (document_profile)",
    f"CREATE INDEX IF NOT EXISTS kv_category_idx          ON {TABLE} (category)",
    f"CREATE INDEX IF NOT EXISTS kv_language_idx          ON {TABLE} (language)",
    f"CREATE INDEX IF NOT EXISTS kv_structure_profile_idx ON {TABLE} (structure_profile)",
    f"CREATE INDEX IF NOT EXISTS kv_document_id_idx       ON {TABLE} (document_id)",
    f"CREATE INDEX IF NOT EXISTS kv_code_idx              ON {TABLE} (code text_pattern_ops)",
    # The tenant-scope predicate is applied on every query — index it (ADR 0040 §4).
    f"CREATE INDEX IF NOT EXISTS kv_scope_idx             ON {TABLE} (scope_kind, organization_id)",
]

_HNSW_DDL = (
    f"CREATE INDEX IF NOT EXISTS {HNSW_INDEX} ON {TABLE} "
    f"USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)"
)


def ensure_table_and_filters(conn: psycopg.Connection) -> None:
    conn.execute(_TABLE_DDL)
    for ddl in _FILTER_INDEXES:
        conn.execute(ddl)
    conn.commit()


def vector_index_exists(conn: psycopg.Connection) -> bool:
    row = conn.execute("SELECT 1 FROM pg_class WHERE relname = %s", (HNSW_INDEX,)).fetchone()
    return row is not None


def create_vector_index(conn: psycopg.Connection) -> None:
    conn.execute(_HNSW_DDL)
    conn.commit()


def apply_schema(conn: psycopg.Connection) -> None:
    """Full schema (table + filter indexes + HNSW). Convenient for tests; the import tool
    builds the HNSW index separately for load speed."""
    ensure_table_and_filters(conn)
    create_vector_index(conn)


def row_count(conn: psycopg.Connection, table: str = TABLE) -> int:
    row = conn.execute(f"SELECT count(*) FROM {table}").fetchone()
    return int(row[0]) if row else 0


def stats(conn: psycopg.Connection, table: str = TABLE) -> dict[str, object]:
    count = row_count(conn, table)
    total = conn.execute("SELECT pg_size_pretty(pg_total_relation_size(%s))", (table,)).fetchone()
    tbl = conn.execute("SELECT pg_size_pretty(pg_relation_size(%s))", (table,)).fetchone()
    indexes = conn.execute(
        "SELECT indexrelname, pg_size_pretty(pg_relation_size(indexrelid)) "
        "FROM pg_stat_user_indexes WHERE relname = %s ORDER BY indexrelname",
        (table,),
    ).fetchall()
    return {
        "row_count": count,
        "total_size": total[0] if total else None,
        "table_size": tbl[0] if tbl else None,
        "indexes": {name: size for name, size in indexes},
    }
