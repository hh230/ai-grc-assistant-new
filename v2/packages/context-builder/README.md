# context-builder (V2)

Phase 10. Transforms a Retrieval Engine `RetrievedContext` into a clean, structured,
**citation-preserving** `ContextPackage` — the final context a *future* LLM phase will
consume. The Context Builder owns **quality, structure, ordering, and token budgeting**. It
does **not** answer.

**No prompting, no LLM, no AI answers, no RAG, no hallucination detection** — those are the
next phase. Implements [v2/docs/architecture/context-builder.md](../../docs/architecture/context-builder.md).

V2-only, isolated: standalone `uv` project with one path dependency on `retrieval-engine`
(to consume its `RetrievedContext` and reuse its `Citation` verbatim). Does not touch V1.

## The shape (never one big string)

```
ContextPackage
  ├─ ContextSection      workflow-ordered: Requirements / Evidence / Policies / sides / …
  │    └─ ContextBlock   one coherent unit of context (a chunk, a merge, or a parent)
  │         └─ Citation  document · page · heading · clause · code · profile  (carried through)
  ├─ BuildMetrics        chunks in/selected/removed, dupes, expansions, merges, tokens, budget
  └─ TokenBudget + warnings + valid
```

## Usage

```python
from context_builder import ContextBuilder, CorpusParentResolver, WorkflowPolicy

# `parent_resolver` is optional — without it, parent expansion is a no-op.
builder = ContextBuilder(parent_resolver=CorpusParentResolver(corpus))

package = builder.build(
    retrieved_context,                    # a RetrievedContext from the Retrieval Engine
    workflow=WorkflowPolicy.GAP_ASSESSMENT,   # or an intent string, e.g. "compliance_review"
    budget=8000,                          # 2000 / 4000 / 8000 / 16000 / 32000
)

assert package.valid                      # False + reasons in .warnings if it failed validation
for section in package.sections:
    for block in section.blocks:
        print(block.citation.formatted, block.text)
```

## Pipeline

`RetrievedContext` → **normalize** → **deduplicate** (chunk_id · checksum · similarity) →
**merge adjacent** (same doc + heading + clause, consecutive) → **expand parents** (add a
child's heading section, via the `ParentResolver` port) → **order + section** (workflow-aware)
→ **enforce budget** (whole blocks, complete sections) → **validate** → `ContextPackage`.

Each stage is a small, independently tested module (`deduplicate.py`, `merge.py`,
`expansion.py`, `ordering.py`, `budget.py`, `validator.py`, `engine.py`). `citations.py` is a
re-export shim over `pipeline_contracts.citations`, which owns the citation rules
(completeness, identity, respan) for the whole platform — this package applies them, it does
not define them.

## Workflow policies

Different workflows need different context strategies (selected via `WorkflowPolicy`, whose
values match the Decision Engine's intents so `plan.intent` maps straight through):

| Workflow | Strategy |
|---|---|
| `lookup` | smallest context — one section, top few hits |
| `comparison` | balanced context from both sides (two sections, round-robin budget) |
| `compliance_review` | evidence-first ordering |
| `gap_assessment` | requirement-first ordering |
| `policy_review` | policy then regulation |
| `document_analysis` | attachment only |
| `explanation` / `general` | balanced default (requirements → policy → evidence) |

## Run tests, benchmark, examples

```bash
cd v2/packages/context-builder
uv sync
uv run pytest -q                          # unit + 100 real-output integration test
uv run python -m context_builder.benchmark   # build latency, per-stage work, token utilization
uv run python -m context_builder.examples    # render one query under several workflows
```

## Guarantees (enforced by `validate`)

A package is rejected (`valid=False`, reasons in `warnings`) if it exceeds budget, loses a
citation, contains a duplicate, or contains an empty section. An empty package (retrieval
found nothing) is valid-but-empty — a legitimate "insufficient evidence" outcome.

## Dependency inversion

The builder depends on **ports**, never on storage:
- `ParentResolver` — resolves a child's parent heading; `CorpusParentResolver` is the
  in-memory adapter, and a pgvector/SQL adapter can replace it with no builder change.
- `TokenCounter` — token estimation; the default is a dependency-free heuristic, swappable
  for a real tokenizer later.

## Not in this phase

No prompting, no LLM, no answer generation, no RAG, no hallucination detection. The builder
prepares context; a later phase grounds an answer on it.
