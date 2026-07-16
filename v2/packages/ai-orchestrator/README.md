# ai-orchestrator

The **composition root** and single entry point of the Rasheed V2 AI pipeline.

```
UserRequest
  → DecisionEngine        what to do (classification lives there, not here)
  → RetrievalEngine       what we know (only when the plan requires retrieval)
  → ContextBuilder        structure the evidence, citations preserved
  → PromptOrchestrator    the provider-agnostic LLMRequest
  → GenerationEngine      retry · metrics · error boundary (generation-engine package)
      → GenerationProvider   the port (pipeline-contracts)
          → OpenAI Adapter   all SDK knowledge (generation-engine)
→ Answer (inside a fully auditable PipelineResult)
```

## What it owns — and what it doesn't

Owns **only orchestration**: pipeline sequencing, dependency injection, engine wiring,
execution flow, metrics, tracing, error propagation, cancellation, and the future
event / human-approval hooks. It performs no retrieval, builds no prompts, classifies
nothing, and contains no business rules.

## Usage

```python
from ai_orchestrator import AIOrchestrator
from context_builder import ContextBuilder
from decision_engine import DecisionEngine
from generation_engine import GenerationEngine, OpenAIGenerationProvider
from prompt_orchestrator import PromptOrchestrator
from retrieval_engine import RetrievalEngine

orchestrator = AIOrchestrator(
    decision_engine=DecisionEngine(),
    retrieval_engine=RetrievalEngine(vector_provider, keyword_provider),
    context_builder=ContextBuilder(),
    prompt_orchestrator=PromptOrchestrator(),
    # the GenerationEngine satisfies the GenerationProvider port and adds
    # retry, metrics, and the provider-independent error boundary
    generation_provider=GenerationEngine(OpenAIGenerationProvider()),
)

result = orchestrator.run({"query": "Explain the consent requirements under PDPL"})
result.answer.text          # the generated answer
result.metrics.timings_ms   # per-stage timings
result.to_dict()            # the full, auditable record of the run
```

## Generation is a port (Phase 12)

`GenerationProvider` is a `Protocol` owned by **pipeline-contracts** — the single source of
truth both this package and the Generation Engine depend on. The orchestrator never imports
a provider SDK and contains no retry/provider logic; the **generation-engine** package owns
the adapters (OpenAI first), retry, metrics, and the SDK→domain error translation — the
orchestrator only ever sees the shared domain errors (`RateLimitError`,
`ProviderUnavailable`, …), never an SDK exception. Adding Claude/Gemini/Ollama/Bedrock means
implementing the protocol in generation-engine and injecting it: **zero orchestrator
changes**. (`ai_orchestrator.GenerationProvider` / `OpenAIGenerationProvider` remain as
backward-compatible re-exports; the SDK extra now forwards to `generation-engine[openai]`.)

## Fail-safe policies

- an `LLMRequest` that failed prompt validation is **never sent** (`INVALID_PROMPT`);
- a plan with `requires_human_gate` **pauses before generation** when an
  `approval_gate` hook is configured (`AWAITING_APPROVAL`);
- retrieval demanded but not wired degrades to the prompt layer's explicit
  insufficient-evidence handling, with a warning — never a silent guess;
- cancellation (`CancellationToken`) is honoured before every stage; generation is the
  only external call and always runs last.
