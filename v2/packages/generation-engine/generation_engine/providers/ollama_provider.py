"""The Ollama adapter for the `GenerationProvider` port — local, self-hosted models.

The only module allowed to know the `ollama` SDK exists. The SDK is an optional dependency
(`generation-engine[ollama]`), imported lazily, so the engine and its tests never load it; a
pre-built client can be injected for tests. Ollama runs locally, so there is no API key; the
host comes from the SDK's own environment (`OLLAMA_HOST`) — never taken as plain config here.

Ollama's chat API accepts the standard system+user message list directly, so `messages()` maps
straight through. Its typed `ChatResponse` also supports mapping access, so this adapter reads
fields through a small attribute-or-key accessor to work across SDK versions. Every SDK
exception is translated into the shared domain errors (an `ollama.ResponseError` carries a
`status_code`). No routing, no provider selection — just generation.
"""

from __future__ import annotations

from pipeline_contracts import Answer, GenerationError, LLMRequest

from generation_engine.providers._errors import translate_sdk_error

DEFAULT_MODEL = "llama3.1"
_FALLBACK_MAX_OUTPUT_TOKENS = 1200
_FALLBACK_TEMPERATURE = 0.2
_PROVIDER = "ollama"


class OllamaGenerationProvider:
    """`GenerationProvider` adapter over the Ollama chat API for locally hosted models."""

    def __init__(self, *, model: str = DEFAULT_MODEL, client: object | None = None) -> None:
        self._model = model
        self._client = client if client is not None else self._build_client()

    @property
    def name(self) -> str:
        return _PROVIDER

    @staticmethod
    def _build_client() -> object:
        try:
            import ollama
        except ImportError as exc:  # pragma: no cover - exercised via tests without the SDK
            raise ImportError(
                "OllamaGenerationProvider needs the 'ollama' package. "
                "Install the optional extra: generation-engine[ollama]"
            ) from exc
        return ollama.Client()

    def generate(self, request: LLMRequest) -> Answer:
        params = request.params
        try:
            response = self._client.chat(  # type: ignore[attr-defined]
                model=self._model,
                messages=request.messages(),
                options={
                    "temperature": float(params.get("temperature", _FALLBACK_TEMPERATURE)),
                    "num_predict": int(params.get("max_output_tokens", _FALLBACK_MAX_OUTPUT_TOKENS)),
                },
            )
        except GenerationError:
            raise  # already a domain error (e.g. from a test double)
        except Exception as exc:
            raise translate_sdk_error(exc, provider=_PROVIDER) from exc
        return self._to_answer(response)

    def _to_answer(self, response: object) -> Answer:
        message = _get(response, "message", {})
        prompt_tokens = _get(response, "prompt_eval_count", 0) or 0
        completion_tokens = _get(response, "eval_count", 0) or 0
        return Answer(
            text=_get(message, "content", "") or "",
            provider=self.name,
            model=_get(response, "model", self._model) or self._model,
            finish_reason=_get(response, "done_reason", "") or "",
            usage={
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            },
        )


def _get(obj: object, key: str, default: object) -> object:
    """Read `key` from an object whether it exposes attributes (typed ChatResponse) or is a
    plain mapping (older SDK / injected dict)."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)
