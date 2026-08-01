# decision-engine (V2)

The first working version of the Decision Engine — the layer that turns a user request
into a structured **DecisionPlan** *before* any retrieval happens. It **decides; it never
executes.**

Implements [v2/docs/architecture/decision-engine.md](../../docs/architecture/decision-engine.md)
at MVP scope: **deterministic rule-based classification only — no LLM, no AI, no retrieval,
no RAG, no database.** Everything is explainable: every plan carries the `reason` and the
`matched_cues` that produced it.

V2-only, fully isolated: standalone `uv` project, zero runtime dependencies (Python
stdlib), its own `.venv`/`uv.lock`, not a member of the repo's root workspace. Does not
touch V1.

## Usage

```python
from decision_engine import DecisionEngine

engine = DecisionEngine()
plan = engine.decide({"query": "Compare ISO 27001 with ECC"})
print(plan.to_dict())
# {'intent': 'comparison', 'workflow': 'comparison_workflow',
#  'requires_retrieval': True, 'retrieval_passes': 2, 'requires_reranker': True,
#  'requires_document': False, 'requires_human_gate': False, 'context_budget': 20,
#  'target_profiles': ['iso_standard', 'control_framework'], 'confidence': 0.88, ...}
```

`decide()` accepts a `UserRequest` or a plain `{"query": ..., "has_document": ...}` dict.

## Run the tests and the demo

```bash
cd v2/packages/decision-engine
uv sync
uv run pytest                              # unit tests
uv run python -m decision_engine.examples  # 35 GRC questions → their DecisionPlans
```

## What it does

- **Classifies** a request (Arabic **and** English) into one of the thirteen GRC classes —
  `lookup`, `explanation`, `comparison`, `compliance_review`, `policy_review`,
  `obligation_extraction`, `risk_analysis`, `gap_assessment`, `control_mapping`,
  `cross_framework_mapping`, `summarization`, `document_analysis`, `conversation` — plus the
  two first-class non-answer outcomes `ambiguous` (GRC topic, no clear task → ask) and
  `unsupported` (out of scope → decline). It never assumes a request is a search.
- **Selects one workflow** per class from a data-driven catalog.
- **Routes**: decides whether retrieval runs, how many passes (scaled by the number of
  subjects for comparisons/mappings), and when to skip it entirely (conversation,
  attachment analysis, out of scope).
- **Plans context budgets** per workflow (tight for lookup, wide/structured for
  compliance & gap).
- **Decomposes** composite requests ("compare X with Y *and* which controls our policy
  misses") into a multi-step plan and folds in each part's passes, budget, and human gate.
- **Gates**: assertive analysis (compliance, gap, risk) carries `requires_human_gate`.

## Structure

```
decision_engine/
  models.py       # Intent enum, UserRequest, DecisionPlan
  rules.py        # AR/EN normalization, framework detection, GRC-vocab / locator / conjunction cues
  intents.py      # per-intent Arabic+English regex patterns with weights (the whole "AI")
  workflows.py    # one Workflow per intent + routing/budget defaults
  classifier.py   # deterministic scoring → Classification (primary, secondaries, confidence, reason)
  planner.py      # Classification → DecisionPlan (routing, budgets, profiles, gates)
  engine.py       # DecisionEngine.decide(request) → DecisionPlan
  examples.py     # runnable 35-question demonstration
```

## Explicitly not in this phase

No retrieval, no vector database, no RAG, no AI generation, no LLM classification, no
database, no execution. The engine classifies and plans; running the plan is a later
phase. This phase is complete when it can correctly classify and plan requests — which the
test suite and the 35-question demo demonstrate.
