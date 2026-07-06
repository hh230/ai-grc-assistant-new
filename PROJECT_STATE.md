# PROJECT_STATE.md — AI GRC Assistant

> **Canonical handoff document.** Read this first when resuming work in a new session. It
> summarizes what exists, why, and what comes next. Authoritative companions:
> [`CLAUDE.md`](./CLAUDE.md) (the engineering constitution), the
> [`docs/SOFTWARE_ARCHITECTURE_HANDBOOK.md`](./docs/SOFTWARE_ARCHITECTURE_HANDBOOK.md) (the
> governance & Knowledge-First roadmap),
> [`docs/architecture/ARCHITECTURE_AUDIT.md`](./docs/architecture/ARCHITECTURE_AUDIT.md)
> (the 2026-06-27 source-verified audit this PSR is reconciled to), the
> [`ARCHITECTURE_DECISION_LOG.md`](./ARCHITECTURE_DECISION_LOG.md) (consolidated decisions),
> [`docs/architecture/PROJECT_SKELETON.md`](./docs/architecture/PROJECT_SKELETON.md)
> (repo structure), the persistence deep-dive
> [`docs/architecture/persistence-implementation-report.md`](./docs/architecture/persistence-implementation-report.md),
> and the ADRs in [`docs/adr/`](./docs/adr/).
>
> **Last updated:** 2026-06-27 · **Status (source-verified, Evidence-First per Handbook
> §12.11):** Knowledge-First roadmap (Handbook §8) milestones **M1–M5 implemented** (M3–M5
> test-verified; M1–M2 implemented-but-unverified); **M6 Knowledge Extraction Engine COMPLETE**
> — ports + pipeline coordinator (`engine.py`) + 7 concrete rule-based adapters
> (`grc_extraction_adapters`) + composition/profiles, runnable end-to-end and fully tested; the
> production Postgres ingestion adapter is deferred pending a Product Owner decision (§0 note,
> [ADL-0008](./ARCHITECTURE_DECISION_LOG.md)). **All Knowledge-First roadmap milestones M6–M12 are
> COMPLETE** (M1–M5 were pre-existing): Extraction Engine, Framework Engine, Knowledge Graph,
> Search, Retrieval, **RAG (OpenAI provider, [ADL-0009](./ARCHITECTURE_DECISION_LOG.md))**, and the
> **AI Agents + Orchestrator** — all pure/abstracted, tested, all gates clean. The
> Application/Services layer and the `apps/web` demo sit **outside** the locked roadmap order (see
> §10 and [ADL-0007](./ARCHITECTURE_DECISION_LOG.md)). Verified test evidence: 82 domain, **27
> extraction-engine**, **22 framework-engine**, **11 knowledge-graph**, **34 rag/llm**, **13
> agents** test functions; 19 persistence test functions (currently un-collectable — see drift
> note), **0 service tests**. See the PSR table below.

---

## 0. Project State Register (PSR) — verified milestone status

> The PSR is the **authoritative implementation tracker** (Handbook §12.12). Status follows
> Handbook §12.14 vocabulary and is **evidence-based** (§12.11): source code, tests, and
> review only — not plans or prose. Mapped to the **Handbook §8 Knowledge-First roadmap**
> (the authoritative order; see [ADL-0001](./ARCHITECTURE_DECISION_LOG.md)). Snapshot date:
> **2026-06-27**.

| #  | Milestone (Handbook §8)       | Status                       | Evidence (source) |
|----|-------------------------------|------------------------------|-------------------|
| 1  | Shared Kernel                 | Completed *(no dedicated tests)* | `packages/domain/grc_domain/shared/` |
| 2  | Core Domain                   | **Implemented / Unverified** | 12 contexts present; **no unit tests** for any |
| 3  | Knowledge Domain              | **Completed**                | `domain/grc_domain/knowledge/` + `domain/tests/knowledge/` |
| 4  | Knowledge Database            | **Completed**                | 20 tables in `0001_initial_schema.py`; `tests/test_migration.py` |
| 5  | Knowledge DB Integration      | **Completed** ⚠️ *(import-broken — see note)* | `repositories/` · `mappers/` · `unit_of_work.py` · `outbox.py`; 19 test fns |
| 6  | Knowledge Extraction Engine   | **Completed (engine)** ⚠️ *(production DB ingestion deferred — see note)* | ports + coordinator `engine.py` + **7 rule-based adapters** + composition/profiles (`grc_extraction_adapters`); **27 tests** (10 engine, 17 adapters incl. end-to-end); ruff + black + mypy-strict clean |
| 7  | Framework Engine              | **Completed**                | `packages/framework-engine` loader+validator+catalog (coverage, cross-mapping, versioning) + real seed data (ISO 27001, NCA ECC, mapping); **22 tests**; ruff + black + mypy-strict clean |
| 8  | Knowledge Graph               | **Completed**                | `packages/knowledge-graph` in-memory typed graph (neighbors/traversal/paths, tenant-isolated); **11 tests**; all gates clean |
| 9  | Search                        | **Completed**                | `grc_rag.search` lexical/type-filtered keyword search over knowledge objects; **9 tests**; all gates clean |
| 10 | Retrieval                     | **Completed**                | `grc_rag.retrieval` grounded cited retrieval + `grc_rag.semantic` embedding-backed vector search; all gates clean |
| 11 | RAG                           | **Completed** (provider: OpenAI, [ADL-0009](./ARCHITECTURE_DECISION_LOG.md)) | `grc_llm` provider abstraction + OpenAI adapter + fakes; `grc_rag.pipeline` grounded generation with citation validation; **34 tests** (llm 7 + rag 27); all gates clean |
| 12 | AI Agents                     | **Completed**                | `grc_agents` roster (Knowledge/Compliance/Risk/Policy/Report/Workflow) + AI Orchestrator (routing, decision trail, human gates); **13 tests**; all gates clean |

**Off-roadmap (built ahead of / outside the locked order):**

| Item | Status | Evidence |
|------|--------|----------|
| Application / Services layer (all 14 contexts) | **Implemented / Unverified** | `packages/services/grc_services/` (~4,093 LOC); **0 tests** |
| Web application (`apps/web`) | **Implemented — self-contained full-stack app** (2026-07-02) | Own Next.js API routes (`apps/web/app/api/**`) implement auth, documents, analysis/RAG, chat, evidence, policies, risk, reports — independent of `apps/api`/the Python Orchestrator. Persistence: PostgreSQL via `lib/db/**` (raw SQL + `pg`), migrations in `lib/db/migrations/`, document-chunk embeddings in pgvector (`vector(3072)`, OpenAI `text-embedding-3-large`, cosine `<=>` retrieval). Every repository (documents/evidence/analyses/document_chunks/conversations/policies/risks) is a tenant-scoped Postgres adapter behind a port; object bytes stay on the filesystem `BlobStore` port. See `apps/web/README.md`. |

