"""Integration: ≥100 real retrieval outputs → ContextPackage.

Runs the real Retrieval Engine over the real corpus and feeds every result through the
Context Builder across all workflows and all budget presets, asserting the four contract
properties on every single package:

  • no duplicate context (block ids and content hashes unique),
  • citation integrity (every block keeps a complete citation),
  • ordering correctness (sections follow the workflow's role priority),
  • token-budget compliance (never over budget),
  • overall validity.

Skips cleanly when the corpus/embeddings aren't present.
"""

from __future__ import annotations

import pytest

from context_builder import BUDGET_PRESETS, ContextBuilder, CorpusParentResolver, WorkflowPolicy
from context_builder.citations import citation_is_complete
from context_builder.ordering import policy_for
from retrieval_engine import RetrievalQuery

QUERIES = [
    "access control policy", "information security risk assessment", "incident response plan",
    "supplier and third party security", "business continuity management", "data protection and privacy",
    "encryption of data at rest", "segregation of duties", "management review of the ISMS",
    "acceptable use of assets", "threat intelligence", "logging and monitoring",
    "vulnerability management", "secure software development", "physical and environmental security",
    "human resource security", "cloud security controls", "network security architecture",
    "backup and recovery", "risk treatment plan", "governance and oversight",
    "internal audit function", "code of conduct", "whistleblowing channel",
    "anti bribery and corruption", "vendor management lifecycle", "personal data breach notification",
    "consent for processing personal data", "data subject rights", "records of processing activities",
    "penalties for non compliance", "obligations of the data controller", "board responsibilities",
    "conflict of interest", "operational technology security", "asset inventory management",
    "cryptographic key management", "access rights review", "change management process",
    "capacity and performance management",
    # Arabic
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


def _role_order_ok(sections, workflow) -> bool:
    """For role-grouped workflows, the emitted section roles must appear in the policy's
    declared priority order (subsequence). Split/single-section workflows are exempt."""
    policy = policy_for(workflow)
    if policy.split_by_document or policy.single_section:
        return True
    priority = list(policy.role_order)
    emitted = [s.role for s in sections]
    positions = [priority.index(r) for r in emitted if r in priority]
    return positions == sorted(positions)


@pytest.fixture(scope="session")
def builder(corpus):
    return ContextBuilder(parent_resolver=CorpusParentResolver(corpus))


def test_100_real_outputs_satisfy_the_context_contract(retrieval_engine, builder):
    checked = 0
    for i, query in enumerate(QUERIES_100):
        workflow = WORKFLOWS[i % len(WORKFLOWS)]
        budget = BUDGET_PRESETS[i % len(BUDGET_PRESETS)]
        ctx = retrieval_engine.retrieve(RetrievalQuery(text=query, top_k=25))
        pkg = builder.build(ctx, workflow=workflow, budget=budget)

        # validity
        assert pkg.valid, f"[{query!r}/{workflow.value}] invalid: {pkg.warnings}"

        blocks = pkg.all_blocks()
        # no duplicate context
        ids = [b.block_id for b in blocks]
        hashes = [b.content_hash for b in blocks]
        assert len(ids) == len(set(ids)), f"[{query!r}] duplicate block id"
        assert len(hashes) == len(set(hashes)), f"[{query!r}] duplicate content"

        # citation integrity
        assert all(citation_is_complete(b.citation) for b in blocks), f"[{query!r}] lost citation"

        # ordering correctness
        assert _role_order_ok(pkg.sections, workflow), f"[{query!r}/{workflow.value}] section order wrong"

        # budget compliance
        assert pkg.token_count <= budget, f"[{query!r}] over budget {pkg.token_count} > {budget}"
        assert pkg.budget.used_tokens == pkg.token_count

        checked += 1
    assert checked == 100


def test_all_budget_presets_are_respected(retrieval_engine, builder):
    ctx = retrieval_engine.retrieve(RetrievalQuery(text="access control policy", top_k=40))
    for preset in BUDGET_PRESETS:
        pkg = builder.build(ctx, workflow=WorkflowPolicy.GAP_ASSESSMENT, budget=preset)
        assert pkg.token_count <= preset
        assert pkg.valid


def test_tighter_budget_selects_no_more_context(retrieval_engine, builder):
    ctx = retrieval_engine.retrieve(RetrievalQuery(text="risk assessment", top_k=40))
    small = builder.build(ctx, workflow=WorkflowPolicy.GENERAL, budget=2000)
    large = builder.build(ctx, workflow=WorkflowPolicy.GENERAL, budget=16000)
    assert small.metrics.chunks_selected <= large.metrics.chunks_selected
    assert small.token_count <= large.token_count
