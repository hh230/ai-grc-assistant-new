"""Import the generated embeddings into pgvector — idempotent, resumable, incremental.

Strategy: bulk-COPY every embedding into a TEMP staging table, compute insert/update/skip
counts by diffing staging against the live table, then a single ON CONFLICT merge that
updates only rows whose checksum / model / version changed and prunes rows no longer
present. The whole merge is one transaction — an interruption leaves the table unchanged
(resumable: just re-run, unchanged rows are skipped). The HNSW index is built after the
initial bulk load for speed; on later imports it already exists and pgvector maintains it
incrementally.
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

import psycopg

from retrieval_engine.pg import schema
from retrieval_engine.pg.config import TABLE
from retrieval_engine.pg.config import dsn as default_dsn

_RESERVED = {"embedding_manifest.json", "embedding_index.json", "_checkpoint.json"}
_COLUMNS = (
    "chunk_id", "document_id", "embedding", "embedding_model", "embedding_version",
    "chunk_checksum", "document_profile", "structure_profile", "category", "language",
    "code", "content_type",
)


@dataclass
class ImportStats:
    total_in_files: int = 0
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    pruned: int = 0
    load_seconds: float = 0.0
    index_seconds: float = 0.0
    index_built: bool = False
    db_stats: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "total_in_files": self.total_in_files,
            "inserted": self.inserted,
            "updated": self.updated,
            "skipped": self.skipped,
            "pruned": self.pruned,
            "load_seconds": round(self.load_seconds, 2),
            "index_seconds": round(self.index_seconds, 2),
            "index_built": self.index_built,
            "db_stats": self.db_stats,
        }


def _iter_records(embeddings_dir: Path) -> Iterator[dict[str, object]]:
    for path in sorted(embeddings_dir.glob("*.json")):
        if path.name in _RESERVED:
            continue
        for record in json.loads(path.read_text(encoding="utf-8")):
            meta = record.get("chunk_metadata") or {}
            yield {
                "chunk_id": record["chunk_id"],
                "document_id": record["document_id"],
                "embedding": "[" + ",".join(str(x) for x in record["vector"]) + "]",
                "embedding_model": record["embedding_model"],
                "embedding_version": record["embedding_version"],
                "chunk_checksum": record.get("chunk_checksum", ""),
                "document_profile": record.get("document_profile"),
                "structure_profile": meta.get("structure_profile") or record.get("structure_profile"),
                "category": (meta.get("category") or "").strip() or None,
                "language": meta.get("language"),
                "code": meta.get("code"),
                "content_type": meta.get("content_type"),
            }


def run_import(embeddings_dir: Path, dsn: str | None = None, *, prune: bool = True) -> ImportStats:
    stats = ImportStats()
    conn = psycopg.connect(dsn or default_dsn(), autocommit=False)
    try:
        schema.ensure_table_and_filters(conn)
        had_index = schema.vector_index_exists(conn)

        load_start = time.perf_counter()
        with conn.cursor() as cur:
            cur.execute(f"CREATE TEMP TABLE staging (LIKE {TABLE} INCLUDING DEFAULTS) ON COMMIT DROP")
            col_list = ", ".join(_COLUMNS)
            with cur.copy(f"COPY staging ({col_list}) FROM STDIN") as copy:
                for rec in _iter_records(embeddings_dir):
                    stats.total_in_files += 1
                    copy.write_row(tuple(rec[c] for c in _COLUMNS))

            # counts (diff staging vs live) before merging
            stats.inserted = cur.execute(
                f"SELECT count(*) FROM staging s WHERE NOT EXISTS "
                f"(SELECT 1 FROM {TABLE} t WHERE t.chunk_id = s.chunk_id)"
            ).fetchone()[0]
            stats.updated = cur.execute(
                f"SELECT count(*) FROM staging s JOIN {TABLE} t USING (chunk_id) "
                f"WHERE t.chunk_checksum IS DISTINCT FROM s.chunk_checksum "
                f"   OR t.embedding_model IS DISTINCT FROM s.embedding_model "
                f"   OR t.embedding_version IS DISTINCT FROM s.embedding_version"
            ).fetchone()[0]
            stats.skipped = stats.total_in_files - stats.inserted - stats.updated

            assignments = ", ".join(f"{c} = EXCLUDED.{c}" for c in _COLUMNS if c != "chunk_id")
            cur.execute(
                f"INSERT INTO {TABLE} ({', '.join(_COLUMNS)}) "
                f"SELECT {', '.join(_COLUMNS)} FROM staging "
                f"ON CONFLICT (chunk_id) DO UPDATE SET {assignments}, updated_at = now() "
                f"WHERE {TABLE}.chunk_checksum IS DISTINCT FROM EXCLUDED.chunk_checksum "
                f"   OR {TABLE}.embedding_model IS DISTINCT FROM EXCLUDED.embedding_model "
                f"   OR {TABLE}.embedding_version IS DISTINCT FROM EXCLUDED.embedding_version"
            )
            if prune:
                pruned = cur.execute(
                    f"DELETE FROM {TABLE} WHERE chunk_id NOT IN (SELECT chunk_id FROM staging)"
                )
                stats.pruned = pruned.rowcount
        conn.commit()
        stats.load_seconds = time.perf_counter() - load_start

        if not had_index:
            index_start = time.perf_counter()
            schema.create_vector_index(conn)
            stats.index_seconds = time.perf_counter() - index_start
            stats.index_built = True

        stats.db_stats = schema.stats(conn)
        return stats
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    import argparse

    _V2 = Path(__file__).resolve().parents[4]  # …/retrieval_engine/pg/ → up to v2/
    parser = argparse.ArgumentParser(description="Import generated embeddings into pgvector")
    parser.add_argument("--embeddings-dir", type=Path, default=_V2 / "knowledge" / "embeddings")
    parser.add_argument("--dsn", type=str, default=None)
    parser.add_argument("--no-prune", action="store_true")
    args = parser.parse_args(argv)

    t = time.perf_counter()
    stats = run_import(args.embeddings_dir, args.dsn, prune=not args.no_prune)
    print(json.dumps(stats.to_dict(), indent=2, ensure_ascii=False))
    print(f"Total wall time: {time.perf_counter() - t:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
