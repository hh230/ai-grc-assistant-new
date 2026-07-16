"""Integration: real retrieval → context → prompt, across workflows and languages.

Builds full LLMRequests from real corpus context and asserts the production-quality contract
on each: valid, all citations reach the prompt, every mandatory layer present, contract
enforced. Skips cleanly without artifacts.
"""

from __future__ import annotations

import pytest
from context_builder import ContextBuilder, CorpusParentResolver
from decision_engine import UserRequest
from pipeline_contracts import TenantContext
from prompt_orchestrator import PromptOrchestrator
from prompt_orchestrator.models import SegmentKind
from retrieval_engine import RetrievalQuery

from tests.conftest import make_plan

_TENANT = TenantContext(tenant_id="org_acme", principal_id="u1")

CASES = [
    ("access control policy", "gap_assessment"),
    ("compare ISO 27001 and NIST access control", "comparison"),
    ("assess our compliance with data protection", "compliance_review"),
    ("summarize incident response requirements", "summarization"),
    ("ما هي متطلبات حماية البيانات الشخصية؟", "lookup"),
    ("قارن بين ISO و NIST لإدارة المخاطر", "comparison"),
    ("what obligations does PDPL place on controllers", "obligation_extraction"),
    ("assess risk of weak encryption", "risk_analysis"),
]


@pytest.fixture(scope="session")
def builder(corpus):
    return ContextBuilder(parent_resolver=CorpusParentResolver(corpus))


def test_real_pipeline_produces_valid_grounded_prompts(retrieval_engine, builder):
    orch = PromptOrchestrator()
    for query, intent in CASES:
        ctx = builder.build(retrieval_engine.retrieve(RetrievalQuery(text=query, top_k=20)),
                            workflow=intent, budget=8000)
        req = orch.orchestrate(make_plan(intent), ctx, UserRequest(tenant=_TENANT, query=query))

        assert req.valid, f"[{query!r}] {req.warnings}"
        assert req.segment(SegmentKind.IDENTITY) and req.segment(SegmentKind.WORKFLOW)
        assert req.segment(SegmentKind.RESPONSE_CONTRACT)
        context = req.segment(SegmentKind.CONTEXT).content
        for block in ctx.all_blocks():
            assert block.citation.formatted in context, f"[{query!r}] citation lost"
        assert req.metrics.estimated_tokens > 0
        # messages are provider-neutral system + user
        assert [m["role"] for m in req.messages()] == ["system", "user"]


def test_prompt_tokens_track_context_size(retrieval_engine, builder):
    orch = PromptOrchestrator()
    ctx_small = builder.build(retrieval_engine.retrieve(RetrievalQuery(text="risk assessment", top_k=40)),
                              workflow="gap_assessment", budget=2000)
    ctx_large = builder.build(retrieval_engine.retrieve(RetrievalQuery(text="risk assessment", top_k=40)),
                              workflow="gap_assessment", budget=16000)
    small = orch.orchestrate(make_plan("gap_assessment"), ctx_small, UserRequest(tenant=_TENANT, query="risk assessment"))
    large = orch.orchestrate(make_plan("gap_assessment"), ctx_large, UserRequest(tenant=_TENANT, query="risk assessment"))
    assert large.metrics.context_tokens >= small.metrics.context_tokens
    assert large.valid and small.valid
