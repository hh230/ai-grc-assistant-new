# Architecture Audit — AI GRC Assistant

> **Document status:** Accepted as a **draft** by the Product Owner on 2026-06-27. This is
> the complete, archived audit report. It is **not** itself the official project state — the
> authoritative implementation tracker is [`PROJECT_STATE.md`](../../PROJECT_STATE.md) (the
> Project State Register), and approved architectural decisions are recorded in
> [`ARCHITECTURE_DECISION_LOG.md`](../../ARCHITECTURE_DECISION_LOG.md).

- **Auditor role:** Chief Architecture Auditor (read-only)
- **Audit date:** 2026-06-27
- **Method:** Source-code inspection only. Per Handbook §12.11 ("Evidence First"),
  *"Plans and documentation are not implementation evidence."* No code was modified,
  created, or refactored during the audit.
- **Roadmap reference:** the Handbook's mandatory "Knowledge-First" implementation order
  ([`docs/SOFTWARE_ARCHITECTURE_HANDBOOK.md`](../SOFTWARE_ARCHITECTURE_HANDBOOK.md) §8).

---

## 1. Executive Summary

The repository is a well-structured **Clean / DDD monorepo** whose *implemented* core is
much narrower than its scaffolding suggests. Source evidence shows real, substantial
implementation in exactly four Python packages — **Domain** (~6,990 LOC),
**Application/Services** (~4,093 LOC), **Persistence** (~5,114 LOC), and the **Knowledge
Extraction Engine abstractions** (~738 LOC) — plus a standalone **Next.js presentation
demo** (~3,562 LOC). Every other capability package (`tools`, `agents`, `rag`,
`framework-engine`, `llm`, `events`, `plugins`, `observability`, `security`, `config`) and
every backend app (`api`, `orchestrator`, `worker`, `workflow`) contains only an empty
`__init__.py` (1 LOC each).

The project is being built along the **Handbook's "Knowledge-First" mandatory roadmap**
(`SOFTWARE_ARCHITECTURE_HANDBOOK.md` §8), **not** the layered roadmap described in
`PROJECT_STATE.md` §10. Against the Handbook roadmap, milestones **1–5 are implemented**,
milestone **6 (Knowledge Extraction Engine) is partially implemented** (ports/abstractions
only, zero adapters), and milestones **7–12 are Not Started**.

Three issues dominate the findings:

1. **Severe documentation drift.** `README.md` still claims *"No business logic, APIs,
   database models, or UI pages have been implemented yet"* — false on all four counts.
   `PROJECT_STATE.md` says "13 bounded contexts"; the source has **14**.
2. **"Complete" is not backed by tests.** PROJECT_STATE marked Domain and Application
   layers "✅ complete," but **Services has zero tests** and **12 of 14 domain contexts
   (including the flagship `missions` aggregate) have no unit tests.** Under Evidence-First
   these are *Implemented / Unverified*, not *Completed*.
3. **A real port/adapter contract hole** — the `UnitOfWork` ABC lacks the `missions`
   property its own handlers call.

Nothing here is a crisis; the implemented layers are clean and the dependency direction is
honored. The priority is **governance hygiene**: reconcile the conflicting roadmaps and the
inaccurate PSR before advancing.

---

## 2. Current Architecture Overview

A polyglot monorepo (`pnpm`/`turbo` for TS, `uv` for Python — `pnpm-workspace.yaml`,
`pyproject.toml`).

**Dependency direction (verified, inward-pointing):**

- **Domain** (`packages/domain/grc_domain/`) — pure. Grep for
  `fastapi|sqlalchemy|pydantic|asyncpg|anthropic|openai|alembic` imports → **none**. A
  shared kernel + 14 bounded contexts.
- **Application/Services** (`packages/services/grc_services/`) — CQRS
  (commands/queries/handlers/dtos/service per context); imports Domain only (verified). 14
  capability packages + a shared kernel.
- **Persistence** (`packages/persistence/grc_persistence/`) — SQLAlchemy 2.x async,
  mappers, repositories, `SqlAlchemyUnitOfWork`, transactional outbox, one Alembic
  migration creating **20 tables** (`migrations/versions/0001_initial_schema.py`).
- **Knowledge Extraction Engine** (`packages/extraction/grc_extraction/`) — hexagonal
  **ports only** (10 ABC ports, profiles, registry, artifacts); no concrete adapters.
