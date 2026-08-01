"""Direct validation-gate tests: structural rejections independent of the orchestrator."""

from __future__ import annotations

from prompt_orchestrator.models import (
    Language,
    LLMRequest,
    PromptFamily,
    PromptSegment,
    ResponseContract,
    SegmentKind,
    SegmentRole,
)
from prompt_orchestrator.renderer import render_context
from prompt_orchestrator.validation import validate

from tests.conftest import make_context_package


def _segment(kind, role=SegmentRole.SYSTEM, content="x"):
    return PromptSegment(role=role, kind=kind, title=kind.value, content=content)


def _contract(empty=False):
    if empty:
        return ResponseContract("w", (), False, "", (), False, ())
    return ResponseContract("w", ("Answer",), True, "style", ("md",), False, ("legal advice",))


def _request(segments, contract):
    return LLMRequest(family=PromptFamily.ANSWER, workflow="lookup", language=Language.ENGLISH,
                      segments=segments, response_contract=contract)


def test_valid_minimal_request_passes():
    segments = [_segment(SegmentKind.IDENTITY), _segment(SegmentKind.WORKFLOW),
                _segment(SegmentKind.USER_REQUEST, SegmentRole.USER),
                _segment(SegmentKind.RESPONSE_CONTRACT, SegmentRole.DEVELOPER)]
    result = validate(_request(segments, _contract()), None, None)
    assert result.is_valid


def test_missing_workflow_is_rejected():
    segments = [_segment(SegmentKind.IDENTITY), _segment(SegmentKind.USER_REQUEST, SegmentRole.USER),
                _segment(SegmentKind.RESPONSE_CONTRACT, SegmentRole.DEVELOPER)]
    req = _request(segments, _contract())
    req.workflow = ""
    result = validate(req, None, None)
    assert not result.is_valid and "missing workflow" in result.issues


def test_missing_response_contract_is_rejected():
    segments = [_segment(SegmentKind.IDENTITY), _segment(SegmentKind.WORKFLOW),
                _segment(SegmentKind.USER_REQUEST, SegmentRole.USER)]
    result = validate(_request(segments, _contract(empty=True)), None, None)
    assert not result.is_valid and "missing response contract" in result.issues


def test_context_lost_when_blocks_present_but_no_segment():
    pkg = make_context_package(n=3)
    segments = [_segment(SegmentKind.IDENTITY), _segment(SegmentKind.WORKFLOW),
                _segment(SegmentKind.USER_REQUEST, SegmentRole.USER),
                _segment(SegmentKind.RESPONSE_CONTRACT, SegmentRole.DEVELOPER)]
    # rendered context exists (blocks) but we omitted the CONTEXT segment
    rendered = render_context(pkg)
    result = validate(_request(segments, _contract()), pkg, rendered)
    assert not result.is_valid
    assert any("context lost" in i for i in result.issues)


def test_invalid_package_is_rejected():
    pkg = make_context_package(n=2)
    pkg.valid = False
    segments = [_segment(SegmentKind.IDENTITY), _segment(SegmentKind.WORKFLOW),
                _segment(SegmentKind.CONTEXT, SegmentRole.USER, render_context(pkg).text),
                _segment(SegmentKind.USER_REQUEST, SegmentRole.USER),
                _segment(SegmentKind.RESPONSE_CONTRACT, SegmentRole.DEVELOPER)]
    result = validate(_request(segments, _contract()), pkg, render_context(pkg))
    assert not result.is_valid and "context package is invalid" in result.issues
