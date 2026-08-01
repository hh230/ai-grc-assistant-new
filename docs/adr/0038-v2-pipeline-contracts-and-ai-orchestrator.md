# ADR 0038: Rasheed V2 — pipeline-contracts as the shared contract library, ai-orchestrator as the composition root

- Status: Accepted — implemented (Phase 12)
- Date: 2026-07-14
- Deciders: Product Owner (via approved Architecture Review), Architecture
- Related: CLAUDE.md §3, §5, §6, §7, §16, §19; ADR 0035, 0036, 0037; architecture docs
  [decision-engine](../../v2/docs/architecture/decision-engine.md),
  [retrieval-engine](../../v2/docs/architecture/retrieval-engine.md),
  [context-builder](../../v2/docs/architecture/context-builder.md),
  [prompt-orchestrator](../../v2/docs/architecture/prompt-orchestrator.md)

## Context

Two architecture-review findings, both approved for implementation:

1. **Shared contracts lived inside engines.** `context-builder` imported `Citation` /
   `RetrievedContext` from `retrieval-engine`, and `prompt-orchestrator` imported models
   from both `decision-engine` and `context-builder`. Cross-engine model imports meant a
   pure structuring library transitively depended on numpy, pgvector, and psycopg, and
   any engine swap risked rippling through unrelated packages.
2. **There was no composition root.** Each phase's engine existed in isolation; nothing
   owned the end-to-end flow, and the first LLM wiring risked landing ad hoc inside a
   handler — against CLAUDE.md §7 (the Orchestrator is the brain, providers are
   swappable).

## Decision

**`pipeline-contracts`** is the single shared contract library for the AI pipeline: pure,
immutable models, shared enums, and provider-neutral `Protocol` interfaces only — zero
infrastructure (no PostgreSQL, pgvector, numpy, OpenAI, or filesystem code; enforced by a
purity test). Every engine depends on it; it depends on nothing. Contract classes moved
(not copied) there; the old module paths remain as re-export shims, so class identity is
shared and no existing import breaks.

**`ai-orchestrator`** is the composition root and single entry point:
`UserRequest → DecisionEngine → (RetrievalEngine when the plan requires it) →
ContextBuilder → PromptOrchestrator → GenerationProvider → Answer`. It owns only
coordination: sequencing, dependency injection, wiring, execution flow, metrics, tracing,
error propagation, cancellation, and the future event / human-approval hooks. Generation
sits behind the `GenerationProvider` protocol; `OpenAIGenerationProvider` is the first
adapter (SDK optional, key from environment). Fail-safe: invalid `LLMRequest`s are never
sent; `requires_human_gate` pauses before generation when an approval hook is configured.

Resulting dependency graph (arrows = "depends on"; engine→engine model imports are gone —
`prompt-orchestrator → context-builder` remains only for pure helpers, and dev-only test
dependencies are excluded):

```
ai-orchestrator ─→ decision-engine ─┐
      │ ─→ retrieval-engine ────────┤
      │ ─→ context-builder ─────────┼─→ pipeline-contracts
      │ ─→ prompt-orchestrator ──┬──┤
      │                          └─→ context-builder
      └─────────────────────────────┘
```

## Consequences

- Engines are independently swappable and testable; `context-builder` and
  `prompt-orchestrator` no longer transitively require database/vector dependencies.
- The pipeline has one governed entry point with a full audit record per run
  (`PipelineResult`), aligning with CLAUDE.md §19 before any real LLM is wired in.
- New generation providers (Claude, Gemini, Ollama, Azure OpenAI) are added by
  implementing one protocol — zero orchestrator changes.
- The old model import paths are shims; new code should import contracts from
  `pipeline_contracts` directly.

## Amendment — Phase 12 (2026-07-14): Generation Engine extraction

The generation layer was extracted and hardened, preserving every contract above:

- **`GenerationProvider` moved to `pipeline_contracts.generation`** — the single source of
  truth. The same module owns the provider-independent error model (`GenerationError` base
  with a `retryable` flag; `AuthenticationError`, `InvalidRequest`, `RateLimitError`,
  `TimeoutError`, `ProviderUnavailable`). The contracts package remains pure (stdlib only).
- **New `v2/packages/generation-engine/`** owns `GenerationEngine` (retry with backoff on
  retryable domain errors only, execution timing, attempt-level `GenerationMetrics`, and an
  error-translation guard so no SDK exception ever escapes), plus the provider adapters. The
  OpenAI adapter moved here with all SDK knowledge and now translates SDK errors into the
  domain errors at the boundary. The engine itself satisfies the `GenerationProvider`
  protocol, so it drops into the orchestrator's existing injection point.
- **AI Orchestrator is thinner**: it calls `generate(llm_request)` once — no retry, no
  provider logic, no SDK imports (enforced by tests). `ai_orchestrator.provider` /
  `ai_orchestrator.openai_provider` remain as re-export shims for backward compatibility,
  and the `ai-orchestrator[openai]` extra forwards to `generation-engine[openai]`.
- Dependency direction: `ai-orchestrator → generation-engine → pipeline-contracts`; no
  cycles. `Answer` and `LLMRequest` are reused unchanged — no duplicate models.
