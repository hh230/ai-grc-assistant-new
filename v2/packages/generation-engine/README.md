# generation-engine (V2)

Phase 12. Executes a provider-agnostic `LLMRequest` through the shared **`GenerationProvider`
port** (`pipeline_contracts.generation`), hardening the call with **retry**, **execution
timing**, **metrics**, and a **provider-independent error boundary**. Owns the provider
adapters (OpenAI today).

```
AI Orchestrator
    ↓  calls generate(llm_request)
Generation Engine        retry · timing · metrics · error boundary
    ↓  via the port
GenerationProvider       (pipeline-contracts — the single source of truth)
    ↓  implemented by
OpenAI Adapter           all SDK knowledge + SDK→domain error translation
```

Depends **only** on `pipeline-contracts`. The engine never knows OpenAI, Anthropic, Gemini,
Ollama, or Bedrock exist.

## What the engine adds

- **Retry** — transient domain errors only (`RateLimitError`, `TimeoutError`,
  `ProviderUnavailable`), exponential backoff (`RetryPolicy`, default 3 attempts, 0.5s
  base ×2). `AuthenticationError` / `InvalidRequest` are raised immediately.
- **Error boundary** — adapters translate SDK exceptions into the shared domain errors; any
  exception that escapes untranslated is wrapped in `GenerationError`. Callers never see an
  SDK exception.
- **Metrics** — `GenerationMetrics`: provider, model, attempts, retries, total + per-attempt
  latency, which errors were retried, success. Available via `engine.last_metrics` or an
  injected `metrics_sink`. Token usage stays on `Answer` and stage timing stays in the AI
  Orchestrator — nothing is duplicated.

## What the engine deliberately does NOT do

Choose providers or models, route requests, modify prompts, validate answers, or inject
citations. It executes exactly the `LLMRequest` it receives — the request object reaches the
adapter untouched. Provider routing/fallback, streaming, tool calling, JSON mode, and answer
validation are future phases.

## Usage

```python
from generation_engine import GenerationEngine, OpenAIGenerationProvider, RetryPolicy

engine = GenerationEngine(OpenAIGenerationProvider())      # OPENAI_API_KEY from env
answer = engine.generate(llm_request)                      # an Answer, or a domain error
print(engine.last_metrics.to_dict())
```

`GenerationEngine` itself satisfies the `GenerationProvider` protocol, so it drops straight
into the AI Orchestrator's `generation_provider=` injection point.

The OpenAI SDK is an optional extra (`generation-engine[openai]`), imported lazily; tests
inject fake clients and never load it. The API key is resolved by the SDK from the
environment — never passed as plain config.

## Run tests

```bash
cd v2/packages/generation-engine
uv sync && uv run pytest -q
```
