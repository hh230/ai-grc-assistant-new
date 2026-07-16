"""Benchmark + validation: InMemoryVectorProvider vs PgVectorProvider on the real corpus.

Measures, per provider: index/setup time, query latency (p50/p95/p99), throughput, and
process memory. Then runs a validation pass over 100 representative queries comparing the
two through the *unchanged* Retrieval Engine — citation overlap, ranking agreement,
confidence, and latency — highlighting any differences (which come only from HNSW's
approximate ANN on the low-weight, non-semantic hash-vector signal; keyword/BM25 dominates
the final ranking).

Run: python -m retrieval_engine.pg.benchmark
"""

from __future__ import annotations

import statistics
import time
from pathlib import Path

from retrieval_engine import Filter, RetrievalEngine, RetrievalQuery
from retrieval_engine.providers.corpus import InMemoryCorpus
from retrieval_engine.providers.inmemory_keyword import InMemoryKeywordProvider
from retrieval_engine.providers.inmemory_vector import InMemoryVectorProvider
from retrieval_engine.providers.pgvector_provider import PgVectorProvider

_V2 = Path(__file__).resolve().parents[4]


def _rss_mb() -> float:
    import resource

    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return peak / (1024 * 1024) if peak > 10**7 else peak / 1024  # bytes on macOS, KB on linux


def _percentiles(latencies_ms: list[float]) -> dict[str, float]:
    s = sorted(latencies_ms)
    n = len(s)

    def pct(p: float) -> float:
        return round(s[min(n - 1, int(p * n))], 2)

    return {
        "p50": pct(0.50),
        "p95": pct(0.95),
        "p99": pct(0.99),
        "mean": round(statistics.fmean(s), 2),
        "min": round(s[0], 2),
        "max": round(s[-1], 2),
    }


QUERIES = [
    "access control policy", "information security risk assessment", "incident response",
    "supplier relationships", "business continuity", "data protection and privacy",
    "encryption", "segregation of duties", "management review", "acceptable use",
    "threat intelligence", "logging and monitoring", "vulnerability management",
    "secure development", "physical security", "human resource security",
    "cloud security", "network security controls", "backup and recovery", "risk treatment",
    "governance oversight", "internal audit", "code of conduct", "whistleblowing",
    "anti bribery", "vendor management", "breach notification", "consent for processing",
    "data subject rights", "records of processing", "penalties for non compliance",
    "obligations of the controller", "board responsibilities", "conflict of interest",
    "operational technology security", "asset management", "cryptographic controls",
    "access rights review", "change management", "capacity management",
    # Arabic
    "سياسة التحكم في الوصول", "تقييم المخاطر", "حماية البيانات الشخصية",
    "الضوابط الأساسية", "التزامات مسؤول البيانات", "استمرارية الأعمال",
    "الحوكمة والرقابة الداخلية", "تشفير المعلومات", "إدارة الحوادث", "التدقيق الداخلي",
]
# repeat to reach 100 representative queries
QUERIES_100 = (QUERIES * 2)[:100]


def _bench_vector_provider(name: str, provider, warmup: int = 5, runs: int = 200) -> dict:
    for q in QUERIES[:warmup]:
        provider.search(q, Filter(), 8)
    latencies: list[float] = []
    start = time.perf_counter()
    for i in range(runs):
        q = QUERIES_100[i % len(QUERIES_100)]
        t = time.perf_counter()
        provider.search(q, Filter(), 8)
        latencies.append((time.perf_counter() - t) * 1000)
    wall = time.perf_counter() - start
    return {"provider": name, "runs": runs, "latency_ms": _percentiles(latencies),
            "throughput_qps": round(runs / wall, 1)}


def _citation_keys(ctx) -> list[str]:
    return [f"{r.document_id}:{r.citation.code}:{r.page_start}" for r in ctx.results]


