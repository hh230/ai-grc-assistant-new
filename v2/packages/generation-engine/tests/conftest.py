"""Shared builders: a minimal LLMRequest and provider doubles (scripted success/failure
sequences) so no test ever touches an SDK or a network."""

from __future__ import annotations

from pipeline_contracts import (
    Answer,
    Language,
    LLMRequest,
    PromptFamily,
    PromptSegment,
    ResponseContract,
    SegmentKind,
    SegmentRole,
)


def make_request(**params) -> LLMRequest:
    return LLMRequest(
        family=PromptFamily.ANSWER,
        workflow="lookup",
        language=Language.ENGLISH,
        segments=[
            PromptSegment(role=SegmentRole.SYSTEM, kind=SegmentKind.IDENTITY,
                          title="System", content="You are Rasheed."),
            PromptSegment(role=SegmentRole.USER, kind=SegmentKind.USER_REQUEST,
                          title="Request", content="What is PDPL?"),
        ],
        response_contract=ResponseContract(
            workflow="lookup", required_sections=(), required_citations=True,
            citation_style="numeric", required_formatting=(), required_confidence=True,
            forbidden_outputs=(),
        ),
        params=params,
    )


ANSWER = Answer(text="PDPL is the Saudi data protection law.", provider="scripted",
                model="fake-1", finish_reason="stop",
                usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})


class ScriptedProvider:
    """A `GenerationProvider` double that raises/returns each scripted outcome in turn and
    records every request it receives."""

    def __init__(self, *outcomes: object, name: str = "scripted") -> None:
        self._outcomes = list(outcomes)
        self._name = name
        self.requests: list[LLMRequest] = []

    @property
    def name(self) -> str:
        return self._name

    def generate(self, request: LLMRequest) -> Answer:
        self.requests.append(request)
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome  # type: ignore[return-value]
