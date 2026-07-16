# Rasheed V2 — Architecture docs

Start with the [Platform Overview](platform-overview.md): the dependency graph, the layers,
what each package owns, and — just as important — what V2 deliberately has not built yet.

| Doc | Covers | Status |
|---|---|---|
| [platform-overview](platform-overview.md) | Dependency graph · layers · the run · single sources of truth | Current (Phase 14.5) |
| [knowledge-library](knowledge-library.md) | The knowledge model: sources, versions, documents, the two-library scope | **Design only — not implemented** |
| [chunking-engine](chunking-engine.md) | Parsing and chunking into retrievable units with structure preserved | Implemented (in `knowledge-importer`) |
| [retrieval-engine](retrieval-engine.md) | Hybrid retrieval: planning, fusion, ranking, the citation gate | **Partially implemented** — no tenant scope, no cache, no reranker |
| [context-builder](context-builder.md) | `RetrievedContext` → structured, ordered, budgeted `ContextPackage` | Implemented (Phase 10) |
| [prompt-orchestrator](prompt-orchestrator.md) | The layered, provider-agnostic `LLMRequest` | Implemented (Phase 11) |
| [decision-engine](decision-engine.md) | Classification and routing: `UserRequest` → `DecisionPlan` | Implemented (routing metadata now in `intent_registry`) |
| [platform-hardening](platform-hardening.md) | Answer validation · tracing · event bus & audit trail · provider adapters | Implemented (Phase 13; audit completed in 14.5) |

**These are design documents, and several describe more than was built.** Each doc's status
line now says which parts are real; where they disagree with the code, the code wins and the
doc is the bug. `retrieval-engine.md` in particular specifies a tenant scope predicate, a
cache hierarchy, and a reranker that **do not exist**.

## Governance

Architecturally significant decisions live in [`docs/adr/`](../../../docs/adr/README.md), not
here. These docs describe *how the code works*; the ADRs record *why it was decided*. The V2
sequence is ADR 0035–0040.

The tenancy model ([ADR 0040](../../../docs/adr/0040-v2-tenancy-model.md)) is a contract, not
an implementation: **the V2 pipeline enforces no tenant isolation today.** Read
[platform-overview §5](platform-overview.md#5-what-is-deliberately-absent) before assuming
otherwise.