> **"Implemented / Unverified"** means code exists but lacks the passing tests + architectural
> review that Evidence-First (§12.11) requires to call a layer *Completed* — see
> [ADL-0005](./ARCHITECTURE_DECISION_LOG.md). Full reasoning:
> [`docs/architecture/ARCHITECTURE_AUDIT.md`](./docs/architecture/ARCHITECTURE_AUDIT.md).
>
> ⚠️ **M5↔M3 drift / M6 production-ingestion boundary (product decision required —
> [ADL-0008](./ARCHITECTURE_DECISION_LOG.md)).** The M6 engine is complete and persists through
> the `KnowledgeIngestionPort` (proven by the reference `InMemoryKnowledgeIngestion` adapter).
> The **production Postgres** ingestion adapter is deferred because the Knowledge persistence
> layer is structurally out of sync with the refactored domain: the `KnowledgeSource` aggregate
> dropped `source_type`/`ingestion_status` (now `knowledge_domain`), yet the
> `knowledge_sources` table/model/migration still carry the old columns and
> `grc_services/knowledge/commands.py` + `grc_persistence/mappers/knowledge.py` import the
> removed enums (`KnowledgeSourceType`, `IngestionStatus`) — so both **fail to import**.
> Re-aligning M5 to M3 is a **schema/migration change that re-opens a "Completed" milestone**
> and involves design choices (where ingestion status lives, title/checksum fields) → **needs
> Product Owner approval.** Unrelated to and not blocking the extraction engine, which depends
> only on `grc_domain`. Tracked in §10.

---

## 1. What this project is

A global, multi-tenant **Enterprise SaaS** platform that helps GRC (Governance, Risk &
Compliance) teams author, map, assess, and monitor controls, policies, and risks across
many frameworks (NCA ECC, SAMA, PDPL, ISO 27001, NIST CSF, CIS, COBIT, COSO, …), grounded
in the customer's own evidence, and executed as governed **missions** rather than ad-hoc
chats. Trust, auditability, grounding, and human-in-the-loop are first-class.

---

## 2. Architecture (the big picture)

Layered, mission-driven, dependencies point **inward**; the Domain depends on nothing.

```
Interfaces (UI · API · CLI · SDK)
        → AI Orchestrator (the brain; plans, routes, memory, policy, human gates)
        → Multi-Agent layer (Knowledge · Policy · Compliance · Risk · Report · Workflow)
        → Tools (every business capability; via the Tool Registry)
        → Services / Application Layer (use cases, transaction boundary)   ← BUILT
        → Domain Layer (DDD bounded contexts; pure)                        ← BUILT
        → Infrastructure (Postgres + pgvector, event bus, LLM providers)   ← BUILT (persistence)
```

The **eight architectural pillars** (CLAUDE.md §3), binding on every change:

1. The **AI Orchestrator is the brain**, not the LLM (the LLM is a swappable reasoning engine).
2. The system is **Mission-Centric**, not chat-centric.
3. Every business function is an independent, callable **Tool** (six callers: Orchestrator,
   API, UI, Workflow, Scheduled Jobs, Tests).
4. **Multi-agent**, specialized, composable, governed.
5. **Everything is grounded** (RAG, citations, confidence).
6. **Frameworks are data, not code** (Framework Engine).
7. **Multi-tenant, enterprise-grade, global** by default.
8. **Transparency/auditability** is mandatory.

---

## 3. ADRs (28 accepted) — `docs/adr/`

