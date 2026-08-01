"""The LLM tool: it builds a correct provider-agnostic request, generates text, threads a system
prompt, works through the real GenerationEngine, and fails safe on a provider error."""

from __future__ import annotations

from generation_engine import GenerationEngine
from llm_tools import GENERATE_TEXT_TOOL, LLMTool
from pipeline_contracts import PromptFamily, SegmentKind, SegmentRole, TenantContext
from tool_registry import (
    PAYLOAD_INSTRUCTION,
    PAYLOAD_PRIOR_CONTEXT,
    SideEffectProfile,
    Tool,
    ToolStepResult,
)


def _generate(tool: LLMTool, tenant: TenantContext, prompt: str) -> ToolStepResult:
    return ToolStepResult.from_payload(tool.invoke({PAYLOAD_INSTRUCTION: prompt}, tenant))


def test_it_is_a_read_only_registry_tool(provider) -> None:
    tool = LLMTool(provider)
    assert isinstance(tool, Tool)
    assert tool.spec.name == GENERATE_TEXT_TOOL
    assert tool.spec.side_effect is SideEffectProfile.READ_ONLY


def test_generates_text_from_the_prompt(provider, tenant) -> None:
    result = _generate(LLMTool(provider), tenant, "summarize the access policy")
    assert result.ok
    assert result.output == "draft: summarize the access policy"
    assert result.source_ids == ()          # raw generation carries no citations, by design


def test_builds_a_tool_family_request_with_the_prompt_as_the_user_message(provider, tenant) -> None:
    _generate(LLMTool(provider), tenant, "write a retention policy")
    request = provider.last_request
    assert request is not None
    assert request.family is PromptFamily.TOOL
    user = [s for s in request.segments if s.role is SegmentRole.USER]
    assert len(user) == 1 and user[0].content == "write a retention policy"
    assert request.params["temperature"] == 0.2


def test_system_prompt_is_threaded_as_a_system_segment(provider, tenant) -> None:
    tool = LLMTool(provider, system_prompt="You are a GRC policy author.")
    _generate(tool, tenant, "draft")
    request = provider.last_request
    system = [s for s in request.segments if s.role is SegmentRole.SYSTEM]
    assert len(system) == 1 and "GRC policy author" in system[0].content


def test_works_through_the_real_generation_engine(provider, tenant) -> None:
    # The engine satisfies GenerationProvider too — the tool wraps it transparently (retry/metrics).
    engine = GenerationEngine(provider)
    result = _generate(LLMTool(engine), tenant, "draft a policy")
    assert result.ok
    assert result.output == "draft: draft a policy"
    assert engine.last_metrics is not None and engine.last_metrics.succeeded


def test_prior_step_context_is_threaded_into_the_prompt(provider, tenant) -> None:
    # ADR 0051: a synthesis step generates *from* the prior steps' rendered output.
    tool = LLMTool(provider)
    tool.invoke(
        {
            PAYLOAD_INSTRUCTION: "write the risk report",
            PAYLOAD_PRIOR_CONTEXT: "[Step 1]\nThe risk of vendor X is HIGH.",
        },
        tenant,
    )
    request = provider.last_request
    context = [s for s in request.segments if s.kind is SegmentKind.CONTEXT]
    assert len(context) == 1
    assert "risk of vendor X is HIGH" in context[0].content
    assert context[0].role is SegmentRole.DEVELOPER


def test_no_prior_context_means_no_context_segment(provider, tenant) -> None:
    tool = LLMTool(provider)
    tool.invoke({PAYLOAD_INSTRUCTION: "draft"}, tenant)   # no prior context key
    request = provider.last_request
    assert not any(s.kind is SegmentKind.CONTEXT for s in request.segments)


def test_empty_prompt_fails_safe(provider, tenant) -> None:
    result = _generate(LLMTool(provider), tenant, "   ")
    assert result.ok is False
    assert "no prompt" in result.warnings[0]


def test_a_provider_error_is_a_fail_safe_not_a_crash(failing_provider, tenant) -> None:
    result = _generate(LLMTool(failing_provider), tenant, "draft")
    assert result.ok is False
    assert "generation failed" in result.warnings[0]
