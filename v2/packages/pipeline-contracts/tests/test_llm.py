"""LLM contract behaviour — chiefly `LLMRequest.messages()`, the fold from the layered,
auditable prompt structure down to the system+user shape a provider actually accepts.

That fold is the last thing to touch a prompt before it leaves the platform, so a bug in it
(a dropped layer, a mis-assigned role) silently changes every answer the system gives.
"""

from __future__ import annotations

import json

from pipeline_contracts import (
    Answer,
    Language,
    LLMMessage,
    LLMRequest,
    PromptFamily,
    PromptMetrics,
    PromptSegment,
    ResponseContract,
    SegmentKind,
    SegmentRole,
)

CONTRACT = ResponseContract(
    workflow="lookup",
    required_sections=("Answer", "Citations"),
    required_citations=True,
    citation_style="bracketed markers like [S1]",
    required_formatting=("1–3 concise paragraphs",),
    required_confidence=False,
    forbidden_outputs=("uncited factual GRC claims",),
)


def segment(role: SegmentRole, kind: SegmentKind, content: str) -> PromptSegment:
    return PromptSegment(role=role, kind=kind, title=kind.value, content=content,
                         source=f"{kind.value}.v1")


def make_request(segments: list[PromptSegment] | None = None, **overrides) -> LLMRequest:
    defaults = dict(
        family=PromptFamily.ANSWER,
        workflow="lookup_workflow",
        language=Language.ENGLISH,
        segments=segments if segments is not None else [
            segment(SegmentRole.SYSTEM, SegmentKind.IDENTITY, "You are Rasheed."),
            segment(SegmentRole.DEVELOPER, SegmentKind.DEVELOPER_INSTRUCTIONS, "Route: lookup."),
            segment(SegmentRole.SYSTEM, SegmentKind.WORKFLOW, "TASK — Lookup."),
            segment(SegmentRole.SYSTEM, SegmentKind.POLICIES, "Ground every claim."),
            segment(SegmentRole.USER, SegmentKind.CONTEXT, "[S1] pdpl.pdf — 5-1 — p. 3"),
            segment(SegmentRole.USER, SegmentKind.USER_REQUEST, "What does PDPL require?"),
            segment(SegmentRole.SYSTEM, SegmentKind.RESPONSE_CONTRACT, "Sections: Answer, Citations."),
        ],
        response_contract=CONTRACT,
    )
    defaults.update(overrides)
    return LLMRequest(**defaults)


# ── messages(): the provider fold ─────────────────────────────────────────────
def test_messages_folds_to_exactly_one_system_and_one_user_message():
    messages = make_request().messages()
    assert [m["role"] for m in messages] == ["system", "user"]


def test_system_message_gathers_everything_that_shapes_behaviour():
    """Identity, developer instructions, workflow, policies, and the response contract all
    steer the model — they belong in the system message, in prompt order."""
    system = make_request().messages()[0]["content"]
    assert system == (
        "You are Rasheed.\n\n"
        "Route: lookup.\n\n"
        "TASK — Lookup.\n\n"
        "Ground every claim.\n\n"
        "Sections: Answer, Citations."
    )


def test_user_message_carries_the_task_payload_context_then_request():
    user = make_request().messages()[1]["content"]
    assert user == "[S1] pdpl.pdf — 5-1 — p. 3\n\nWhat does PDPL require?"


def test_no_segment_content_is_lost_in_the_fold():
    request = make_request()
    folded = "\n\n".join(m["content"] for m in request.messages())
    for seg in request.segments:
        assert seg.content in folded


def test_developer_segments_fold_into_the_system_message():
    """`messages()` is the conventional shape; a provider with a real developer role can
    still read `segments` instead — the structure is preserved either way."""
    request = make_request(segments=[
        segment(SegmentRole.DEVELOPER, SegmentKind.DEVELOPER_INSTRUCTIONS, "dev-only"),
        segment(SegmentRole.USER, SegmentKind.USER_REQUEST, "hello"),
    ])
    assert request.messages()[0] == {"role": "system", "content": "dev-only"}


def test_empty_segments_are_skipped_rather_than_padding_the_prompt():
    request = make_request(segments=[
        segment(SegmentRole.SYSTEM, SegmentKind.IDENTITY, "You are Rasheed."),
        segment(SegmentRole.SYSTEM, SegmentKind.POLICIES, ""),
        segment(SegmentRole.USER, SegmentKind.USER_REQUEST, "hi"),
    ])
    assert request.messages()[0]["content"] == "You are Rasheed."


def test_a_request_with_no_system_layer_emits_only_the_user_message():
    request = make_request(segments=[segment(SegmentRole.USER, SegmentKind.USER_REQUEST, "hi")])
    assert request.messages() == [{"role": "user", "content": "hi"}]


def test_the_user_message_is_always_present_even_when_empty():
    """Providers reject a call with no user turn; an empty one is still a turn."""
    request = make_request(segments=[segment(SegmentRole.SYSTEM, SegmentKind.IDENTITY, "sys")])
    assert request.messages()[-1] == {"role": "user", "content": ""}


def test_messages_are_plain_json_serializable_dicts():
    json.dumps(make_request().messages())


# ── typed_messages ────────────────────────────────────────────────────────────
def test_typed_messages_is_the_same_fold_as_value_objects():
    request = make_request()
    typed = request.typed_messages()
    assert all(isinstance(m, LLMMessage) for m in typed)
    assert [m.to_dict() for m in typed] == request.messages()


# ── segment access ────────────────────────────────────────────────────────────
def test_segment_finds_a_layer_by_kind_and_returns_none_when_absent():
    request = make_request()
    assert request.segment(SegmentKind.CONTEXT).content.startswith("[S1]")
    assert request.segment(SegmentKind.CONTEXT).source == "context.v1"
    assert make_request(segments=[]).segment(SegmentKind.CONTEXT) is None


def test_system_prompt_returns_the_identity_layer_or_empty():
    assert make_request().system_prompt() == "You are Rasheed."
    assert make_request(segments=[]).system_prompt() == ""


# ── response contract ─────────────────────────────────────────────────────────
def test_response_contract_is_empty_only_without_sections_and_prohibitions():
    assert not CONTRACT.is_empty()
    empty = ResponseContract(
        workflow="", required_sections=(), required_citations=False, citation_style="",
        required_formatting=(), required_confidence=False, forbidden_outputs=(),
    )
    assert empty.is_empty()


# ── serialization ─────────────────────────────────────────────────────────────
def test_request_serializes_enums_to_values_and_nests_its_models():
    data = make_request().to_dict()
    assert data["family"] == "answer"
    assert data["language"] == "en"
    assert data["segments"][0]["role"] == "system"
    assert data["segments"][0]["kind"] == "identity"
    assert data["response_contract"]["required_sections"] == ["Answer", "Citations"]
    json.dumps(data)


def test_prompt_metrics_records_the_versions_an_audit_replays_from():
    metrics = PromptMetrics(workflow="lookup_workflow", language="en",
                            prompt_versions={"system": "rasheed_system.v1"})
    assert metrics.to_dict()["prompt_versions"] == {"system": "rasheed_system.v1"}


def test_answer_carries_its_provenance_and_serializes():
    answer = Answer(text="Consent must be explicit [S1].", provider="claude", model="opus",
                    finish_reason="stop", usage={"total_tokens": 120})
    data = answer.to_dict()
    assert data["provider"] == "claude"
    assert data["usage"] == {"total_tokens": 120}
    assert data["warnings"] == []
    json.dumps(data)