| ADR | Decision |
|-----|----------|
| 0001 | Record architecture decisions (ADR process) |
| 0002 | Monorepo strategy (polyglot: pnpm+turbo / uv) |
| 0003 | Mission-Centric design (not chat-centric) |
| 0004 | AI Orchestrator is the brain — not the LLM |
| 0005 | Multi-Agent architecture |
| 0006 | Tools as first-class units & the Tool Registry |
| 0007 | Framework Engine — frameworks as data, not code |
| 0008 | Knowledge & RAG architecture |
| 0009 | Event-Driven Architecture where it earns its keep |
| 0010 | Plugin architecture for extensibility |
| 0011 | Domain-Driven Design boundaries |
| 0012 | PostgreSQL + pgvector as the primary data store |
| 0013 | FastAPI (backend) + Next.js (frontend) stack |
| 0014 | Security principles & multi-tenancy |
| 0015 | Audit & traceability (AI transparency) |
| 0016 | Workspace model (Workspace-first UX) |
| 0017 | Policy Intelligence AI runtime: real Tool Registry, roster extension, apps/web-Postgres persistence bridge (`packages/persistence-web`) — `apps/api`/`apps/worker` become the real AI runtime, reading/writing apps/web's live schema; no second database |
| 0018 | Regulatory Intelligence engine (PI-P1): pure obligation split/classify pipeline (`packages/regulatory-intelligence`), Tool-audited LLM classification (`packages/regulatory-intelligence-adapters`), platform-scope storage (`regulatory_raw_documents`/`regulatory_obligations`) — the connector→raw→extract→classify→store pipeline that will feed Policy Hunter |
| 0019 | Regulatory Connectors / Crawlers (PI-P2): source registry as config (`/regulatory-sources`), polite web crawling (`packages/regulatory-crawlers` — robots.txt, rate limiting, HTML/PDF/text normalization), change detection, and `RegulatoryCrawlerRunner` orchestration — the discovery/fetch stage feeding the PI-P1 engine; 6 initial Saudi sources (SAMA, CMA, NCA, SDAIA, MHRSD, ZATCA) |
| 0020 | Policy Hunter Agent (PI-P3): a read-only, deterministic (no LLM) coverage-gap agent (`packages/policy-hunter`) — compares confirmed regulatory obligations against tenant policies via word-overlap matching, reports `missing_required_policy`/`outdated_policy`/`incomplete_coverage`/`unmapped_regulatory_obligation` findings with full evidence, through two Tool-Registry-audited Tools (`list_applicable_obligations.v1`, `scan_policy_coverage_gaps.v1`) |
| 0021 | Policy Analyst Agent (PI-P4): a read-only, deterministic (no LLM) policy-quality agent (`packages/policy-analyst`) — analyzes one policy's completeness (7 required sections), regulatory alignment (recall-scored coverage vs. confirmed obligations), internal consistency (unclear ownership/ambiguous language/conflicting cadences), and freshness (stale policy/policy older than a linked regulation), through one Tool-Registry-audited Tool (`review_policy_quality.v1`) |
| 0022 | Policy Intelligence API exposure (PI-P5): `apps/api`'s `web_runtime.py` now registers Policy Hunter's and Policy Analyst's three Tools on the live Tool Registry; a new `routers/policy_intelligence.py` exposes `GET /policy-intelligence/obligations`, `/coverage-gaps`, and `/policies/{id}/quality-review` — each authorized via the existing RBAC `Action.READ`/`ResourceType.POLICY` gate, executed through `PolicyHunterAgent`/`PolicyAnalystAgent`, and unconditionally audited by the same Tool Registry as every other Tool call |
| 0023 | Policy Intelligence frontend (PI-P6): `apps/web`'s first real call to `apps/api` — `lib/policyIntelligence/service.ts` proxies to PI-P5's endpoints using `ActorContext.apiToken` (the PI-P0-era bridge, unused until now), exposed via `app/api/policy-intelligence/*` Route Handlers and a three-tab `/policy-intelligence` workspace page (Obligations, Coverage Gaps, Quality Review); `apps/api` remains the sole authorization source of truth, no business logic is duplicated in TypeScript |
| 0024 | Policy Builder Agent (PI-P7): a read-only, deterministic (no LLM) drafting agent (`packages/policy-builder`) — turns one confirmed regulatory obligation into a starter policy draft (a template: the Purpose section quotes the obligation with a citation, the other six required sections are explicit `[Human input required]` placeholders), through one Tool-Registry-audited Tool (`draft_policy_from_obligation.v1`); has no write path at all — human approval before any policy change is structural, not a runtime check, since a human must save the proposal through the existing, unchanged `submit-for-review`/`approve`/`publish` workflow |
| 0025 | Autonomous Knowledge Engine (KI-P1): a catalog-driven Knowledge Question Generator (`/knowledge-catalog`, 33 questions across 11 GRC/legal domains), a deterministic Knowledge Gap Detector (`packages/knowledge-intelligence`), and a Tool-audited LLM synthesis step (`packages/knowledge-intelligence-adapters`, `synthesize_knowledge_answer.v1`) that grounds every answer in one already-fetched trusted-source excerpt — never the model's own knowledge; new platform-scope `knowledge_items` storage (`grc_persistence_web.KnowledgeItemRepository`) whose idempotent upsert never resets an already-verified item's status; no live trusted-source fetching, consumer wiring, API/UI, or scheduling yet — all named future work |
| 0026 | Autonomous Knowledge Research (KI-P2): closes KI-P1's named fetching gap — a curated, authority-ranked trusted-source catalog (`/trusted-sources`), a pure Research Planner/Coordinator (`packages/knowledge-research`) that reuses `grc_regulatory_crawlers`'s HTTP primitives (never a second crawler) and the unmodified `KnowledgeDiscoveryEngine`, and a `KnowledgeGapResearchRunner` (`packages/knowledge-research-adapters`) tying gap detection, research, and the existing idempotent upsert together end to end; no new Tool — every synthesis call still flows through `synthesize_knowledge_answer`; no schema change, UI, or scheduling |
| 0027 | Domain Ontology Engine (KI-P3): a structured GRC/Compliance/Governance/Risk/Legal/Contracts taxonomy (`/ontology`, 37 topics across 7 domains + 6 contract types with 38 categorized clauses), a pure package (`packages/knowledge-ontology`) with deterministic, template-based question generation (additive to and disjoint from the hand-curated catalog), missing-clause detection, and a fixed six-member relationship vocabulary (one kind derived from contract-type data, five illustrated by curated example edges); one verified trusted-source addition (NIST CSF) — no unverifiable sources added; no LLM decisions, no new Tool, no UI/API |
| 0028 | Autonomous Knowledge Worker (KI-P4): closes ADR-0019/25/26/27's repeated "no scheduling" deferral — a pure `LearningCycleScheduler` + `combine_question_sources` (merges KI-P1's catalog with KI-P3's ontology-generated questions) in a new package (`packages/knowledge-worker`), an `AutonomousKnowledgeWorker` runner/orchestrator (`tick`/bounded `run_loop`) that drives the *unmodified* KI-P2 `KnowledgeGapResearchRunner` via a structural Protocol (no new dependency, no new Tool); and the project's first real, always-on composition root — `apps/worker/src/grc_worker/knowledge_learning_loop.py` — wiring a real Postgres `KnowledgeItemRepository`, a real `OpenAIChatModel` behind the already-registered `synthesize_knowledge_answer.v1` Tool, and a real `HttpResearchCrawler`, driven by a genuine infinite loop with SIGINT/SIGTERM shutdown; found and fixed two pre-existing mypy-strict Protocol gaps in `grc_knowledge_research_adapters` (frozen-dataclass vs. plain-attribute Protocol members; invariant `list` vs. covariant `Sequence`) surfaced only once a real caller exercised them |
| 0029 | AI Worker Control Center (KI-P5): closes ADR-0028's "no durable last_run_at... no API endpoint, no UI" deferral — optional `WorkerControlPort`/`WorkerEventSink` seams added to `packages/knowledge-worker` (zero behavior change when omitted) so an admin's enable/disable/interval/manual-trigger change takes effect on the next poll; `KnowledgeGapResearchRunner` (KI-P2) now emits the same timeline events during research; three new platform-scope tables (`worker_control` singleton, `worker_run_history`, `worker_events` — one unified append-only table serving both the activity timeline and the admin-action audit trail); a new `ResourceType.KNOWLEDGE_WORKER` in the RBAC matrix (`OWNER`/`ADMIN` full control, `AUDITOR` read-only via its existing blanket grant, everyone else 403); six new `apps/api` endpoints (`GET /status`,`/events`,`/runs`,`/reports`, `POST /schedule`,`/trigger`) modeled on Policy Intelligence's router; and a real `/ai-worker` admin page (status card, schedule control, "Run Learning Now", activity timeline, learning reports) — verified live end-to-end in the browser, not just against tests |

Any change to the pillars, the Tool contract, the agent roster, the Framework Engine
model, or the Mission Lifecycle **requires a new ADR** and a CLAUDE.md update. ADRs are
immutable once accepted — supersede, don't edit.

---

## 4. Domain Layer — `packages/domain/grc_domain/` (implemented; partially verified)

**Pure Python, standard library only.** Verified by source inspection: zero imports of
FastAPI, SQLAlchemy, pydantic, LLM SDKs, or DB drivers. A shared kernel + **14 bounded
contexts** (the 14th, `extraction`, supports the Knowledge Extraction Engine and was added
after this file's earlier "13 contexts" claim — see
[ADL-0003](./ARCHITECTURE_DECISION_LOG.md)). Repository classes here are **abstract
interfaces only**.

> **Verification status (Evidence-First, Handbook §12.11):** the **82 domain test functions
> cover only the `knowledge` and `extraction` contexts** (`packages/domain/tests/`). The
> other **12 contexts — including the flagship `missions` aggregate (lifecycle + human-gate
> rule) — have no unit tests** and are therefore **Implemented / Unverified**, not
> "complete." This is the test-debt gate of [ADL-0005](./ARCHITECTURE_DECISION_LOG.md).

**Shared kernel (`shared/`):** base `Entity`, `AggregateRoot` (records domain events),
`ValueObject`, `DomainEvent`, typed identifiers (one per aggregate), base exception
hierarchy, shared value objects (`Confidence`, `Citation`, `DateRange`, `Actor`,
`SemanticVersion`, `TraceContext`) + shared enums (`ConfidenceLevel`, `DataClassification`).

**Bounded contexts (14):** tenancy, workspace, frameworks, controls, policies, risks,
assessments, evidence, knowledge, **extraction** (knowledge-extraction support context;
tested), reporting, platform (tool/agent/plugin descriptors), missions (the flagship
aggregate with lifecycle + human-gate rule), audit (append-only).

> The Domain Layer was **not modified** during the persistence work.

---

## 5. Application Layer — `packages/services/grc_services/` (implemented; **unverified**)

**Clean Architecture; depends only on `grc_domain`** (verified: no framework imports). A
shared kernel + 14 capability packages. CQRS bases, `TransactionalCommandHandler` (open UoW
→ `_execute` → commit → dispatch events), the **`UnitOfWork`** port (the transaction
boundary exposing the domain repositories), ports (`Clock`, `IdGenerator`,
`AuthorizationService`, `EventDispatcher`, `Validator`, `CommandBus`/`QueryBus`), `Result`
types, application exceptions (incl. `ConcurrencyError`, `ConflictError`), and
`ExecutionContext`/`Principal`.

