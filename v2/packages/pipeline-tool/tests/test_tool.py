"""PipelineTool: it is a proper Tool, and it maps a real pipeline run to the tool boundary."""

from pipeline_contracts import TenantContext
from pipeline_tool import RUN_PIPELINE_TOOL, PipelineTool
from tool_registry import SideEffectProfile, Tool


def test_pipeline_tool_is_a_registrable_tool(orchestrator):
    tool = PipelineTool(orchestrator)
    assert isinstance(tool, Tool)  # satisfies the tool-registry Tool protocol
    assert tool.spec.name == RUN_PIPELINE_TOOL
    assert tool.spec.side_effect is SideEffectProfile.READ_ONLY  # answering is read-only


def test_invoke_runs_the_pipeline_and_returns_a_grounded_answer(orchestrator):
    tool = PipelineTool(orchestrator)
    tenant = TenantContext(tenant_id="org_acme", principal_id="u1")
    result = tool.invoke(
        {"instruction": "What are the security controls required for personal data?"}, tenant
    )

    assert result["ok"] is True
    assert "[1]" in str(result["output"])   # the generated answer flowed back
    # grounding flowed through from the real retrieval stage
    assert result["source_ids"]  # non-empty
    assert isinstance(result["confidence"], float)
