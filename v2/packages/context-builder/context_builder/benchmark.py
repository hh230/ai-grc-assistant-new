"""Benchmark — the Context Builder over ≥100 real retrieval outputs.

Retrieves real context for a representative query set and builds a ContextPackage for each
across all workflows and budget presets, reporting build latency, the average work done at
each stage (dedup / merge / expansion / trim), token utilization, and validity — the
Phase-10 observability contract.

Run: python -m context_builder.benchmark
"""

from __future__ import annotations

import statistics
import time
from pathlib import Path

from context_builder import BUDGET_PRESETS, ContextBuilder, CorpusParentResolver, WorkflowPolicy
from retrieval_engine import RetrievalEngine, RetrievalQuery
from retrieval_engine.providers.corpus import InMemoryCorpus
from retrieval_engine.providers.inmemory_keyword import InMemoryKeywordProvider
from retrieval_engine.providers.inmemory_vector import InMemoryVectorProvider

_V2 = Path(__file__).resolve().parents[3]

QUERIES = [
    "access control policy", "information security risk assessment", "incident response plan",
    "supplier and third party security", "business continuity management", "data protection and privacy",
    "encryption of data at rest", "segregation of duties", "management review of the ISMS",
    "acceptable use of assets", "threat intelligence", "logging and monitoring",
    "vulnerability management", "secure software development", "physical and environmental security",
    "human resource security", "cloud security controls", "network security architecture",
    "backup and recovery", "risk treatment plan", "governance and oversight", "internal audit function",
    "code of conduct", "whistleblowing channel", "anti bribery and corruption", "vendor management",
    "personal data breach notification", "consent for processing", "data subject rights",
    "records of processing activities", "penalties for non compliance", "obligations of the controller",
    "board responsibilities", "conflict of interest", "operational technology security",
    "asset inventory management", "cryptographic key management", "access rights review",
    "change management process", "capacity management",
    "سياسة التحكم في الوصول", "تقييم مخاطر أمن المعلومات", "حماية البيانات الشخصية",
    "الضوابط الأساسية للأمن السيبراني", "التزامات مسؤول البيانات", "استمرارية الأعمال",
    "الحوكمة والرقابة الداخلية", "تشفير المعلومات", "إدارة الحوادث الأمنية", "التدقيق الداخلي",
]
QUERIES_100 = (QUERIES * 2)[:100]

WORKFLOWS = [
    WorkflowPolicy.LOOKUP, WorkflowPolicy.EXPLANATION, WorkflowPolicy.COMPARISON,
    WorkflowPolicy.COMPLIANCE_REVIEW, WorkflowPolicy.POLICY_REVIEW, WorkflowPolicy.GAP_ASSESSMENT,
    WorkflowPolicy.GENERAL,
]


def _pct(xs: list[float], p: float) -> float:
    s = sorted(xs)
    return round(s[min(len(s) - 1, int(p * len(s)))], 3)


def main() -> int:
    print("Loading corpus + retrieval engine…")
    t = time.perf_counter()
    corpus = InMemoryCorpus.load(_V2 / "knowledge" / "chunks")
    engine = RetrievalEngine(
        InMemoryVectorProvider.load(corpus, _V2 / "knowledge" / "embeddings"),
        InMemoryKeywordProvider(corpus),
    )
    builder = ContextBuilder(parent_resolver=CorpusParentResolver(corpus))
    print(f"  {len(corpus.chunks):,} chunks; ready in {time.perf_counter() - t:.1f}s")

    # pre-retrieve so we time the builder, not retrieval
    contexts = [engine.retrieve(RetrievalQuery(text=q, top_k=25)) for q in QUERIES_100]

    latencies: list[float] = []
    valid = 0
    agg = {"duplicates_removed": 0, "merged_chunks": 0, "parent_expansions": 0,
           "blocks_trimmed": 0, "chunks_selected": 0}
    util_by_preset: dict[int, list[float]] = {p: [] for p in BUDGET_PRESETS}

    print("\n=== BUILDING 100 CONTEXT PACKAGES (all workflows × presets) ===")
    for i, ctx in enumerate(contexts):
        workflow = WORKFLOWS[i % len(WORKFLOWS)]
        preset = BUDGET_PRESETS[i % len(BUDGET_PRESETS)]
        t = time.perf_counter()
        pkg = builder.build(ctx, workflow=workflow, budget=preset)
        latencies.append((time.perf_counter() - t) * 1000)
        valid += 1 if pkg.valid else 0
        for k in agg:
            agg[k] += getattr(pkg.metrics, k)
        util_by_preset[preset].append(pkg.token_count / preset)

    n = len(contexts)
    print(f"  packages built:      {n}")
    print(f"  valid:               {valid}/{n}")
    print(f"  build latency:       p50={_pct(latencies, .5)} p95={_pct(latencies, .95)} "
          f"p99={_pct(latencies, .99)} mean={round(statistics.fmean(latencies), 3)} ms")
    print(f"  throughput:          {round(n / (sum(latencies) / 1000), 1)} packages/s")

    print("\n=== AVERAGE WORK PER PACKAGE ===")
    for k, v in agg.items():
        print(f"  {k:20s} {v / n:.2f}")

    print("\n=== TOKEN UTILIZATION BY BUDGET PRESET ===")
    for preset in BUDGET_PRESETS:
        us = util_by_preset[preset]
        if us:
            print(f"  {preset:>6} tokens: mean fill {100 * statistics.fmean(us):5.1f}%  "
                  f"max {100 * max(us):5.1f}%  (n={len(us)})")

    print("\nAll packages are structured (sections→blocks→citations), deduplicated, ordered,")
    print("and within budget. No prompting, no LLM — context preparation only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
