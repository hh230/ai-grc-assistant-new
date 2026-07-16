# ADR 0036: Rasheed V2 — the Context Builder as a deterministic stage between retrieval and generation

- Status: Accepted — implemented (Phase 10)
- Date: 2026-07-14
- Deciders: Product Owner (via direct working session), Architecture
- Related: CLAUDE.md §3, §6, §12, §19; ADR 0035; architecture docs
  [context-builder](../../v2/docs/architecture/context-builder.md),
  [retrieval-engine](../../v2/docs/architecture/retrieval-engine.md),
  [decision-engine](../../v2/docs/architecture/decision-engine.md)

## Context

The V2 read path now produces high-quality, cited retrieval (Retrieval Engine, Phase 9A; the
pgvector backend, Phase 9B). The next capability is grounded generation. Before wiring in any
LLM, there is a distinct, deterministic responsibility that must not live inside a prompt:
turning a `RetrievedContext` — a ranked list of cited chunks — into *good context*.

Handed raw to a model, retrieval output duplicates passages, strips the heading a sub-clause
needs, interleaves evidence with requirements in retrieval order, and spends an unbounded
number of tokens. These are the last properties we can *guarantee* (no duplicates, every
citation intact, within budget) before a probabilistic model touches the text. Embedding that
logic in prompt engineering would make it untestable, non-reproducible, and impossible to
audit — the opposite of what a regulated GRC platform requires (CLAUDE.md §19).

## Decision

We introduce a **Context Builder** as its own stage and package (`v2/packages/context-builder/`),
sitting strictly between retrieval and the future generation phase. Its contract is
`RetrievedContext → ContextPackage`, and it owns exactly four concerns: **quality, structure,
ordering, and token budgeting**. It does not prompt, call an LLM, generate answers, do RAG, or
detect hallucinations.

Key decisions:

1. **Structured output, never a string.** `ContextPackage → ContextSection → ContextBlock →
   Citation`. The `Citation` is the Retrieval Engine's own object carried through untouched, so
   citation preservation is structural, not a copy that can drift.
2. **A deterministic pipeline of small, independently tested stages:** deduplicate (chunk_id ·
   checksum · similarity) → merge adjacent → expand parents → order + section → enforce budget
   → validate.
3. **Workflow-aware strategies.** The Decision Engine's intent selects the context strategy —
   evidence-first for compliance, requirement-first for gap, policy-then-regulation for policy
   review, two balanced sides for comparison, smallest for lookup, attachment-only for document
   analysis.
4. **Guarantees are enforced, not hoped for.** A validator rejects any package that exceeds
   budget, loses a citation, contains a duplicate, or has an empty section.
5. **Dependency inversion.** Parent expansion and token counting sit behind ports
   (`ParentResolver`, `TokenCounter`); the in-memory/heuristic adapters are swappable for
   SQL/pgvector and a real tokenizer with no change to the builder.

## Consequences

- The boundary between deterministic context preparation and probabilistic generation is
  explicit and testable: 100 real retrieval outputs build into valid packages across all
  workflows and budget presets (2k–32k), p50 ~2.7 ms, none over budget.
- Trimming keeps whole blocks (never truncates a chunk mid-citation), so every surviving block
  remains exactly citable.
- The generation phase inherits a clean allow-list of cited blocks to ground on and to reject
  hallucinated citations against — but that logic is out of scope here, by design.
- Adds one intra-V2 path dependency (context-builder → retrieval-engine) to reuse
  `RetrievedContext`/`Citation`; V1 is untouched.
