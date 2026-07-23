"""The `ControlLibraryTool` as a registered Tool: it speaks the frozen contract, interprets the
step instruction (code / theme / keyword / empty / no-match), and never depends on an LLM."""

from __future__ import annotations

from framework_library import CONTROL_LIBRARY_TOOL, ControlLibraryTool
from tool_registry import PAYLOAD_INSTRUCTION, SideEffectProfile, Tool, ToolStepResult


def _invoke(tool: ControlLibraryTool, tenant, instruction: str) -> ToolStepResult:
    return ToolStepResult.from_payload(tool.invoke({PAYLOAD_INSTRUCTION: instruction}, tenant))


def test_it_is_a_read_only_registry_tool(tool: ControlLibraryTool) -> None:
    assert isinstance(tool, Tool)                       # satisfies the frozen protocol
    assert tool.spec.name == CONTROL_LIBRARY_TOOL
    assert tool.spec.side_effect is SideEffectProfile.READ_ONLY


def test_exact_code_lookup_returns_one_control_with_provenance(tool, tenant) -> None:
    result = _invoke(tool, tenant, "A.8.5")
    assert result.ok
    assert "A.8.5 Secure authentication" in result.output
    assert result.source_ids == ("iso_27001:A.8.5",)   # the matched control id is the provenance
    assert result.confidence is None                    # deterministic lookup, not a probability


def test_theme_lookup_returns_the_whole_theme(tool, tenant) -> None:
    result = _invoke(tool, tenant, "People")
    assert result.source_ids == tuple(f"iso_27001:A.6.{n}" for n in range(1, 9))  # 8 People ctrls


def test_keyword_lookup_matches_titles(tool, tenant) -> None:
    result = _invoke(tool, tenant, "authentication")
    # both "Authentication information" (A.5.17) and "Secure authentication" (A.8.5)
    assert set(result.source_ids) == {"iso_27001:A.5.17", "iso_27001:A.8.5"}


def test_empty_instruction_lists_the_whole_catalog(tool, tenant) -> None:
    result = _invoke(tool, tenant, "")
    assert len(result.source_ids) == 93


def test_no_match_is_a_clean_empty_result_not_a_failure(tool, tenant) -> None:
    result = _invoke(tool, tenant, "zzzz-not-a-control")
    assert result.ok is True                            # a zero-match lookup is valid, not an error
    assert result.source_ids == ()
    assert result.warnings and "no controls matched" in result.warnings[0]
