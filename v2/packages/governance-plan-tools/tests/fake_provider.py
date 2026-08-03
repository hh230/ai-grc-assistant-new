"""A deterministic `GenerationProvider` test double — no live LLM call, no network. Returns
canned, correctly-shaped text so the drafting tool's parsing/orchestration logic is exercised
without depending on (or paying for) a real model."""

from __future__ import annotations

from pipeline_contracts import Answer, LLMRequest


class FakeGenerationProvider:
    name = "fake"

    def __init__(self, *, fail: bool = False) -> None:
        self._fail = fail
        self.requests: list[LLMRequest] = []

    def generate(self, request: LLMRequest) -> Answer:
        self.requests.append(request)
        if self._fail:
            from pipeline_contracts import ProviderUnavailable

            raise ProviderUnavailable("fake provider configured to fail", provider="fake")
        prompt = request.segments[-1].content
        if "RATIONALE:" in prompt or "OBJECTIVE:" in prompt:
            text = (
                "RATIONALE: This was identified from the facts you shared.\n"
                "OBJECTIVE: Close the identified gap.\n"
                "EXPECTED_OUTCOME: The gap is closed and tracked going forward.\n"
                "RISK_IF_SKIPPED: The underlying exposure continues unmanaged."
            )
        elif "DESCRIPTION:" in prompt:
            text = (
                "DESCRIPTION: A specific control is not yet in place.\n"
                "IMPACT: This could delay detection of a real issue."
            )
        else:
            text = "Your organization shows an early-stage governance structure. Focus first on ownership and accountability."
        return Answer(text=text, provider=self.name, model="fake-model")
