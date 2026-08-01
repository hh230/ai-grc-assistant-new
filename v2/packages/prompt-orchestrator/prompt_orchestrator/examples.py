"""Runnable example — show the full layered `LLMRequest` for a couple of requests, so the
seven segments, the citation markers, the response contract, and the provider-neutral
messages are all visible. No LLM is called.

Run: python -m prompt_orchestrator.examples
"""

from __future__ import annotations

from pathlib import Path

from context_builder import ContextBuilder, CorpusParentResolver
from decision_engine import DecisionPlan, UserRequest
from pipeline_contracts import TenantContext

_DEMO_TENANT = TenantContext(tenant_id="demo_org", principal_id="demo_user")
from retrieval_engine import RetrievalEngine, RetrievalQuery
from retrieval_engine.providers.corpus import InMemoryCorpus
from retrieval_engine.providers.inmemory_keyword import InMemoryKeywordProvider
from retrieval_engine.providers.inmemory_vector import InMemoryVectorProvider

from prompt_orchestrator import LLMRequest, PromptOrchestrator

_V2 = Path(__file__).resolve().parents[3]


def _plan(intent: str, language: str = "en") -> DecisionPlan:
    return DecisionPlan(
        intent=intent, workflow=f"{intent}_workflow", requires_retrieval=True,
        requires_document=False, requires_reranker=False, requires_human_gate=False,
        multi_step=False, retrieval_passes=1, context_budget=8000, target_profiles=[],
        confidence=0.85, reason="example", language=language,
    )


def render(req: LLMRequest) -> str:
    out = [
        f"workflow={req.workflow}  language={req.language.value}  valid={req.valid}",
        f"metrics: {req.metrics.to_dict()}",
        f"contract sections: {list(req.response_contract.required_sections)}",
        "",
        "── SEGMENTS (in order) ──",
    ]
    for s in req.segments:
        head = s.content.strip().splitlines()[0] if s.content.strip() else ""
        out.append(f"  [{s.role.value:9s}] {s.kind.value:22s} ~{s.estimated_tokens:>5} tok  «{head[:60]}»")
    out.append("")
    out.append("── PROVIDER-NEUTRAL MESSAGES ──")
    for m in req.messages():
        out.append(f"  {m['role']}: {len(m['content'])} chars")
    return "\n".join(out)


def main() -> int:
    corpus = InMemoryCorpus.load(_V2 / "knowledge" / "chunks")
    rengine = RetrievalEngine(
        InMemoryVectorProvider.load(corpus, _V2 / "knowledge" / "embeddings"),
        InMemoryKeywordProvider(corpus),
    )
    builder = ContextBuilder(parent_resolver=CorpusParentResolver(corpus))
    orch = PromptOrchestrator()

    for query, intent in [("gap assessment for access control", "gap_assessment"),
                          ("قارن بين ISO 27001 و NIST لضبط الوصول", "comparison")]:
        ctx = builder.build(rengine.retrieve(RetrievalQuery(text=query, top_k=15)), workflow=intent, budget=4000)
        req = orch.orchestrate(_plan(intent), ctx, UserRequest(query=query, tenant=_DEMO_TENANT))
        print("\n" + "=" * 96)
        print(f"QUERY: {query}")
        print(render(req))

    # show one full rendered prompt body
    print("\n" + "=" * 96)
    print("FULL SYSTEM MESSAGE (first request):")
    ctx = builder.build(rengine.retrieve(RetrievalQuery(text="gap assessment for access control", top_k=8)),
                        workflow="gap_assessment", budget=3000)
    req = orch.orchestrate(_plan("gap_assessment"), ctx, UserRequest(query="gap assessment for access control", tenant=_DEMO_TENANT))
    print(req.messages()[0]["content"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
