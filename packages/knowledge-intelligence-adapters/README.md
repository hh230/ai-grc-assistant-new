# grc-knowledge-intelligence-adapters

The Autonomous Knowledge Engine's concrete, Tool-audited LLM synthesis adapter (Knowledge
Intelligence KI-P1, ADR-0025). Implements `grc_knowledge_intelligence.KnowledgeExtractorPort`
by calling `SynthesizeKnowledgeAnswerTool` *through the Tool Registry*, so every synthesis
call is authorized, validated, and unconditionally audited exactly like any other Tool
invocation (CLAUDE.md §9, §19) — never a raw, unaudited LLM SDK call from business logic
(CLAUDE.md §7). Mirrors `grc_regulatory_intelligence_adapters`'s classifier structure exactly.

```
one KnowledgeQuestion + one trusted SourceExcerpt
  -> SynthesizeKnowledgeAnswerTool (Tool Registry, audited)
  -> the provider-agnostic ChatModel, grounded strictly in the excerpt
  -> KnowledgeAnswer (or KnowledgeExtractionError if the excerpt doesn't address the question)
```

- `prompts.py` — the versioned system/user prompt (CLAUDE.md §22: prompts are versioned
  files, never inline). Instructs the model to answer **using only the given excerpt**, never
  outside knowledge, and to report confidence 0 rather than guess when the excerpt does not
  address the question.
- `synthesis.py` — `SynthesizeKnowledgeAnswerTool` (`synthesize_knowledge_answer.v1`):
  `ToolSideEffect.READ_ONLY` (structurally `requires_approval=False` — it only proposes an
  answer; nothing is persisted here), permission-checked (`Permission("knowledge_intelligence")`).
  The LLM's raw JSON is validated strictly (`_RawSynthesisPayload`) — an empty field or a
  confidence outside `[0, 1]` is rejected before it can ever become a candidate
  `KnowledgeItem`. `LlmKnowledgeExtractor` is the `KnowledgeExtractorPort` adapter that invokes
  the Tool through the Tool Registry; a confidence of exactly `0` (the excerpt does not
  address the question) is translated into `KnowledgeExtractionError`, matching the pure
  engine's "fail safe, never guess" contract.
- `exceptions.py` — `KnowledgeSynthesisRejectedError`: malformed/invalid LLM output, rejected
  before it becomes a candidate answer.

**No hallucinated answers.** The prompt is explicit that the model must ground its answer only
in the given excerpt; a confidence-0 response for an unrelated excerpt is the expected,
correct behavior, not an edge case to work around.

**Not in this package:** any persistence, any `apps/api` HTTP endpoint, and any live
trusted-source fetching — see `grc_knowledge_intelligence`'s README and ADR-0025 for what is
explicit future work.