> **Verification status:** the Application layer has **zero tests** (`packages/services/tests/`
> is an empty `.gitkeep`). Under Evidence-First it is **Implemented / Unverified**, not
> "complete" — and this also breaks the Definition of Done (CLAUDE.md §24, which requires
> tests for the Application layer). See [ADL-0005](./ARCHITECTURE_DECISION_LOG.md).
>
> **Known contract hole (blocker):** the `UnitOfWork` ABC declares 16 repositories but **not
> `missions`**, even though `missions/handlers.py` calls `uow.missions` in nine places and
> only the *concrete* `SqlAlchemyUnitOfWork` provides it. This is a Liskov/contract
> violation and a likely `mypy` failure. The corrective decision is
> [ADL-0006](./ARCHITECTURE_DECISION_LOG.md); the fix is **deferred until approved** (not
> implemented as part of these governance tasks). Also tracked in §10.

---

## 6. Infrastructure / Persistence Layer ✅ — `packages/persistence/grc_persistence/`

**The outermost adapter (CLAUDE.md §5).** Implements the domain repository interfaces and
the application's `UnitOfWork` port against PostgreSQL. Depends on `grc_domain` and
`grc_services` only — never the reverse. **SQLAlchemy 2.x async + asyncpg + Alembic +
PostgreSQL** in production; the test suite runs against an async **SQLite** engine built
from the same metadata (portable `JSON`/`JSONB` type). Full design rationale lives in
[`docs/architecture/persistence-implementation-report.md`](./docs/architecture/persistence-implementation-report.md).

**Sub-packages**

- **`contracts/`** — the persistence seams: `AggregateMapper`/`ChildMapper` (the Domain↔ORM
  translation contract), `RepositoryCache` + `NullRepositoryCache` + `CacheKey`, `Outbox` +
  `IntegrationEvent`, and the `AggregateTracker` protocol.
- **`db/`** — `Base` (DeclarativeBase) + deterministic constraint-naming convention,
  `TimestampMixin`/`AggregateRootMixin` (string PK + `version` wired as `version_id_col`),
  the portable `JSONColumn` type (`JSONB` on Postgres, `JSON` elsewhere), and the async
  engine + session-factory helpers.
- **`models/`** — 20 SQLAlchemy ORM tables across the 13 contexts plus `outbox_messages`.
  Missions own child tables (`mission_steps`, `mission_approval_gates`) with ordered,
  cascade relationships. Models carry no behaviour and no translation logic.
- **`mappers/`** — the **only** place Domain↔ORM (and Domain→integration-event) translation
  happens: one mapper per context, `_common.py` value-object codecs, `events.py` for the
  outbox envelope. Aggregates are reconstructed via the plain constructor so loading never
  re-emits domain events.
- **`repositories/`** — concrete implementations of every domain repository interface (17:
  the 16 on the `UnitOfWork` ABC + `MissionRepository`). A `base.py` centralizes the
  mechanics (query construction helpers, optimistic concurrency, aggregate tracking, child
  synchronization, cache hooks); `_sync.py` performs diff-based child synchronization keyed
  on stable identifiers. Concrete repos contain essentially only their queries.
- **`unit_of_work.py`** — `SqlAlchemyUnitOfWork`: one session per activation, every
  repository exposed lazily, aggregate tracking for event collection, the transactional
  outbox write, and translation of `StaleDataError`→`ConcurrencyError` /
  `IntegrityError`→`ConflictError`. Overrides `__aexit__` so read-only query handlers
  release their session.
- **`outbox.py`** — `SqlAlchemyOutbox`: writes integration events as `outbox_messages` rows
  **in the same transaction** as the state change — the single source of integration events.
- **`migrations/`** — Alembic `env.py` (URL from `ALEMBIC_DATABASE_URL`/`DATABASE_URL`, never
  in code), `script.py.mako`, and `versions/0001_initial_schema.py` (all 20 tables, FKs,
  indexes, composite PK for frameworks, JSONB on Postgres).

**Cross-cutting behaviour implemented**

- **Tenant isolation** — every read/list is scoped by `organization_id`; `save` retrieves
  the managed row by PK and re-checks the tenant defensively (default deny).
- **Optimistic concurrency** — `version_id_col` on every aggregate root; the loaded row is
  pinned for the unit of work so the version read at load time stays authoritative.
- **Transactional outbox** — domain events recorded by tracked aggregates become outbox
  rows atomically with the change; a rejected commit leaves no outbox row.
- **Diff-based child sync** — Mission steps/gates reconciled (add/update/remove) by stable
  id with order preserved via a `position` column.
- **Repository cache** — `RepositoryCache` hooks on every read/write; default is
  `NullRepositoryCache` (read-your-writes preserved out of the box).

**Verification** (in an isolated Python 3.12 venv with SQLAlchemy 2.0, aiosqlite, Alembic):
- `ruff` clean, `black` clean, **59 modules import** cleanly.
- **19 integration tests pass** (see §6 of the implementation report): repository
  round-trip, tenant isolation, optimistic-concurrency conflicts, diff-based child sync,
  transactional outbox, and migration↔model parity.
- The Alembic migration builds the full schema on SQLite (20/20 tables, all columns match
  `Base.metadata`), downgrades cleanly, and renders `JSONB` against the Postgres dialect.

---

## 7. Current package structure (high level)

