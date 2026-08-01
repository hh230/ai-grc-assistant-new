# Rasheed V2 — Context Builder Architecture

- Status: **Implemented (Phase 10).** Package: `v2/packages/context-builder/`.
- Date: 2026-07-14
- Companions: [Retrieval Engine](retrieval-engine.md) (produces the `RetrievedContext` this
  consumes), [Decision Engine](decision-engine.md) (its `Intent`/workflow selects the
  strategy), [Knowledge Library](knowledge-library.md), [ADR 0036](../../../docs/adr/0036-v2-context-builder.md).
- Scope boundary: **v2/ only.** Sits *between* retrieval and the (future) generation phase:
  it prepares the final context and stops. It does **not** prompt, call an LLM, generate
  answers, do RAG, or detect hallucinations — those belong to the next phase.

---

## 0. Why a Context Builder at all

Retrieval returns a *ranked list of cited chunks*. That is not yet good context. Handed to a
model raw, it duplicates passages, drops the section heading a sub-clause needs to be
understood, mixes evidence with requirements in retrieval order, and blows an unbounded
number of tokens. The Context Builder is the deterministic stage that turns "good retrieval"
into "good context": **quality, structure, ordering, and token budgeting — nothing else.**

It is the last place we can *guarantee* properties (no duplicates, every citation intact,
within budget) before a probabilistic model touches the text. Those guarantees are enforced,
not hoped for (see §8).

---

## 1. Contract

- **Input:** `RetrievedContext` (from the Retrieval Engine) — query, ranked `RetrievedChunk`s
  each carrying a `Citation`, warnings.
- **Output:** `ContextPackage` — a structured tree, never a single string:

```
ContextPackage
  ├─ ContextSection      (workflow-ordered)
  │    └─ ContextBlock    (one coherent unit: a chunk, a merge, or an expanded parent)
  │         └─ Citation   (document · page · heading · clause · code · profile)
  ├─ BuildMetrics
  └─ TokenBudget + warnings + valid
```

The `Citation` is the Retrieval Engine's own object, carried through untouched — so citation
preservation is structural, not a copy that can drift.

---

## 2. Pipeline

```
RetrievedContext
  → normalize        RetrievedChunk → ContextBlock; derive GRC role; stamp content hash
  → deduplicate      chunk_id · checksum · similarity/containment  (keep highest score)
  → merge adjacent   same document + heading + clause, consecutive pages → one block
  → expand parents   add the child's parent heading section, when useful (ParentResolver)
  → dedup (exact)    final byte-identical guard after merge/expansion
  → order + section  workflow-aware role sectioning + within-section reading order
  → enforce budget   token budget; drop whole blocks; complete sections; balanced for compare
  → validate         reject over-budget / lost-citation / duplicate / empty-section
→ ContextPackage (+ BuildMetrics)
```

Each stage is a separate, unit-tested module. The orchestration (`engine.py::ContextBuilder`)
is stateless.

---

## 3. Deduplication (§ "no duplicated context")

Three signals, cheapest first: **chunk_id** (same hit twice), **checksum** (a hash of the
normalized text — catches the same clause embedded in two documents), and **similarity**
(Jaccard over normalized token shingles, plus containment for a short chunk sitting inside a
longer one). Above threshold they are the same context; the higher-scoring block is kept and
absorbs the loser's provenance. Containment collapses only *within a document* — across
documents a shared passage is two legitimate citations. A final exact-hash pass runs after
merge/expansion, which can reintroduce byte-identical text.

## 4. Parent expansion

A deep sub-clause ("A.5.15.2") is often retrieved without the section it lives under, which
is what makes it interpretable. Expansion pulls in the immediate parent heading — but only
when useful: the child must have a real parent (heading depth ≥ 2), the parent must not
already be present, and the count is capped. Parents are scored just below their child so
real hits always outrank them and the budget trims parents first. **Dependency inversion:**
the builder depends on a `ParentResolver` port; `CorpusParentResolver` is the in-memory
adapter, replaceable by a SQL/pgvector one with no builder change. With no resolver,
expansion is a clean no-op.

## 5. Merge

Adjacent fragments of the same clause are stitched back together when *all* hold: same
document, same heading path, same citation clause, and consecutive (contiguous/overlapping
pages, or an unpaged article). The merge concatenates text (dropping a contained fragment),
widens the page span, and reformats the citation to match. **Never across documents** — that
would fabricate a citation.

## 6. Ordering (§ "never preserve retrieval order blindly")

Two levels. **Section order = workflow priority:** compliance review leads with evidence,
gap assessment with requirements, policy review is policy-then-regulation, comparison splits
into the two sides, lookup collapses to the single smallest context, document analysis is the
attachment only. **Within a section:** retrieval score first, then document hierarchy
(documents grouped, strongest first), then heading path and page — so near-equal hits fall
into natural reading order and an expanded parent sits just above its child.

GRC role is derived from the document profile: `law`/`regulation`/`iso_standard`/
`control_framework` → **requirement**, `corporate_policy` → **policy**,
`contract`/`spreadsheet` → **evidence**, else **general**.

## 7. Budget (§ 2k / 4k / 8k / 16k / 32k)

A configurable token budget, counted behind a `TokenCounter` port (default: a dependency-free
heuristic that leans conservative for mixed Arabic/English, swappable for a real tokenizer).
Trimming **keeps whole blocks** — it drops entire lowest-priority blocks rather than
truncating a chunk mid-sentence (which would corrupt its citation's page/section span),
honouring "prefer complete sections over partial chunks". Sequential fill respects the
workflow's section priority; comparison uses **balanced** round-robin fill so both sides get
even representation instead of the first side consuming the budget.

## 8. Validation (the guarantee)

A `ContextPackage` is rejected (`valid=False`, with concrete reasons in `warnings`) when it
**exceeds budget**, **loses a citation** (a block that no longer resolves to a source + a
locator), **contains duplicates** (same id, or identical text under different ids), or
**contains an empty section**. An empty package (retrieval found nothing) is *valid but
empty* — a legitimate "insufficient evidence" outcome, not a failure.

## 9. Metrics (observability)

Every build emits `BuildMetrics`: chunks in / selected / removed, duplicates removed, parent
expansions, merged chunks, blocks trimmed, sections, token usage, remaining budget.

---

## 10. Measured behaviour (real corpus, 31,793 chunks)

100 real retrieval outputs (top-k 25) built across all workflows × all budget presets:

- **100/100 valid**; no duplicate context; every block citation complete; sections in
  workflow order; **never over budget**.
- Build latency **p50 2.7 ms / p95 6.7 ms**, ~320 packages/s (retrieval excluded).
- Average per package: ~3.6 duplicates removed, ~7 parent expansions, ~1.4 blocks trimmed,
  ~23 blocks selected.
- Token fill: ~70 % at 2k–8k budgets (max 100 %, never exceeded); lower at 16k–32k because
  25 retrieved chunks don't fill that much.

---

## 11. Non-goals (named, not overlooked)

No prompting, no LLM, no answer generation, no RAG, no hallucination detection, no
cross-encoder reranking. The Context Builder prepares context; grounding an answer on it —
and rejecting hallucinated citations against this package's allow-list — is the next phase.

*Living document. Implemented in `v2/packages/context-builder/`; keep them in sync.*
