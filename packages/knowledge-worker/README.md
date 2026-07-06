# grc-knowledge-worker

The Autonomous Learning Loop (Knowledge Intelligence KI-P4, ADR-0028): the "Scheduler" and
"repeat" links the requested loop was missing —

```
Scheduler -> Ontology -> Question Generator -> Gap Detector -> Research Coordinator ->
Trusted Sources -> Knowledge Repository -> repeat
```

Every other link already existed before this phase and is reused unmodified:

- **Ontology / Question Generator** — `grc_knowledge_ontology.generate_ontology_questions`
  (KI-P3) plus KI-P1's hand-curated `/knowledge-catalog`. This package's own
  `question_sources.combine_question_sources` only merges the two into one question set,
  defensively checking for an id collision between them.
- **Gap Detector / Research Coordinator / Trusted Sources / Knowledge Repository** —
  `grc_knowledge_research_adapters.KnowledgeGapResearchRunner` (KI-P2), already implementing
  "detect gaps against the stored knowledge base, research each via the curated trusted-source
  catalog, store every grounded result" end to end, fail-safe per question. This package
  depends on it only *structurally* (`GapResearchRunnerPort`, matching `.run()` exactly) —
  never by import — so `grc_knowledge_worker` stays as dependency-free as
  `grc_knowledge_research` itself.

What this phase actually adds:

- `scheduler.LearningCycleScheduler` — a pure, fixed-interval "is a new discovery cycle due"
  decision, deliberately distinct from `grc_knowledge_intelligence.gap_detection`'s own
  per-question staleness check (that asks "is *this answer* stale"; this asks "has it been
  long enough since the worker last looked at anything at all").
- `worker.AutonomousKnowledgeWorker` — ties the scheduler and the injected
  `GapResearchRunnerPort` together: `tick(now=...)` runs one scheduling decision (skip, or
  research every actionable gap and advance `last_run_at`); `run_loop(...)` repeats `tick` a
  bounded number of times with an injected clock and sleep function, for deterministic,
  fully-testable "repeat" behavior with no real time passing.

**No I/O of its own.** The clock, the sleep function, and the runner are all injected — this
package never touches a database, an LLM SDK, or the network, and has no third-party
dependencies beyond `grc-knowledge-intelligence` and `grc-knowledge-ontology` (both
dependency-free themselves).

**Not in this package:** the real, always-on process. Wiring a real Postgres-backed
`KnowledgeItemRepository`, a real `LlmKnowledgeExtractor` behind the Tool Registry, a real
`HttpResearchCrawler`, and an actual infinite loop with OS signal handling is a deployment
composition-root concern — see `apps/worker/src/grc_worker/knowledge_learning_loop.py` and
ADR-0028's Consequences.