```
ai-grc-assistant/
├─ apps/            web (✅ self-contained full-stack app; own API routes + PostgreSQL/pgvector;
│                        PI-P6 (ADR-0023) adds its first real call to apps/api —
│                        lib/policyIntelligence/service.ts proxies to PI-P5's endpoints via
│                        ActorContext.apiToken; app/api/policy-intelligence/* Route Handlers;
│                        /policy-intelligence workspace page — obligations, coverage gaps,
│                        quality review)
│                   api (real FastAPI app + routers + Orchestrator wiring; now also the
│                        Policy Intelligence AI runtime — ADR-0017, web_runtime.py; PI-P5
│                        (ADR-0022) exposes Policy Hunter/Analyst over HTTP:
│                        routers/policy_intelligence.py)
│                   orchestrator · workflow (scaffold only) · worker (scaffold; scheduled
│                        Policy Intelligence jobs land here in a later phase)
├─ packages/
│  ├─ domain/       grc_domain/        ◑ Domain Layer (pure; knowledge+extraction tested, rest unverified)
│  ├─ services/     grc_services/      ◑ Application Layer (depends on domain only; 0 tests — unverified)
│  ├─ persistence/  grc_persistence/   ✅ Infrastructure / Persistence (test-verified; depends on domain + services)
│  │  ├─ contracts/ db/ models/ mappers/ repositories/ migrations/
│  │  ├─ unit_of_work.py · outbox.py · alembic.ini · tests/
│  ├─ persistence-web/ grc_persistence_web/ ✅ Adapters against apps/web's live Postgres schema
│  │                     (ai_tool_invocations, policies, policy_missions, regulatory_raw_documents,
│  │                     regulatory_obligations, knowledge_items) — ADR-0017/0018/0019/0025;
│  │                     not a second database, and independent of packages/persistence above
│  ├─ regulatory-intelligence/ grc_regulatory_intelligence/ ✅ PI-P1 pure engine: split→classify
│  │                     obligation pipeline; PI-P2 adds source registry/config loader,
│  │                     RegulatoryDocumentInput, change detection, CrawlerPort — zero external
│  │                     deps throughout (ADR-0018/0019; 24 tests)
│  ├─ regulatory-intelligence-adapters/ grc_regulatory_intelligence_adapters/ ✅ PI-P1 connectors,
│  │                     rule-based extractor, Tool-audited LLM classifier (ADR-0018; 15 tests)
│  ├─ regulatory-crawlers/ grc_regulatory_crawlers/ ✅ PI-P2 ingestion layer: robots.txt +
│  │                     rate-limited HTTP crawler, HTML/PDF/text normalization,
│  │                     RegulatoryCrawlerRunner orchestrator, observability (ADR-0019; 27 tests)
│  ├─ policy-hunter/     grc_policy_hunter/       ✅ PI-P3 read-only, deterministic (no LLM)
│  │                     coverage-gap agent: list_applicable_obligations.v1 +
│  │                     scan_policy_coverage_gaps.v1 Tools, PolicyHunterAgent (ADR-0020; 15
│  │                     tests) — wired into apps/api's Tool Registry in PI-P5 (ADR-0022)
│  ├─ policy-analyst/    grc_policy_analyst/      ✅ PI-P4 read-only, deterministic (no LLM)
│  │                     policy-quality agent: completeness/regulatory alignment/internal
│  │                     consistency/freshness via review_policy_quality.v1,
│  │                     PolicyAnalystAgent (ADR-0021; 21 tests) — wired into apps/api's Tool
│  │                     Registry in PI-P5 (ADR-0022)
│  ├─ policy-builder/    grc_policy_builder/      ✅ PI-P7 read-only, deterministic (no LLM)
│  │                     drafting agent: draft_policy_from_obligation.v1 (a template — quotes
│  │                     the obligation in Purpose, six other sections are explicit
│  │                     placeholders), PolicyBuilderAgent (ADR-0024; 13 tests); no write
│  │                     path — not yet wired into apps/api or apps/web
│  ├─ knowledge-intelligence/ grc_knowledge_intelligence/ ✅ KI-P1 pure engine: catalog-driven
│  │                     Knowledge Question Generator (question_catalog.py, reads
│  │                     /knowledge-catalog/*.json), deterministic Knowledge Gap Detector
│  │                     (gap_detection.py), KnowledgeDiscoveryEngine (ADR-0025; 22 tests) —
│  │                     distinct from knowledge-graph/ below (M8, unrelated older roadmap)
│  ├─ knowledge-intelligence-adapters/ grc_knowledge_intelligence_adapters/ ✅ KI-P1
│  │                     Tool-audited LLM synthesis: synthesize_knowledge_answer.v1, grounded
│  │                     strictly in a given trusted-source excerpt (ADR-0025; 6 tests); no
│  │                     live trusted-source fetching yet — reuses regulatory-crawlers later
│  ├─ knowledge-research/ grc_knowledge_research/ ✅ KI-P2 pure engine: curated-catalog Research
│  │                     Planner (planning.py), word-overlap relevance ranking, ResearchCoordinator
│  │                     reusing KnowledgeDiscoveryEngine unmodified (ADR-0026; 16 tests)
│  ├─ knowledge-research-adapters/ grc_knowledge_research_adapters/ ✅ KI-P2 HttpResearchCrawler
│  │                     (built from grc_regulatory_crawlers primitives), trusted-source catalog
│  │                     loader, KnowledgeGapResearchRunner tying gap detection→research→storage
│  │                     together (ADR-0026; 24 tests incl. KI-P5's optional activity-timeline
│  │                     event emission, ADR-0029) — no new Tool, no scheduling yet
│  ├─ knowledge-ontology/ grc_knowledge_ontology/ ✅ KI-P3 Domain Ontology Engine: Topic/
│  │                     ContractType/Clause/Relationship models (reads /ontology/*.json),
│  │                     deterministic template-based question generation, missing-clause
│  │                     detection (ADR-0027; 27 tests) — no LLM decisions, no new Tool
│  ├─ knowledge-worker/   grc_knowledge_worker/    ✅ KI-P4 Autonomous Learning Loop: merges
│  │                     KI-P1 catalog + KI-P3 ontology questions (question_sources.py), a
│  │                     pure LearningCycleScheduler (scheduler.py), and
│  │                     AutonomousKnowledgeWorker's tick()/bounded run_loop() driving the
│  │                     unmodified KI-P2 KnowledgeGapResearchRunner via a structural Protocol
│  │                     (ADR-0028; 26 tests incl. KI-P5's control.py/events.py seams) —
│  │                     apps/worker/src/grc_worker/knowledge_learning_loop.py is the real
│  │                     composition root (10 tests) wiring real Postgres/OpenAI/HTTP behind
│  │                     it plus (KI-P5, ADR-0029) WorkerControlRepository/
│  │                     WorkerEventRepository/WorkerRunHistoryRepository, driven by a real
│  │                     infinite loop with SIGINT/SIGTERM shutdown. KI-P5 also added
│  │                     `worker_control`/`worker_run_history`/`worker_events` to
│  │                     persistence-web (5 tests), `apps/api/routers/knowledge_worker.py`
│  │                     (9 tests) and apps/web's admin-only `/ai-worker` page
│  ├─ extraction/        grc_extraction/          ✅ M6 engine: ports + pipeline coordinator (10 tests)
│  ├─ extraction-adapters/ grc_extraction_adapters/ ✅ M6 rule-based adapters + composition (17 tests)
│  ├─ framework-engine/   grc_framework_engine/    ✅ M7 loader + catalog + seed data (22 tests)
│  ├─ knowledge-graph/    grc_knowledge_graph/     ✅ M8 in-memory typed graph (11 tests)
│  ├─ rag/                grc_rag/                 ✅ M9 search · M10 retrieval/semantic · M11 RAG (27 tests)
│  ├─ llm/                grc_llm/                 ✅ provider abstraction + OpenAI adapter + fakes (7 tests)
│  ├─ agents/             grc_agents/              ✅ M12 agent roster + AI Orchestrator (13 tests)
│  ├─ tools/              grc_tools/               ✅ Tool contract + Registry (ADR-0006 implemented; 5 tests)
│  ├─ events/ plugins/ observability/ security/ config/            (scaffold only)
│  ├─ ui/ contracts/ i18n/  (TypeScript; scaffold only)
├─ frameworks/      framework definitions as data (schema + per-framework folders)
├─ regulatory-sources/ regulatory source definitions as data (PI-P2, ADR-0019) — sa/{sama,cma,
│                   nca,sdaia,mhrsd,zatca}.json
├─ knowledge-catalog/ GRC/compliance/legal question catalog as data (KI-P1, ADR-0025) — one
│                   JSON file per KnowledgeDomain, 33 questions across 11 domains
├─ trusted-sources/ curated, authority-typed research catalog as data (KI-P2/KI-P3, ADR-0026/
│                   0027) — sa/{sama,cma,nca,sdaia,mhrsd,zatca}.json (reused, verified regulator
│                   URLs) + us/nist.json (verified live in KI-P3); ISO deliberately not added
│                   (could not be verified live — see ADR-0027)
├─ ontology/        GRC/Compliance/Governance/Risk/Legal/Contracts taxonomy as data (KI-P3,
│                   ADR-0027) — one JSON file per domain (37 topics across 7 domains),
│                   contracts.json (6 contract types, 38 categorized clauses), relationships.json
├─ prompts/         versioned prompt artifacts (empty)
├─ docs/            architecture/ (+ persistence report) · adr/ (27) · onboarding/ · runbooks/
├─ infra/ docker/ config/ scripts/ tests/ .github/
├─ CLAUDE.md · README.md · PROJECT_STATE.md (this file)
└─ workspace manifests: pnpm-workspace.yaml · turbo.json · pyproject.toml · Makefile
```

