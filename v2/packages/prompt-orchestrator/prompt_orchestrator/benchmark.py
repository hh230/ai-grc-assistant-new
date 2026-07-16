"""Benchmark — the Prompt Orchestrator over ≥100 real end-to-end requests.

Runs the full V2 chain (retrieval → context → prompt) for a representative query set across
all workflows and languages, then reports orchestration latency, prompt/context token sizes,
policy usage, and validity — the Phase-11 observability contract. No LLM is called.

Run: python -m prompt_orchestrator.benchmark
"""

from __future__ import annotations

import statistics
import time
from collections import Counter
from pathlib import Path

from context_builder import ContextBuilder, CorpusParentResolver
from decision_engine import DecisionPlan, UserRequest
from pipeline_contracts import TenantContext

_DEMO_TENANT = TenantContext(tenant_id="demo_org", principal_id="demo_user")
from retrieval_engine import RetrievalEngine, RetrievalQuery
from retrieval_engine.providers.corpus import InMemoryCorpus
from retrieval_engine.providers.inmemory_keyword import InMemoryKeywordProvider
from retrieval_engine.providers.inmemory_vector import InMemoryVectorProvider

from prompt_orchestrator import PromptOrchestrator

_V2 = Path(__file__).resolve().parents[3]

QUERIES = [
    ("access control policy", "gap_assessment"), ("information security risk assessment", "risk_analysis"),
    ("incident response plan", "lookup"), ("compare ISO 27001 and NIST CSF", "comparison"),
    ("business continuity management", "explanation"), ("data protection and privacy", "compliance_review"),
    ("encryption of data at rest", "lookup"), ("segregation of duties", "policy_review"),
    ("obligations of the data controller", "obligation_extraction"), ("map ISO to NCA ECC", "cross_framework_mapping"),
    ("threat intelligence", "summarization"), ("logging and monitoring", "gap_assessment"),
    ("vulnerability management", "compliance_review"), ("secure software development", "explanation"),
    ("physical security", "lookup"), ("cloud security controls", "control_mapping"),
    ("ما هي متطلبات ضبط الوصول", "lookup"), ("قارن بين NIST و ISO", "comparison"),
    ("حماية البيانات الشخصية", "compliance_review"), ("تقييم مخاطر التشفير", "risk_analysis"),
]
CASES_100 = (QUERIES * 5)[:100]


def make_plan(intent: str) -> DecisionPlan:
    return DecisionPlan(
        intent=intent, workflow=f"{intent}_workflow", requires_retrieval=True,
        requires_document=False, requires_reranker=False, requires_human_gate=False,
        multi_step=False, retrieval_passes=1, context_budget=8000, target_profiles=[],
        confidence=0.8, reason="benchmark",
    )


def main() -> int:
    print("Loading V2 chain…")
    corpus = InMemoryCorpus.load(_V2 / "knowledge" / "chunks")
    rengine = RetrievalEngine(
        InMemoryVectorProvider.load(corpus, _V2 / "knowledge" / "embeddings"),
        InMemoryKeywordProvider(corpus),
    )
    builder = ContextBuilder(parent_resolver=CorpusParentResolver(corpus))
    orch = PromptOrchestrator()
    print(f"  {len(corpus.chunks):,} chunks ready")

    # pre-build contexts so we time only orchestration
    prepared = []
    for query, intent in CASES_100:
        ctx = builder.build(rengine.retrieve(RetrievalQuery(text=query, top_k=20)), workflow=intent, budget=8000)
        prepared.append((query, intent, ctx))

    latencies: list[float] = []
    valid = 0
    tokens: list[int] = []
    context_tokens: list[int] = []
    langs: Counter[str] = Counter()
    policy_counts: Counter[str] = Counter()

    print("\n=== ORCHESTRATING 100 LLMRequests (all workflows × languages) ===")
    for query, intent, ctx in prepared:
        t = time.perf_counter()
        req = orch.orchestrate(make_plan(intent), ctx, UserRequest(query=query, tenant=_DEMO_TENANT))
        latencies.append((time.perf_counter() - t) * 1000)
        valid += 1 if req.valid else 0
        tokens.append(req.metrics.estimated_tokens)
        context_tokens.append(req.metrics.context_tokens)
        langs[req.language.value] += 1
        for p in req.metrics.policies_applied:
            policy_counts[p] += 1

    n = len(prepared)
    s = sorted(latencies)
    print(f"  requests:            {n}")
    print(f"  valid:               {valid}/{n}")
    print(f"  orchestration:       p50={s[n//2]:.3f} p95={s[int(n*0.95)]:.3f} "
          f"mean={statistics.fmean(latencies):.3f} ms · {round(n/(sum(latencies)/1000))} req/s")
    print(f"  prompt tokens:       mean={round(statistics.fmean(tokens))} "
          f"min={min(tokens)} max={max(tokens)}")
    print(f"  context tokens:      mean={round(statistics.fmean(context_tokens))} "
          f"max={max(context_tokens)}")
    print(f"  languages:           {dict(langs)}")
    print("\n=== POLICY USAGE ===")
    for policy, count in policy_counts.most_common():
        print(f"  {policy:22s} {count}/{n}")

    print("\nEvery request is a structured, provider-agnostic LLMRequest — no LLM was called.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
