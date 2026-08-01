"""The Anthropic (Claude) adapter for the `GenerationProvider` port.

The only module allowed to know the `anthropic` SDK exists. The SDK is an optional dependency
(`generation-engine[claude]`), imported lazily, so the engine and its tests never load it; a
pre-built client can be injected, which is how tests exercise the adapter without the SDK or a
network. The API key is resolved by the SDK from the environment (`ANTHROPIC_API_KEY`) — never
taken as plain config here.

Anthropic's Messages API takes the system prompt as a top-level `system` argument (not a chat
turn), so this adapter lifts the request's folded system content out of `messages()` and passes
the remaining user turn(s) through. Every SDK exception is translated into the shared domain
errors before it leaves this module. This adapter does not route, choose, or compare providers —
it just answers when it is the one wired in.
"""

from __future__ import annotations

from pipeline_contracts import Answer, GenerationError, LLMRequest

from generation_engine.providers._errors import translate_sdk_error

DEFAULT_MODEL = "claude-opus-4-8"
_FALLBACK_MAX_OUTPUT_TOKENS = 1200
_FALLBACK_TEMPERATURE = 0.2
_PROVIDER = "claude"


class ClaudeGenerationProvider:
    """`GenerationProvider` adapter over Anthropic's Messages API. Maps the request's
    provider-neutral system/user fold and `params` onto the SDK call, and maps the response
    back into the shared `Answer` contract."""

    def __init__(self, *, model: str = DEFAULT_MODEL, client: object | None = None) -> None:
        self._model = model
        self._client = client if client is not None else self._build_client()

    @property
    def name(self) -> str:
        return _PROVIDER

    @staticmethod
    def _build_client() -> object:
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - exercised via tests without the SDK
            raise ImportError(
                "ClaudeGenerationProvider needs the 'anthropic' package. "
                "Install the optional extra: generation-engine[claude]"
            ) from exc
        return anthropic.Anthropic()

    def generate(self, request: LLMRequest) -> Answer:
        params = request.params
        messages = request.messages()
        system = next((m["content"] for m in messages if m["role"] == "system"), "")
        turns = [{"role": m["role"], "content": m["content"]} for m in messages if m["role"] != "system"]
        try:
            response = self._client.messages.create(  # type: ignore[attr-defined]
                model=self._model,
                system=system,
                messages=turns,
                temperature=float(params.get("temperature", _FALLBACK_TEMPERATURE)),
                max_tokens=int(params.get("max_output_tokens", _FALLBACK_MAX_OUTPUT_TOKENS)),
            )
        except GenerationError:
            raise  # already a domain error (e.g. from a test double)
        except Exception as exc:
            raise translate_sdk_error(exc, provider=_PROVIDER) from exc
        return self._to_answer(response)

    def _to_answer(self, response: object) -> Answer:
        usage = getattr(response, "usage", None)
        input_tokens = getattr(usage, "input_tokens", 0) or 0
        output_tokens = getattr(usage, "output_tokens", 0) or 0
        return Answer(
            text=_extract_text(response),
            provider=self.name,
            model=getattr(response, "model", self._model),
            finish_reason=getattr(response, "stop_reason", "") or "",
            usage={
                "prompt_tokens": input_tokens,
                "completion_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
            },
        )


def _extract_text(response: object) -> str:
    """Anthropic returns a list of content blocks; concatenate the text blocks."""
    blocks = getattr(response, "content", None) or []
    parts = [getattr(block, "text", "") for block in blocks if getattr(block, "type", "text") == "text"]
    return "".join(parts)