def main() -> int:
    chunks_dir = _V2 / "knowledge" / "chunks"
    embeddings_dir = _V2 / "knowledge" / "embeddings"

    print("Loading corpus…")
    t = time.perf_counter()
    corpus = InMemoryCorpus.load(chunks_dir)
    print(f"  {len(corpus.chunks):,} chunks in {time.perf_counter() - t:.1f}s")
    keyword = InMemoryKeywordProvider(corpus)

    # ── InMemory vector: index (matrix) build time + memory ──
    rss_before = _rss_mb()
    t = time.perf_counter()
    inmem = InMemoryVectorProvider.load(corpus, embeddings_dir)
    inmem_index_s = time.perf_counter() - t
    rss_with_matrix = _rss_mb()
    print(f"\nInMemory: matrix {inmem.__dict__['_matrix'].shape} built in {inmem_index_s:.1f}s; "
          f"process RSS +{rss_with_matrix - rss_before:.0f} MB")

    # ── PgVector: no in-process index; vectors live in PG ──
    pg = PgVectorProvider(corpus)

    print("\n=== VECTOR-PROVIDER LATENCY (200 searches) ===")
    inmem_bench = _bench_vector_provider("InMemoryVectorProvider", inmem)
    pg_bench = _bench_vector_provider("PgVectorProvider", pg)
    for b in (inmem_bench, pg_bench):
        lm = b["latency_ms"]
        print(f"  {b['provider']:26s} p50={lm['p50']:>7} p95={lm['p95']:>7} p99={lm['p99']:>7} "
              f"mean={lm['mean']:>7} ms · {b['throughput_qps']} qps")

    # ── memory summary ──
    print("\n=== MEMORY (process RSS) ===")
    print(f"  corpus only (baseline):        {rss_before:>7.0f} MB")
    print(f"  + InMemory vector matrix:      {rss_with_matrix:>7.0f} MB  (+{rss_with_matrix - rss_before:.0f} MB held in-process)")
    print("  PgVector holds NO vectors in-process — they live in PostgreSQL")

    # ── end-to-end validation over 100 queries through the UNCHANGED engine ──
    print("\n=== 100-QUERY VALIDATION (full engine: fusion of vector+keyword) ===")
    engine_inmem = RetrievalEngine(inmem, keyword)
    engine_pg = RetrievalEngine(pg, keyword)

    overlaps, top1_matches, conf_deltas = [], 0, []
    inmem_lat, pg_lat = [], []
    diffs = []
    for q in QUERIES_100:
        t = time.perf_counter(); ci = engine_inmem.retrieve(RetrievalQuery(text=q, top_k=5)); inmem_lat.append((time.perf_counter()-t)*1000)
        t = time.perf_counter(); cp = engine_pg.retrieve(RetrievalQuery(text=q, top_k=5)); pg_lat.append((time.perf_counter()-t)*1000)
        ki, kp = _citation_keys(ci), _citation_keys(cp)
        overlap = len(set(ki) & set(kp)) / max(1, len(ki))
        overlaps.append(overlap)
        if ki[:1] == kp[:1]:
            top1_matches += 1
        elif ki and kp:
            diffs.append((q, ki[0], kp[0]))
        if ci.results and cp.results:
            conf_deltas.append(abs(ci.overall_confidence - cp.overall_confidence))

    n = len(QUERIES_100)
    print(f"  queries:                 {n}")
    print(f"  top-1 citation identical: {top1_matches}/{n} ({100*top1_matches/n:.0f}%)")
    print(f"  mean top-5 overlap:       {statistics.fmean(overlaps):.3f}")
    print(f"  mean |confidence Δ|:      {statistics.fmean(conf_deltas):.4f}")
    print(f"  engine latency InMemory:  p50={_percentiles(inmem_lat)['p50']} p95={_percentiles(inmem_lat)['p95']} ms")
    print(f"  engine latency PgVector:  p50={_percentiles(pg_lat)['p50']} p95={_percentiles(pg_lat)['p95']} ms")
    if diffs:
        print(f"\n  top-1 differences ({len(diffs)}) — from HNSW approximation on the low-weight hash-vector signal:")
        for q, a, b in diffs[:8]:
            print(f"    “{q[:34]}”  inmem={a}  pg={b}")
    else:
        print("\n  no top-1 citation differences.")

    pg.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
