"""Integration tests for the pgvector adapter. They connect to the DSN in
`RETRIEVAL_PG_DSN` (default: the isolated `rasheed_v2` dev DB) and **skip cleanly** when no
database is reachable, so the unit suite still runs anywhere.

Two kinds of test:
 1. read-only search/filter/drop-in tests against the real populated `knowledge_vectors`;
 2. an isolated upsert/incremental test against a self-managed TEMP table (fast, no
    pollution of the real table), exercising the exact ON CONFLICT merge the import uses.
"""

from __future__ import annotations

from pathlib import Path

import pytest

psycopg = pytest.importorskip("psycopg")

from retrieval_engine import Filter, RetrievalEngine, RetrievalQuery  # noqa: E402
from retrieval_engine.pg.config import TABLE, dsn  # noqa: E402
from retrieval_engine.providers.corpus import InMemoryCorpus  # noqa: E402
from retrieval_engine.providers.inmemory_keyword import InMemoryKeywordProvider  # noqa: E402
from retrieval_engine.providers.pgvector_provider import PgVectorProvider  # noqa: E402

_V2 = Path(__file__).resolve().parents[3]  # tests/ → retrieval-engine → packages → v2


def _connect():
    try:
        conn = psycopg.connect(dsn(), autocommit=True, connect_timeout=3)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"no reachable PostgreSQL ({exc})")
    return conn


@pytest.fixture(scope="module")
def conn():
    c = _connect()
    yield c
    c.close()


@pytest.fixture(scope="module")
def populated(conn):
    row = conn.execute(f"SELECT count(*) FROM {TABLE}").fetchone()
    if not row or row[0] == 0:
        pytest.skip("knowledge_vectors is empty — run the import first")
    return row[0]


@pytest.fixture(scope="module")
def corpus():
    chunks_dir = _V2 / "knowledge" / "chunks"
    if not chunks_dir.exists():
        pytest.skip("chunk artifacts not present")
    return InMemoryCorpus.load(chunks_dir)


# ── read-only, against the real populated table ───────────────────────────────
def test_row_count_matches_corpus_scale(populated):
    assert populated == 31793


def test_pgvector_provider_returns_citable_hits(corpus, populated):
    provider = PgVectorProvider(corpus)
    hits = provider.search("access control policy", Filter(), top_k=5)
    assert len(hits) == 5
    assert all(h.source == "vector" for h in hits)
    assert all(h.chunk.source_filename for h in hits)  # every hit carries a citable payload
    assert all(0.0 <= h.score <= 1.0 or h.score <= 1.0 for h in hits)  # cosine similarity
    provider.close()


def test_pgvector_filter_scopes_by_profile(corpus, populated):
    provider = PgVectorProvider(corpus)
    hits = provider.search("risk", Filter(document_profiles=("iso_standard",)), top_k=10)
    assert hits
    assert all(h.chunk.document_profile == "iso_standard" for h in hits)
    provider.close()


def test_pgvector_filter_scopes_by_category_and_language(corpus, populated):
    provider = PgVectorProvider(corpus)
    hits = provider.search("حماية البيانات", Filter(categories=("Laws",), languages=("ar",)), top_k=10)
    assert all(h.chunk.category == "Laws" and h.chunk.language == "ar" for h in hits)
    provider.close()


def test_pgvector_is_a_drop_in_replacement(corpus, populated):
    # the SAME engine, unchanged, works with the pgvector provider
    engine = RetrievalEngine(PgVectorProvider(corpus), InMemoryKeywordProvider(corpus))
    ctx = engine.retrieve(RetrievalQuery(text="incident response", top_k=3))
    assert ctx.results
    assert ctx.results[0].citation.formatted  # cited, assembled context bundle


# ── isolated upsert / incremental logic (TEMP table) ──────────────────────────
def _row(chunk_id, checksum, model="m", version="v1"):
    vec = "[" + ",".join(["0.1"] * 1536) + "]"
    return (chunk_id, "doc1", vec, model, version, checksum, "iso_standard", "standard_clause",
            "ISO", "en", "A.5.15", "section")

_COLS = ("chunk_id", "document_id", "embedding", "embedding_model", "embedding_version",
         "chunk_checksum", "document_profile", "structure_profile", "category", "language",
         "code", "content_type")


def _merge(cur):
    assignments = ", ".join(f"{c} = EXCLUDED.{c}" for c in _COLS if c != "chunk_id")
    cur.execute(
        f"INSERT INTO kv_it ({', '.join(_COLS)}) SELECT {', '.join(_COLS)} FROM kv_stage "
        f"ON CONFLICT (chunk_id) DO UPDATE SET {assignments}, updated_at = now() "
        f"WHERE kv_it.chunk_checksum IS DISTINCT FROM EXCLUDED.chunk_checksum "
        f"   OR kv_it.embedding_model IS DISTINCT FROM EXCLUDED.embedding_model "
        f"   OR kv_it.embedding_version IS DISTINCT FROM EXCLUDED.embedding_version"
    )


def test_upsert_is_idempotent_and_incremental(conn):
    # a private connection with its own transaction so temp tables are isolated
    c = _connect()
    try:
        c.autocommit = False
        cur = c.cursor()
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        cur.execute(
            "CREATE TEMP TABLE kv_it (LIKE knowledge_vectors INCLUDING DEFAULTS, "
            "PRIMARY KEY (chunk_id)) ON COMMIT DROP"
        )

        def stage(rows):
            cur.execute("DROP TABLE IF EXISTS kv_stage")
            cur.execute("CREATE TEMP TABLE kv_stage (LIKE knowledge_vectors INCLUDING DEFAULTS)")
            with cur.copy(f"COPY kv_stage ({', '.join(_COLS)}) FROM STDIN") as copy:
                for r in rows:
                    copy.write_row(r)

        # first load: 2 inserted
        stage([_row("a", "sum-a"), _row("b", "sum-b")])
        _merge(cur)
        assert cur.execute("SELECT count(*) FROM kv_it").fetchone()[0] == 2

        # re-load identical: idempotent, no change
        stage([_row("a", "sum-a"), _row("b", "sum-b")])
        _merge(cur)
        pre = cur.execute("SELECT max(updated_at) FROM kv_it").fetchone()[0]
        stage([_row("a", "sum-a"), _row("b", "sum-b")])
        _merge(cur)
        post = cur.execute("SELECT max(updated_at) FROM kv_it").fetchone()[0]
        assert pre == post  # nothing rewritten

        # changed checksum on 'a' only → incremental update of one row
        stage([_row("a", "sum-a-NEW"), _row("b", "sum-b")])
        changed = cur.execute(
            "SELECT count(*) FROM kv_stage s JOIN kv_it t USING (chunk_id) "
            "WHERE t.chunk_checksum IS DISTINCT FROM s.chunk_checksum"
        ).fetchone()[0]
        assert changed == 1
        _merge(cur)
        assert cur.execute("SELECT chunk_checksum FROM kv_it WHERE chunk_id='a'").fetchone()[0] == "sum-a-NEW"
        assert cur.execute("SELECT chunk_checksum FROM kv_it WHERE chunk_id='b'").fetchone()[0] == "sum-b"
        c.rollback()
    finally:
        c.close()
