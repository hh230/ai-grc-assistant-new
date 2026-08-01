"""`LLMTool` — a real, read-only GRC tool that turns a prompt into generated text by **wrapping the
frozen generation stack**. It re-implements nothing and imports no SDK: it builds a
provider-agnostic `LLMRequest` from the step instruction and calls an **injected
`GenerationProvider`** — a `generation-engine` adapter (Claude / Gemini / Ollama / OpenAI) or the
`GenerationEngine` that wraps one (adding retry / metrics / error translation). The composition root
injects the provider; the tool depends only on the pure `GenerationProvider` port.

Unlike the Pipeline Tool (grounded RAG — retrieve then generate), this is **raw generation** for
generative GRC tasks (drafting, summarizing, rewriting) where a capability supplies its own context.
It carries no citations (nothing was retrieved) — `source_ids` is empty by design. A
`GenerationError` from the provider becomes a fail-safe `ok=False`; the SDK exception never crosses
the tool boundary.
"""

from __future__ import annotations

from pipeline_contracts import (
    GenerationError,
    GenerationProvider,
    Language,
    LLMRequest,
    PromptFamily,
    PromptSegment,
    ResponseContract,
    SegmentKind,
    SegmentRole,
    TenantContext,
)
from tool_registry import (
    PAYLOAD_INSTRUCTION,
    PAYLOAD_PRIOR_CONTEXT,
    SideEffectProfile,
    ToolSpec,
    ToolStepResult,
)

GENERATE_TEXT_TOOL = "generate_text"

# A raw-generation tool imposes no response contract — the capability's prompt shapes the output.
_NO_CONTRACT = ResponseContract(
    workflow="llm_tool",
    required_sections=(),
    required_citations=False,
    citation_style="",
    required_formatting=(),
    required_confidence=False,
    forbidden_outputs=(),
)


class LLMTool:
    """A registered `Tool` that generates text through an injected `GenerationProvider`."""

    def __init__(
        self,
        provider: GenerationProvider,
        *,
        name: str = GENERATE_TEXT_TOOL,
        system_prompt: str = "",
        language: Language = Language.ENGLISH,
        temperature: float = 0.2,
        max_output_tokens: int = 1200,
        version: int = 1,
    ) -> None:
        self._provider = provider
        self._system_prompt = system_prompt
        self._language = language
        self._temperature = temperature
        self._max_output_tokens = max_output_tokens
        self._spec = ToolSpec(
            name=name,
            version=version,
            description="Generate text from a prompt via the LLM provider (raw, uncited).",
            side_effect=SideEffectProfile.READ_ONLY,
        )

    @property
    def spec(self) -> ToolSpec:
        return self._spec

    def invoke(self, payload: dict[str, object], tenant: TenantContext) -> dict[str, object]:
        prompt = str(payload.get(PAYLOAD_INSTRUCTION, "")).strip()
        if not prompt:
            return _fail("no prompt given")
        # ADR 0051: when this step follows others, synthesise *from* their rendered output.
        prior_context = str(payload.get(PAYLOAD_PRIOR_CONTEXT, "")).strip()
        try:
            answer = self._provider.generate(self._build_request(prompt, prior_context))
        except GenerationError as exc:
            return _fail(f"generation failed: {exc}")
        return ToolStepResult(
            ok=True, output=answer.text, warnings=tuple(answer.warnings)
        ).as_payload()

    def _build_request(self, prompt: str, prior_context: str = "") -> LLMRequest:
        segments = []
        if self._system_prompt:
            segments.append(
                PromptSegment(
                    role=SegmentRole.SYSTEM,
                    kind=SegmentKind.IDENTITY,
                    title="System",
                    content=self._system_prompt,
                )
            )
        if prior_context:
            # A developer-role context block carrying the prior steps' output the task builds on.
            segments.append(
                PromptSegment(
                    role=SegmentRole.DEVELOPER,
                    kind=SegmentKind.CONTEXT,
                    title="Prior step results",
                    content=prior_context,
                )
            )
        segments.append(
            PromptSegment(
                role=SegmentRole.USER,
                kind=SegmentKind.USER_REQUEST,
                title="Request",
                content=prompt,
            )
        )
        return LLMRequest(
            family=PromptFamily.TOOL,
            workflow="llm_tool",
            language=self._language,
            segments=segments,
            response_contract=_NO_CONTRACT,
            params={
                "temperature": self._temperature,
                "max_output_tokens": self._max_output_tokens,
            },
        )


def _fail(reason: str) -> dict[str, object]:
    return ToolStepResult(ok=False, output="", warnings=(reason,)).as_payload()
