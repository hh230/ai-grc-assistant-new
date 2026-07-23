"""`ToolStepResult` (ADR 0049): the shared tool-step result contract now lives in `tool-registry`,
the pure package every tool depends on — so a leaf tool speaks it without the LLM stack."""

from tool_registry import ToolStepResult


def test_round_trips_through_the_dict_boundary():
    original = ToolStepResult(
        ok=True, output="93 controls", source_ids=("iso_27001:A.5.1",), confidence=None,
        warnings=("truncated",),
    )
    assert ToolStepResult.from_payload(original.as_payload()) == original


def test_from_payload_degrades_safely_on_a_partial_or_ill_typed_result():
    result = ToolStepResult.from_payload({"output": 123, "source_ids": ["a", 7, "b"]})
    assert result.ok is False          # missing → not ok
    assert result.output == ""         # non-str → empty
    assert result.source_ids == ("a", "b")  # non-str items dropped
    assert result.confidence is None


def test_a_bool_is_never_read_as_a_confidence_float():
    # guard the isinstance(bool) trap: True must not coerce to 1.0
    assert ToolStepResult.from_payload({"ok": True, "confidence": True}).confidence is None


def test_defaults_are_a_clean_empty_read_only_result():
    result = ToolStepResult()
    assert result.ok and result.output == "" and result.source_ids == ()
    assert result.confidence is None and result.warnings == ()