Tooling: **uv** (Python workspace) + **pnpm/turbo** (TS). Quality gates: `ruff`, `black`,
`mypy` (Python); ESLint/Prettier/tsc (TS). Local infra: `docker/compose` with
`pgvector/pgvector:pg16`.

---

## 8. Coding conventions (as practiced so far)

- **Python ≥ 3.12 target**; domain/application kept 3.10-runnable but the persistence layer
  uses SQLAlchemy 2.x typed `Mapped[...]` declarative and requires 3.12 to run. `ruff` +
  `black` clean (line length 100). Generated Alembic migrations carry a per-file `E501`
  ignore in the root `pyproject.toml`.
- **`from __future__ import annotations`** at the top of every module.
- **Persistence-specific:**
  - All Domain↔ORM translation lives in `mappers/`; repositories never read a domain field
    to write an ORM column directly.
  - Repositories do only query construction, persistence orchestration, optimistic
    concurrency, aggregate tracking, child synchronization, and cache hooks.
  - Enums and typed ids are stored as strings; structured value-object collections as
    `JSONB`/`JSON`; sets are encoded as sorted lists for deterministic storage.
  - Aggregate-root tables carry a `version` optimistic-concurrency column (the framework
    table names it `row_version` to avoid colliding with its domain `version_label`).
  - The tenant column is `organization_id` (the tenant aggregate is `Organization`); this is
    the concrete realization of CLAUDE.md §21's generic `tenant_id` guidance.
- DTOs, identifiers, events, and naming otherwise follow the domain/application conventions.

---

## 9. Architectural principles to keep honoring

- **Dependencies point inward.** Domain imports nothing; Application imports only Domain;
  Persistence implements the interfaces and is injected at the composition root. The
  Persistence layer imports `grc_domain` and `grc_services` and nothing imports it back.
- **Tenant isolation is absolute.** Every load/list/save is scoped by `organization_id`;
  default deny. (Demonstrated by the tenant-isolation tests.)
- **Human gates for consequential actions.** Encoded in the domain; the persistence layer
  preserves the mission gates and approval state faithfully.
- **Grounding & auditability** are structural; the transactional outbox makes every state
  change emit a reconstructable integration event.
- **Frameworks/Tools/Agents/Plugins extend at the edges** via data/registries, not core
  edits.
- **No business logic in the wrong layer** — none in repositories, mappers, or migrations.

---

## 10. Roadmap — authoritative order = Handbook §8 (Knowledge-First)

> **Reconciliation note (2026-06-27):** the previously published roadmap in this section
> ordered work as Eventing relay → Composition root → Tools → LLM → RAG → Framework Engine →
> Orchestrator → API → Web. That order **conflicts** with the Handbook §8 "Roadmap Lock" and
> is therefore **retired** as the milestone sequence. Per
> [ADL-0001](./ARCHITECTURE_DECISION_LOG.md) (Proposed — pending Product Owner approval) the
> authoritative order is the Handbook's Knowledge-First roadmap below. The retired items are
> not lost — they are **cross-cutting enablers** sequenced *within* the milestones that need
> them (noted inline).

**Authoritative milestone order (Handbook §8):**

1. ✅ Shared Kernel — *implemented.*
2. ◑ Core Domain — *implemented; unverified (needs unit tests, esp. `missions`).*
3. ✅ Knowledge Domain — *implemented & tested.*
4. ✅ Knowledge Database — *implemented & tested (20 tables, migration).*
5. ✅ Knowledge Database Integration — *implemented & tested (repos, mappers, UoW, outbox).*
6. ✅ **Knowledge Extraction Engine — COMPLETE (engine).**
   - **Coordinator** `ExtractionPipeline` (`packages/extraction/grc_extraction/engine.py`) —
     drives the `ExtractionRun` aggregate through all stages via the ports, fail-safe, with
     confidence routing and idempotency. 10 unit tests.
   - **7 concrete rule-based adapters** + composition/profiles
     (`packages/extraction-adapters/grc_extraction_adapters`): in-memory text document adapter,
     whitespace normalizer, heading segmenter, keyword classifier, rule-based normative
     extractor, heuristic scorer, and a reference in-memory ingestion adapter. 17 tests (incl.
     end-to-end: raw text → `ExtractionResult` → ingestion). ruff + black + mypy-strict clean.
   - 🚫 **Deferred (product decision — [ADL-0008](./ARCHITECTURE_DECISION_LOG.md)):** the
     **production Postgres** `KnowledgeIngestionPort` adapter, blocked by the M5↔M3 knowledge
     persistence drift (⚠️ note under §0). The port contract is fully satisfied by the reference
     adapter, so the engine is complete and runnable; only the production DB binding awaits the
     M5 re-alignment decision.
7. ✅ **Framework Engine — COMPLETE** (`packages/framework-engine`): pure loader/validator
   (anti-corruption: framework/mapping data → domain aggregates), an in-memory **catalog**
   (versioned lookup, cross-framework correspondence resolution, coverage/gap computation), a
   JSON file loader (YAML-extensible behind one seam), and **real seed data** under
   `/frameworks` (ISO 27001:2022 + NCA ECC v2.0 subsets + an ISO→NCA mapping). 22 tests.
8. ✅ **Knowledge Graph — COMPLETE** (`packages/knowledge-graph`): in-memory typed graph over
   `KnowledgeObject` nodes and `KnowledgeRelationship` edges — neighbor/traversal/path queries,
   tenant-isolated by construction. 11 tests.
9. ✅ **Search — COMPLETE** (`grc_rag.search`): lexical, tenant-scoped, type-filtered keyword
   search with deterministic TF-overlap ranking. 9 tests.
10. ✅ **Retrieval — COMPLETE**: `grc_rag.retrieval` (grounded, budget-bounded, cited keyword
    retrieval) + `grc_rag.semantic` (embedding-backed cosine vector search via the `EmbeddingModel`
    port). *(The pgvector-backed production vector store is the remaining swap behind the same
    shape — gated on the M5 persistence re-alignment, [ADL-0008](./ARCHITECTURE_DECISION_LOG.md).)*
11. ✅ **RAG — COMPLETE** ([ADL-0009](./ARCHITECTURE_DECISION_LOG.md): **OpenAI**). `grc_llm` is the
    provider-agnostic abstraction (`ChatModel`/`EmbeddingModel` ports + provider-agnostic models +
    the **OpenAI adapter** — the only module importing the SDK — + deterministic fakes). `grc_rag`
    adds grounded generation (`pipeline`) with **citation validation**: uncited/hallucinated answers
    are rejected as "insufficient evidence", fail-safe on bad JSON; prompts are versioned. Gates use
    fakes; the OpenAI adapter has opt-in live tests.
