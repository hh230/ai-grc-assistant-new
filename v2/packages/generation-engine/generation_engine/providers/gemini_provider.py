"""The Google Gemini adapter for the `GenerationProvider` port.

The only module allowed to know the `google-genai` SDK exists. The SDK is an optional
dependency (`generation-engine[gemini]`), imported lazily, so the engine and its tests never
load it; a pre-built client can be injected for tests. The API key is resolved by the SDK from
the environment (`GEMINI_API_KEY` / `GOOGLE_API_KEY`) — never taken as plain config here.

Gemini takes the system prompt as `config.system_instruction` and the user turn(s) as
`contents`, so this adapter lifts the folded system content out of `messages()` and passes the
user content as the prompt. Every SDK exception is translated into the shared domain errors;
google-genai carries the HTTP status on `.code`, which the shared translator understands. No
routing, no provider selection — just generation.
"""

from __future__ import annotations

from pipeline_contracts import Answer, GenerationError, LLMRequest

from generation_engine.providers._errors import translate_sdk_error

DEFAULT_MODEL = "gemini-2.5-pro"
_FALLBACK_MAX_OUTPUT_TOKENS = 1200
_FALLBACK_TEMPERATURE = 0.2
_PROVIDER = "gemini"


class GeminiGenerationProvider:
    """`GenerationProvider` adapter over the google-genai `models.generate_content` call."""

    def __init__(self, *, model: str = DEFAULT_MODEL, client: object | None = None) -> None:
        self._model = model
        self._client = client if client is not None else self._build_client()

    @property
    def name(self) -> str:
        return _PROVIDER

    @staticmethod
    def _build_client() -> object:
        try:
            from google import genai
        except ImportError as exc:  # pragma: no cover - exercised via tests without the SDK
            raise ImportError(
                "GeminiGenerationProvider needs the 'google-genai' package. "
                "Install the optional extra: generation-engine[gemini]"
            ) from exc
        return genai.Client()

    def generate(self, request: LLMRequest) -> Answer:
        params = request.params
        messages = request.messages()
        system = next((m["content"] for m in messages if m["role"] == "system"), "")
        user = "\n\n".join(m["content"] for m in messages if m["role"] != "system")
        config: dict[str, object] = {
            "temperature": float(params.get("temperature", _FALLBACK_TEMPERATURE)),
            "max_output_tokens": int(params.get("max_output_tokens", _FALLBACK_MAX_OUTPUT_TOKENS)),
        }
        if system:
            config["system_instruction"] = system
        try:
            response = self._client.models.generate_content(  # type: ignore[attr-defined]
                model=self._model,
                contents=user,
                config=config,
            )
        except GenerationError:
            raise  # already a domain error (e.g. from a test double)
        except Exception as exc:
            raise translate_sdk_error(exc, provider=_PROVIDER) from exc
        return self._to_answer(response)

    def _to_answer(self, response: object) -> Answer:
        usage = getattr(response, "usage_metadata", None)
        prompt_tokens = getattr(usage, "prompt_token_count", 0) or 0
        completion_tokens = getattr(usage, "candidates_token_count", 0) or 0
        total_tokens = getattr(usage, "total_token_count", 0) or (prompt_tokens + completion_tokens)
        return Answer(
            text=getattr(response, "text", "") or "",
            provider=self.name,
            model=getattr(response, "model_version", None) or self._model,
            finish_reason=_finish_reason(response),
            usage={
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            },
        )


def _finish_reason(response: object) -> str:
    candidates = getattr(response, "candidates", None) or []
    if not candidates:
        return ""
    reason = getattr(candidates[0], "finish_reason", "")
    # google-genai exposes this as an enum; fall back to its string form.
    return getattr(reason, "name", None) or str(reason or "")