- **Web** (`apps/web/`) — Next.js App Router dashboard rendering **static compile-time demo
  data** (`apps/web/lib/data.ts` explicitly: *"This is NOT a mock API… no fetch, no route
  handler, no network"*).

**Not yet present in source:** AI Orchestrator, Multi-Agent layer, Tool Registry/Tools,
RAG/retrieval, Framework Engine logic, LLM provider abstraction, event bus/outbox relay,
composition root/DI wiring, API endpoints.

---

## 3. Project State Register (PSR) — Audit Snapshot

Status vocabulary per Handbook §12.14 (Completed / In Progress / Partially Implemented /
Not Started / Unverified), mapped to the **Handbook §8 mandatory roadmap**. The live PSR is
maintained in `PROJECT_STATE.md`; this is the snapshot as observed on the audit date.

| #  | Handbook Milestone            | Status (source-evidenced)      | Primary Evidence |
|----|-------------------------------|--------------------------------|------------------|
| 1  | Shared Kernel                 | **Completed** (no dedicated tests; exercised transitively) | `domain/grc_domain/shared/` |
| 2  | Core Domain                   | **Implemented / Unverified**   | 12 contexts present; **no unit tests** for any |
| 3  | Knowledge Domain              | **Completed**                  | `domain/grc_domain/knowledge/` + `domain/tests/knowledge/` (part of 82 domain test fns) |
| 4  | Knowledge Database            | **Completed**                  | 20 tables in `0001_initial_schema.py`; `tests/test_migration.py` |
| 5  | Knowledge DB Integration      | **Completed**                  | `repositories/`, `mappers/`, `unit_of_work.py`, `outbox.py`; 19 persistence test fns |
| 6  | Knowledge Extraction Engine   | **Partially Implemented**      | `extraction/grc_extraction/ports.py` (10 ABC ports) — abstractions only, **zero adapters, no package tests** |
| 7  | Framework Engine              | **Not Started**                | `packages/framework-engine/` = 1 LOC; `frameworks/nca-ecc/metadata.yaml` `status: placeholder` |
| 8  | Knowledge Graph               | **Not Started**                | No source artifact |
| 9  | Search                        | **Not Started**                | No source artifact |
| 10 | Retrieval                     | **Not Started**                | `packages/rag/retrieval/` empty |
| 11 | RAG                           | **Not Started**                | `packages/rag/` = 1 LOC; no pgvector columns anywhere |
| 12 | AI Agents                     | **Not Started**                | `packages/agents/` = 1 LOC |

**Off-roadmap items present in source (built ahead of / outside the locked order):**

| Item | Status | Evidence |
|------|--------|----------|
| Application/Services layer (all 14 contexts) | **Implemented / Unverified** | `packages/services/grc_services/` (~4,093 LOC); `tests/` is `.gitkeep` — **0 tests** |
| Web presentation demo | **Implemented (prototype)** | `apps/web/` ~3,562 LOC, static data, no backend wiring |

---

## 4. Completed Milestones (with evidence)

**M1 Shared Kernel — Completed.** `domain/grc_domain/shared/` provides
`AggregateRoot`/`Entity` (`entity.py`), value objects, domain events, typed identifiers, and
a base exception hierarchy. Purity verified (no framework imports). *Caveat:* no dedicated
test module; exercised transitively via knowledge/extraction tests.

**M3 Knowledge Domain — Completed.** `domain/grc_domain/knowledge/` is the only core context
with full unit coverage: `domain/tests/knowledge/` (knowledge objects, documents/sections,
relationships, source/version, value objects), part of **82** verified domain test
functions. Aligns with the Handbook "Knowledge-First Principle" (§9).

**M4 Knowledge Database — Completed.** A single Alembic migration builds all 20 tables
(`organizations`, `users`, `workspaces`, `frameworks`, `framework_mapping_sets`, `controls`,
`policies`, `risks`, `assessments`, `evidence`, `knowledge_sources`, `reports`,
`tool_descriptors`, `agent_descriptors`, `plugin_descriptors`, `missions`, `mission_steps`,
`mission_approval_gates`, `audit_records`, `outbox_messages`) —
`migrations/versions/0001_initial_schema.py`. `tests/test_migration.py` verifies
model↔migration parity.

**M5 Knowledge Database Integration — Completed.** Concrete repositories, mappers (the sole
Domain↔ORM seam), `SqlAlchemyUnitOfWork` (`unit_of_work.py:160`), and a transactional outbox
(`outbox.py`). **19** persistence test functions cover tenant isolation
(`test_tenant_isolation.py`), optimistic concurrency (`test_optimistic_concurrency.py`),
diff-based child sync (`test_child_synchronization.py`), the outbox
(`test_transactional_outbox.py`), repository round-trip, and migration parity.

---

## 5. Partially Implemented Milestones (with evidence)

**M2 Core Domain — Implemented but Unverified.** All 12 non-knowledge contexts exist with
entities/enums/events/exceptions/repositories. The `missions` aggregate encodes a real
lifecycle state machine and the human-gate rule (`missions/entities.py`: `_ALLOWED`
transition map, `ApprovalGate`, `is_consequential`). **However, none of these 12 contexts
has a unit test** — the 82 domain test functions cover only `knowledge/` and `extraction/`.
The platform's most safety-critical aggregate (Mission, the human-in-the-loop gate) is
**untested**.

**M6 Knowledge Extraction Engine — Partially Implemented.** `extraction/grc_extraction/`
defines a complete hexagonal port surface (`DocumentAdapterPort`, `OcrPort`,
`NormalizerPort`, `SegmenterPort`, `ClassifierPort`, `ExtractorPort`,
`RelationshipExtractorPort`, `ConfidenceScorerPort`, `FrameworkMappingPort`,
`KnowledgeIngestionPort`) plus profiles/registry/artifacts. The package states it is *"pure
abstraction… concrete adapters implement these ports in outer infrastructure packages."*
**Zero concrete adapters exist** (grep for any class implementing those ports → none), and
the package has **no tests**. Design/contract done; execution not.

**Application/Services layer — Implemented but Unverified (off-roadmap).** Full CQRS across
14 capability packages, but **0 tests** (`packages/services/tests/` is `.gitkeep`),
violating the Definition of Done (CLAUDE.md §24).

---

## 6. Missing Milestones

All **Not Started** (only a 1-LOC `__init__.py` or `.gitkeep` exists):

- **M7 Framework Engine** — `packages/framework-engine/` empty; `frameworks/` has no real
  framework data, only `nca-ecc/metadata.yaml` marked `status: placeholder`.
- **M8 Knowledge Graph** — no artifact in source.
- **M9 Search** — no artifact in source.
- **M10 Retrieval** — `packages/rag/retrieval/` empty.
- **M11 RAG** — `packages/rag/` empty; the `vector` extension is enabled in
  `scripts/db/init/001_extensions.sql` but **no vector/embedding column exists** in any
  model or migration.
- **M12 AI Agents** — `packages/agents/` empty; the whole AI stack (orchestrator, LLM
  provider, tools, agents) is absent.

Also absent and required before any of the above can run: **composition root / DI wiring**
(only referenced as "future" in `persistence/db/engine.py`), **eventing relay**
(`packages/events/` empty), **Tool Registry** (`packages/tools/` empty), and **API
endpoints** (`apps/api/` = 1 LOC).

---

## 7. Architecture Deviations

1. **Two conflicting authoritative roadmaps.** The Handbook mandates a Knowledge-First order
   (`SOFTWARE_ARCHITECTURE_HANDBOOK.md` §8) and declares *"No phase may be skipped."*
   `PROJECT_STATE.md` §10 instead prescribes Eventing relay → Composition root → Tools →
   LLM → RAG → Framework Engine → Orchestrator → API → Web. These orders **disagree on what
   comes next**. Governance deviation against Handbook §12.22 "Roadmap Lock."
2. **Breadth built ahead of the locked order.** The full Application layer for
   non-knowledge contexts was built before milestones 6–11. Handbook §11.35 requires *"No
   future milestone dependencies are introduced"*; §11.36 *"Future roadmap items remain
   untouched."*
3. **`apps/web` is entirely off-roadmap.** A 3,562-LOC dashboard exists, yet UI appears
   nowhere in the Handbook §8 roadmap. It is honestly labeled an "investor demo" with static
   data (`lib/data.ts`), but its existence still deviates from the locked order and from the
   "Workspace-first / Mission-centric" UX pillar (it is a static executive dashboard, not a
   mission workspace).
4. **Port/adapter contract hole.** The application's `UnitOfWork` ABC declares 16 repository
   properties but **not `missions`** (`shared/unit_of_work.py:41-103`), while
   `missions/handlers.py` and nine other call sites use `uow.missions`, and only the
   *concrete* `unit_of_work.py:160` provides it. The interface does not satisfy its own
   consumers — a Liskov/contract violation.

---

## 8. Technical Debt

| Debt | Evidence | Impact |
|------|----------|--------|
| `UnitOfWork` ABC missing `missions` property | `shared/unit_of_work.py` vs `missions/handlers.py` | Likely a `mypy` failure (CI runs `uv run mypy .`); breaks the port abstraction |
| Application layer: **0 tests** | `packages/services/tests/` | "Complete" unverifiable; DoD unmet (CLAUDE.md §24) |
| 12/14 domain contexts untested (incl. `missions`) | `packages/domain/tests/` | Flagship human-gate logic unverified |
| Extraction **engine** package untested | `packages/extraction/` (no test dir) | M6 abstractions unverified |
| No composition root / DI | comments only (`db/engine.py`) | Implemented layers not runnable end-to-end |
| No versioned prompt artifacts | `prompts/` holds only README + CHANGELOG | Fine until AI work; CLAUDE.md §21/22 requires versioned prompt files |
| Framework data is placeholder | `frameworks/nca-ecc/metadata.yaml` | Framework Engine has nothing to load |

---

## 9. Risks

- **Governance (high):** two locked-but-divergent roadmaps make "the next milestone"
  ambiguous; advancing risks skipping a mandated phase.
- **Truth-of-status (high):** documentation asserts "Completed" where tests are absent,
  contradicting Evidence-First (§12.11). Stakeholders would over-estimate readiness.
- **CI integrity (medium):** the `uow.missions` gap should fail `mypy` if CI runs as
  configured. Either CI is red, or type-checking is not catching it — both are problems.
- **Stakeholder perception (medium):** `apps/web` renders concrete-looking compliance scores
  from hardcoded data; without framing, it can be mistaken for working product.
- **RAG-readiness (low/known):** pgvector is enabled but no vector schema exists; the
  Knowledge Database needs a schema migration before M10–M11.

---

## 10. Documentation Drift

| Document | Claim | Source Reality |
|----------|-------|----------------|
| `README.md` | *"No business logic, APIs, database models, or UI pages have been implemented yet."* | **False ×4:** domain/services/persistence implemented; 20 DB tables; UI pages in `apps/web/app/`. Most stale doc. |
| `docs/architecture/PROJECT_SKELETON.md` §15 | *"No business logic… services and domain folders are empty shells."* | False; never updated for the extraction/knowledge build-out |
| `PROJECT_STATE.md` | Domain has **"13 bounded contexts"** | Source has **14** (extraction added) |
| `PROJECT_STATE.md` | `apps/web` = "scaffold only; no logic" | 3,562 LOC of real components |
| `PROJECT_STATE.md` | Does not mention the **Knowledge Extraction Engine** at all | A 738-LOC subsystem + a domain context absent from the PSR |
| `PROJECT_STATE.md` | Domain & Application "✅ complete" | No service tests; 12/14 domain contexts untested → *Unverified* under §12.11 |
| Handbook §8 vs PROJECT_STATE §10 | — | Conflicting mandatory roadmaps |

The Handbook (`SOFTWARE_ARCHITECTURE_HANDBOOK.md`, 31,156 lines, most recently updated) is
internally consistent with the source's *direction* (Knowledge-First); README,
PROJECT_SKELETON, and parts of PROJECT_STATE drifted behind it.

---

## 11. Recommended Current Milestone

**Adopt the Handbook §8 roadmap as the single source of truth** (it is the constitution;
CLAUDE.md and PROJECT_STATE conform to it, not vice-versa). On that roadmap, milestones 1–5
are done and:

> **Current Milestone = M6, Knowledge Extraction Engine — completion.**

The abstraction layer (ports, profiles, registry, artifacts) is in place; what remains to
move M6 from *Partially Implemented* to *Completed* is, per Handbook §11.40 layer order:
concrete adapters for the defined ports, a `KnowledgeIngestionPort` adapter wiring extraction
output into the existing knowledge persistence, a composition seam, and tests. **No
framework-engine, graph, search, retrieval, or RAG work should begin** — those are future,
locked milestones (§11.36).

---

## 12. Recommended Next Action

Because Handbook §12 makes an **accurate PSR a precondition for advancing**, the next action
is **not coding** — it is a governance reconciliation requiring Product Owner approval on:

1. **Confirm the authoritative roadmap** (recommended: Handbook §8 Knowledge-First) and
   correct `PROJECT_STATE.md`, `README.md`, and `PROJECT_SKELETON.md` to match source
   reality.
2. **Approve a scope** for the immediate work: (a) close the `uow.missions` contract hole as
   a blocking fix, then (b) complete **M6 Knowledge Extraction Engine** (adapters + ingestion
   wiring + tests), under the standard layer order.

Address the `uow.missions` defect and the missing Mission-aggregate tests *before* extending
the engine, since the Mission human-gate is the platform's core safety guarantee and is
currently both contract-broken and untested.

---

*Archived audit. The living status tracker is [`PROJECT_STATE.md`](../../PROJECT_STATE.md);
approved decisions are logged in
[`ARCHITECTURE_DECISION_LOG.md`](../../ARCHITECTURE_DECISION_LOG.md). When code and any
document disagree, one of them is a bug — fix it.*