12. ✅ **AI Agents + Orchestrator — COMPLETE** (`grc_agents`). The roster (Knowledge, Compliance,
    Risk, Policy, Report, Workflow) reasons via the provider-agnostic `ChatModel`; the Knowledge
    agent grounds via RAG. The **Orchestrator** owns deterministic routing, an auditable decision
    trail, and **human gates** — consequential output (policy drafts, workflow actions) is held for
    approval, never auto-applied (CLAUDE.md §7, §11).

**Cross-cutting, out-of-milestone-sequence (deferred / governed separately):** API
(`apps/api`), Web (`apps/web` — currently an out-of-roadmap prototype, see
[ADL-0007](./ARCHITECTURE_DECISION_LOG.md)), authorization-service implementation,
observability wiring, and the Tool-contract / mission-e2e / AI-eval test suites.

**Current state:** the **entire Knowledge-First roadmap (M6–M12) is complete and verified** — the
Extraction Engine, Framework Engine, Knowledge Graph, Search, Retrieval (lexical + semantic), RAG
(OpenAI provider), and the AI Agents + Orchestrator. Every package passes ruff + black +
mypy-strict and its tests; LLM calls in the gates use deterministic fakes (the OpenAI adapter has
opt-in live tests). **Remaining for production deployment** (not roadmap milestones, tracked as
decisions/debt): the **M5↔M3 knowledge-persistence re-alignment**
([ADL-0008](./ARCHITECTURE_DECISION_LOG.md)) so extracted knowledge + embeddings persist to
Postgres/pgvector; the **composition root + API** to wire the real OpenAI provider and the durable
stores at runtime; observability; and the `UnitOfWork.missions` fix
([ADL-0006](./ARCHITECTURE_DECISION_LOG.md)) + Core-Domain tests. A live OpenAI smoke-test was not
run because the `.env`/key is not visible to the build sandbox; the integration reads the key from
the environment and is exercised by the opt-in live suite.

---

## 11. How to verify the current state quickly

