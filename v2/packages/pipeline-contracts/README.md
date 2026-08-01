# pipeline-contracts

The single shared contract library for the Rasheed V2 AI pipeline.

Every shape that crosses an engine boundary lives here — pure, immutable Python models,
shared enums, and provider-neutral `Protocol` interfaces. Nothing else does:

- **zero infrastructure** — no PostgreSQL, no pgvector, no numpy, no OpenAI, no filesystem
- **zero dependencies** — stdlib `dataclasses` / `enum` / `typing` only (enforced by
  `tests/test_purity.py`)

## Modules

| Module | Contracts |
|---|---|
| `pipeline_contracts.decision` | `UserRequest`, `Intent`, `DecisionPlan` |
| `pipeline_contracts.citations` | **The one canonical home of citation rules**: the `Citation` contract, its formatting (`format_citation`, `build_citation`), its two validity gates (`is_citable` for retrieval, `citation_is_complete` for context), its identities (`citation_key`, `clause_key`), `respan`, and `missing_facets`. No other package defines these — they re-export |
| `pipeline_contracts.retrieval` | `Filter` (alias `RetrievalFilter`), `CorpusChunk`, `ScoredHit`, `FusedHit`, `RetrievedChunk`, `RetrievedContext`, `RetrievalQuery`, `VectorSearchProvider`, `KeywordSearchProvider`; re-exports `Citation` + its helpers from `citations` |
| `pipeline_contracts.context` | `WorkflowPolicy`, `BlockRole`, `role_for_profile`, `OrderingPolicy`, `ContextBlock`, `ContextSection`, `TokenBudget`, `BUDGET_PRESETS`, `BuildMetrics`, `ContextPackage` |
| `pipeline_contracts.llm` | `Language`, `SegmentRole`, `SegmentKind`, `PromptFamily`, `PromptSegment`, `ResponseContract`, `PromptMetrics`, `LLMMessage`, `LLMRequest`, `Answer` |
| `pipeline_contracts.generation` | `GenerationProvider` (the generation port) + the provider-independent error model: `GenerationError`, `AuthenticationError`, `InvalidRequest`, `RateLimitError`, `TimeoutError`, `ProviderUnavailable` |
| `pipeline_contracts.intent_registry` | **The single source of truth for per-intent behaviour**: `IntentSpec` (routing · response contract · workflow template body · ordering/context policy · output profile), `INTENT_REGISTRY`, `spec_for`, `RoutingPolicy`, `OutputProfile`, `ORDERING_POLICIES`. Adding an intent = one `IntentSpec` here (plus its classifier cues in decision-engine). |
| `pipeline_contracts.serialization` | `to_plain`, `dataclass_dict` — the shared to_dict conventions (enum→value, tuple→list, nested models) |

## Not only models

The package started as data shapes, but three of its modules now carry real behaviour — the
rules that must not be allowed to differ between the engines that apply them:

- **`intent_registry`** — one `IntentSpec` per intent: routing, response contract, template
  body, ordering policy, output profile. Every engine reads it; none keeps a private table.
- **`citations`** — the citation rules the platform's grounding claim rests on.
- **`llm.LLMRequest.messages()`** — the fold from the layered, auditable prompt structure to
  the system+user shape a provider accepts.

All of it is covered directly by `tests/` (not only through downstream packages), because a
bug in any of the three propagates to every engine at once.

## Dependency rule

```
pipeline-contracts        (depends on nothing — stdlib only)
      ▲
      │ every engine depends on the contracts, never on another engine's models
      │
decision-engine · retrieval-engine · context-builder ·
prompt-orchestrator · generation-engine · answer-validation · ai-orchestrator
```

Engines re-export these names for backward compatibility (e.g.
`from retrieval_engine import Citation` and `from context_builder.citations import
citation_is_complete` both still work), but the classes and functions are defined here and
identity is shared everywhere.

`event-bus` and `pipeline-tracing` deliberately sit *outside* this rule: they depend on
nothing at all, including the contracts, so the observability layer can never become a
reason for a contract to change.
