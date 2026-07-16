"""Orchestration across every workflow: structure, ordering, metrics, messages, serialization."""

from __future__ import annotations

import json

import pytest
from decision_engine import Intent, UserRequest
from pipeline_contracts import TenantContext
from prompt_orchestrator import PromptOrchestrator, SegmentKind, SegmentRole
from prompt_orchestrator.models import PromptFamily

from tests.conftest import make_context_package, make_plan

_TENANT = TenantContext(tenant_id="org_acme", principal_id="u1")

ALL_INTENTS = [i.value for i in Intent]
GROUNDED = {"lookup", "explanation", "comparison", "compliance_review", "policy_review",
            "obligation_extraction", "risk_analysis", "gap_assessment", "control_mapping",
            "cross_framework_mapping", "summarization", "document_analysis"}


@pytest.fixture
def orch():
    return PromptOrchestrator()


@pytest.mark.parametrize("intent", ALL_INTENTS)
def test_every_workflow_builds_a_valid_request(orch, intent):
    requires_retrieval = intent in GROUNDED
    ctx = make_context_package() if requires_retrieval else None
    plan = make_plan(intent, requires_retrieval=requires_retrieval)
    req = orch.orchestrate(plan, ctx, UserRequest(tenant=_TENANT, query="access control policy"))

    assert req.valid, f"{intent}: {req.warnings}"
    assert req.workflow == intent
    # the mandatory layers are always present
    assert req.segment(SegmentKind.IDENTITY) is not None
    assert req.segment(SegmentKind.WORKFLOW) is not None
    assert req.segment(SegmentKind.USER_REQUEST) is not None
    assert req.segment(SegmentKind.RESPONSE_CONTRACT) is not None
    assert not req.response_contract.is_empty()


def test_segments_are_in_canonical_order(orch):
    req = orch.orchestrate(make_plan("gap_assessment"), make_context_package(),
                           UserRequest(tenant=_TENANT, query="access control"))
    kinds = [s.kind for s in req.segments]
    expected = [SegmentKind.IDENTITY, SegmentKind.DEVELOPER_INSTRUCTIONS, SegmentKind.WORKFLOW,
                SegmentKind.POLICIES, SegmentKind.CONTEXT, SegmentKind.USER_REQUEST,
                SegmentKind.RESPONSE_CONTRACT]
    assert kinds == expected


def test_messages_fold_into_system_and_user(orch):
    req = orch.orchestrate(make_plan("lookup"), make_context_package(), UserRequest(tenant=_TENANT, query="access control"))
    messages = req.messages()
    assert [m["role"] for m in messages] == ["system", "user"]
    # system carries identity + policies + contract; user carries the context + request
    assert "Rasheed" in messages[0]["content"]
    assert "Expected Response" in messages[0]["content"]
    assert "# Context" in messages[1]["content"]
    assert "# User Request" in messages[1]["content"]


def test_context_and_user_are_user_role(orch):
    req = orch.orchestrate(make_plan("compliance_review"), make_context_package(),
                           UserRequest(tenant=_TENANT, query="assess our access control"))
    assert req.segment(SegmentKind.CONTEXT).role == SegmentRole.USER
    assert req.segment(SegmentKind.USER_REQUEST).role == SegmentRole.USER
    assert req.segment(SegmentKind.IDENTITY).role == SegmentRole.SYSTEM


def test_metrics_are_populated(orch):
    req = orch.orchestrate(make_plan("gap_assessment"), make_context_package(n=4),
                           UserRequest(tenant=_TENANT, query="access control"))
    m = req.metrics
    assert m.segment_count == len(req.segments)
    assert m.estimated_tokens > 0
    assert m.system_tokens > 0
    assert m.context_tokens > 0
    assert m.prompt_chars == sum(len(s.content) for s in req.segments)
    assert m.policies_applied
    assert m.prompt_versions["system"] == "rasheed_system.v1"


def test_conversation_has_no_context_layer(orch):
    req = orch.orchestrate(make_plan("conversation", requires_retrieval=False), None,
                           UserRequest(tenant=_TENANT, query="hello"))
    assert req.segment(SegmentKind.CONTEXT) is None
    assert req.valid


def test_to_dict_is_json_serializable(orch):
    req = orch.orchestrate(make_plan("gap_assessment"), make_context_package(), UserRequest(tenant=_TENANT, query="q"))
    json.dumps(req.to_dict())


def test_unknown_family_warns_but_still_builds(orch):
    req = orch.orchestrate(make_plan("lookup"), make_context_package(),
                           UserRequest(tenant=_TENANT, query="q"), family=PromptFamily.AGENT)
    assert any("not implemented" in w for w in req.warnings)
    assert req.valid  # still a usable answer-style request


def test_document_analysis_notes_attachment(orch):
    req = orch.orchestrate(make_plan("document_analysis", requires_document=True),
                           make_context_package(), UserRequest(tenant=_TENANT, query="analyze this", has_document=True))
    assert "attached document" in req.segment(SegmentKind.USER_REQUEST).content