```bash
# Domain: import everything + purity (pure stdlib; runs on 3.10+)
cd packages/domain && python3 -c "import pkgutil,importlib; \
[importlib.import_module(m.name) for m in pkgutil.walk_packages(['grc_domain'],'grc_domain.')]"

# Application: import everything (needs domain on path)
cd packages && PYTHONPATH=services:domain python3 -c "import grc_services"

# Knowledge Extraction Engine (M6) — pipeline coordinator tests (needs Python 3.12 +
# pytest, pytest-asyncio; LLM-free, no DB). 10 tests.
PYTHONPATH=packages/domain:packages/extraction \
  python -m pytest packages/extraction/tests -q

# Knowledge-First serving layers (M6 adapters, M7 framework engine, M8 graph, M9/M10/M11 rag,
# M12 agents). The AI gates use deterministic fakes — no network/key. `openai` is needed only so
# the OpenAI adapter imports/type-checks. 76+47 tests.
pip install pytest pytest-asyncio 'openai>=1.40'
PYTHONPATH=packages/domain:packages/extraction:packages/extraction-adapters \
  python -m pytest packages/extraction-adapters/tests -q
PYTHONPATH=packages/domain:packages/framework-engine python -m pytest packages/framework-engine/tests -q
PYTHONPATH=packages/domain:packages/knowledge-graph python -m pytest packages/knowledge-graph/tests -q
PYTHONPATH=packages/llm python -m pytest packages/llm/tests -q
PYTHONPATH=packages/domain:packages/llm:packages/rag python -m pytest packages/rag/tests -q
PYTHONPATH=packages/domain:packages/llm:packages/rag:packages/agents \
  python -m pytest packages/agents/tests -q

# Live OpenAI smoke test (opt-in; makes paid calls). Requires the key in the env.
RUN_LLM_LIVE_TESTS=1 OPENAI_API_KEY=... \
  PYTHONPATH=packages/llm python -m pytest packages/llm/tests/test_openai_live.py -q

# Persistence: needs a Python 3.12 venv with SQLAlchemy>=2, aiosqlite, alembic,
# pytest, pytest-asyncio (asyncpg + greenlet for the Postgres extra).
cd packages && PYTHONPATH=domain:services:persistence python -c "import grc_persistence"

# Persistence tests (hermetic, async SQLite; set TEST_DATABASE_URL for Postgres parity)
PYTHONPATH=packages/domain:packages/services:packages/persistence \
  python -m pytest packages/persistence/tests -q

# Policy Intelligence PI-P0 (ADR-0017) + PI-P1 Regulatory Intelligence (ADR-0018) +
# PI-P2 Regulatory Connectors/Crawlers (ADR-0019) + PI-P3 Policy Hunter Agent (ADR-0020) +
# PI-P4 Policy Analyst Agent (ADR-0021) + PI-P5 Policy Intelligence API exposure (ADR-0022) +
# PI-P6 Policy Intelligence frontend (ADR-0023) + PI-P7 Policy Builder Agent (ADR-0024) +
# KI-P1 Autonomous Knowledge Engine (ADR-0025).
#
# `pyproject.toml` now declares `[tool.uv.sources]` for every internal package (a newer uv
# release requires each workspace member named explicitly, not just listed under
# `[tool.uv.workspace] members`) and `--import-mode=importlib` (many packages have a same-named
# `tests/` directory, which otherwise collide when the whole suite runs together). With those
# in place, `uv sync --all-packages` + `uv run pytest` runs the *entire* monorepo suite in one
# invocation — the manual per-package `PYTHONPATH=...` commands below still work but are no
# longer required. `packages/persistence/tests` is the one pre-existing exception: it still
# fails to import (`IngestionStatus` moved in `grc_domain.knowledge.enums`), unrelated to Policy
# Intelligence and already tracked as ADL-0008-gated, 0-test debt.
# Tool Registry (5 tests):
PYTHONPATH=packages/domain:packages/tools python -m pytest packages/tools/tests -q
# apps/web-Postgres bridge, incl. regulatory repositories + change-detection queries (15
# tests; needs a reachable Postgres — apply apps/web/lib/db/migrations first via
# `pnpm --filter web db:migrate`; skips cleanly if TEST_DATABASE_URL/DATABASE_URL is not
# reachable):
PYTHONPATH=packages/domain:packages/tools:packages/persistence-web \
  python -m pytest packages/persistence-web/tests -q
# Pure Regulatory Intelligence engine — zero external deps, no DB, no network. Includes the
# PI-P2 source registry/config loader and the 6 Saudi source config files (24 tests):
PYTHONPATH=packages/regulatory-intelligence python -m pytest packages/regulatory-intelligence/tests -q
# Regulatory Intelligence adapters — connectors, rule-based extractor, Tool-audited LLM
# classifier (deterministic fake chat model, no network/key; 15 tests):
PYTHONPATH=packages/domain:packages/tools:packages/llm:packages/regulatory-intelligence:packages/regulatory-intelligence-adapters \
  python -m pytest packages/regulatory-intelligence-adapters/tests -q
# Regulatory Crawlers (PI-P2) — robots.txt, rate limiting, HTML/PDF/text normalization, and
# RegulatoryCrawlerRunner, all against a fake HTTP transport (no network; 27 tests). `pypdf`
# is the one third-party dependency this package adds.
PYTHONPATH=packages/regulatory-intelligence:packages/regulatory-crawlers \
  python -m pytest packages/regulatory-crawlers/tests -q
# Policy Hunter (PI-P3) — deterministic, no-LLM coverage-gap matching engine plus its two
# Tool-Registry-audited Tools and PolicyHunterAgent, all against in-memory fakes (no DB,
# no network; 15 tests):
PYTHONPATH=packages/domain:packages/tools:packages/policy-hunter \
  python -m pytest packages/policy-hunter/tests -q
# Policy Analyst (PI-P4) — deterministic, no-LLM policy-quality engine (completeness,
# regulatory alignment, internal consistency, freshness) plus its Tool-Registry-audited Tool
# and PolicyAnalystAgent, all against in-memory fakes (no DB, no network; 21 tests):
PYTHONPATH=packages/domain:packages/tools:packages/policy-analyst \
  python -m pytest packages/policy-analyst/tests -q
# Policy Builder (PI-P7) — deterministic, no-LLM drafting engine (a template: Purpose quotes
# the obligation, six other required sections are explicit placeholders) plus its
# Tool-Registry-audited Tool and PolicyBuilderAgent, all against in-memory fakes (no DB, no
# network, no write path at all; 13 tests):
PYTHONPATH=packages/domain:packages/tools:packages/policy-builder \
  python -m pytest packages/policy-builder/tests -q
# Autonomous Knowledge Engine (KI-P1) — catalog-driven Question Generator + deterministic Gap
# Detector + KnowledgeDiscoveryEngine, zero external deps, no DB, no network (22 tests):
PYTHONPATH=packages/knowledge-intelligence python -m pytest packages/knowledge-intelligence/tests -q
# Knowledge Intelligence adapters — Tool-audited LLM synthesis grounded strictly in a given
# trusted-source excerpt (deterministic fake chat model, no network/key; 6 tests):
PYTHONPATH=packages/domain:packages/tools:packages/llm:packages/knowledge-intelligence:packages/knowledge-intelligence-adapters \
  python -m pytest packages/knowledge-intelligence-adapters/tests -q
# Knowledge Engine storage (KI-P1, ADR-0025) — KnowledgeItemRepository against apps/web's live
# `knowledge_items` table: idempotent upsert never resets an already-verified item's status
# (needs a reachable Postgres with apps/web's migrations applied; skips cleanly otherwise;
# 6 tests):
PYTHONPATH=packages/domain:packages/tools:packages/persistence-web \
  python -m pytest packages/persistence-web/tests/test_knowledge.py -q
# Autonomous Knowledge Worker (KI-P4, ADR-0028) — pure question-merge + scheduler + tick/
# run_loop orchestration, plus KI-P5's (ADR-0029) optional WorkerControlPort/WorkerEventSink
# seams: disabled/manual-trigger/dynamic-interval tick behavior and cycle_started/completed/
# error event emission; zero external deps, no DB, no network (26 tests):
PYTHONPATH=packages/knowledge-intelligence:packages/knowledge-ontology:packages/knowledge-worker \
  python -m pytest packages/knowledge-worker/tests -q
# Knowledge Research adapters (KI-P2, ADR-0026) — KnowledgeGapResearchRunner's gap detection/
# research/storage, plus KI-P5's (ADR-0029) activity-timeline event emission
# (questions_loaded/gap_detected/source_searched/knowledge_discovered/item_saved/error), all
# against fake crawler/extractor/store doubles (24 tests):
PYTHONPATH=packages/domain:packages/tools:packages/llm:packages/knowledge-intelligence:packages/knowledge-research:packages/knowledge-research-adapters:packages/knowledge-worker \
  python -m pytest packages/knowledge-research-adapters/tests -q
# Knowledge Worker composition root (KI-P4, ADR-0028) — real data loading (no network) and
# environment-driven configuration/fail-fast paths, run_forever's stop/skip/tick/
# survive-an-exception semantics against a fake runner, and (KI-P5, ADR-0029) run-history
# recording after a cycle ran; no real DB/HTTP/LLM call in this suite (10 tests):
uv run pytest apps/worker/tests -q
# Run the real, always-on process (manual/ops verification — not part of the automated
# suite; see apps/worker/README.md):
#   DATABASE_URL=postgresql://postgres:postgres@localhost:5432/aigrc?schema=public \
#   OPENAI_API_KEY=sk-... uv run python -m grc_worker.knowledge_learning_loop

# AI Worker Control Center persistence (KI-P5, ADR-0029) — WorkerControlRepository/
# WorkerRunHistoryRepository/WorkerEventRepository against apps/web's live
# `worker_control`/`worker_run_history`/`worker_events` tables (needs a reachable Postgres
# with apps/web's migrations applied — apply 0019_worker_control.sql via
# `pnpm --filter web db:migrate`; skips cleanly otherwise; 5 tests):
PYTHONPATH=packages/domain:packages/tools:packages/persistence-web \
  python -m pytest packages/persistence-web/tests/test_worker_control.py -q
# AI Worker Control Center API (KI-P5, ADR-0029) — apps/api's routers/knowledge_worker.py:
# status/events/runs/reports/schedule/trigger, RBAC (owner/admin full control, auditor
# read-only, everyone else 403); needs a reachable Postgres with apps/web's migrations
# applied (skips cleanly otherwise; 9 tests):
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/aigrc?schema=public \
  uv run pytest apps/api/tests/test_knowledge_worker.py -q
# AI Worker Control Center frontend (KI-P5, ADR-0029) — apps/web's /ai-worker admin page
# (requireRoles("owner","admin")) plus its /api/knowledge-worker/* proxy routes; verified
# manually end-to-end in the browser this session (status/schedule-toggle/manual-trigger all
# round-tripped through Postgres); no automated eval suite added yet:
pnpm --filter @grc/web typecheck && pnpm --filter @grc/web lint

# Policy Intelligence API exposure (PI-P5, ADR-0022) — apps/api's web_runtime.py now
# registers Policy Hunter's/Policy Analyst's three Tools on the live Tool Registry and
# routers/policy_intelligence.py exposes them as GET /policy-intelligence/{obligations,
# coverage-gaps,policies/{id}/quality-review}; needs a reachable Postgres with apps/web's
# migrations applied (skips cleanly otherwise; 8 tests):
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/aigrc?schema=public \
  uv run pytest apps/api/tests/test_policy_intelligence.py -q

# Policy Intelligence frontend (PI-P6, ADR-0023) — apps/web's proxy to the PI-P5 endpoints
# (lib/policyIntelligence/service.ts) plus the /policy-intelligence workspace page. The one
# integration check exercises the real proxy against a real apps/api + Postgres and skips
# cleanly if apps/api isn't reachable (same convention as arabicAnalysis.eval.ts):
uv run uvicorn grc_api.app:create_app --factory --port 8000 &  # from the repo root
pnpm --filter @grc/web exec tsx tests/eval/policyIntelligence.eval.ts

# Lint / format
python -m ruff check packages/domain/grc_domain packages/services/grc_services \
  packages/persistence/grc_persistence packages/persistence/tests
python -m black --check packages/persistence

# Migration (offline render against Postgres; no DB connection needed)
cd packages/persistence && ALEMBIC_DATABASE_URL=postgresql+asyncpg://u:p@localhost/db \
  alembic upgrade head --sql | head
```

> When code and any document disagree, one of them is a bug — fix it and update this file.
