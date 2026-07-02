# ARCHITECTURE_DECISION_LOG.md — AI GRC Assistant

> The **Architecture Decision Log (ADL)** is the consolidated record of approved
> architectural decisions and their evolution (Handbook §12.17). It complements — does not
> replace — the detailed per-decision records in [`docs/adr/`](./docs/adr/) (the MADR-style
> ADRs governed by CLAUDE.md §23). Where an ADL entry needs a full rationale, it links to or
> calls for a matching ADR.
>
> **Governance rules that bind this file:**
> - Handbook §12.17 — *"Implementation alone does not create ADL entries."*
> - Handbook §12.19 — *"Only approved architectural decisions enter the ADL. Recommendations
>   remain recommendations until approved."*
> - Handbook §12.20 — every future decision respects prior approved decisions unless
>   explicitly superseded.
>
> **Therefore:** every entry below was *discovered during the 2026-06-27 architecture audit*
> and is recorded with status **Proposed — pending Product Owner approval**. None is yet
> "Accepted." On approval, the Product Owner (or Chief Architect) flips the status to
> **Accepted**, and any entry tagged *(needs ADR)* gets a companion file under `docs/adr/`.

**Entry format (Handbook §12.18):** Decision Identifier · Date · Decision · Reason ·
Alternatives · Impact · Reversibility — plus a **Status** field for governance tracking.

**Status legend:** `Proposed` (recommendation, not yet binding) · `Accepted` (approved,
binding) · `Superseded` · `Rejected`.

---

## ADL-0001 — Authoritative implementation roadmap

- **Date:** 2026-06-27
- **Status:** **Proposed — pending Product Owner approval**
- **Decision:** Adopt the Handbook §8 **"Knowledge-First"** roadmap (Shared Kernel → Core
  Domain → Knowledge Domain → Knowledge Database → Knowledge DB Integration → Knowledge
  Extraction Engine → Framework Engine → Knowledge Graph → Search → Retrieval → RAG → AI
  Agents) as the **single authoritative implementation order**. The divergent roadmap in
  `PROJECT_STATE.md` §10 is retired and reframed as a backlog of cross-cutting enablers
  (composition root, eventing relay, Tool Registry, API) sequenced *within* the
  Knowledge-First milestones.
- **Reason:** Two locked but conflicting roadmaps existed (audit §7.1). The Handbook is the
  project constitution and declares *"No phase may be skipped"* (§8) and "Roadmap Lock"
  (§12.22). A single source of truth is required before any milestone proceeds.
- **Alternatives:** (a) adopt the PROJECT_STATE layered roadmap instead — rejected: it
  contradicts the constitution; (b) keep both — rejected: they conflict on what comes next.
- **Impact:** Sets the "current milestone" to **M6 Knowledge Extraction Engine**. Reframes
  the already-built Application layer for non-knowledge contexts as *ahead of order* (see
  ADL-0007).
- **Reversibility:** High — documentation/sequencing change only; no code impact.

---

## ADL-0002 — Knowledge Extraction Engine as a hexagonal ports subsystem *(needs ADR)*

- **Date:** 2026-06-27
- **Status:** **Proposed — pending Product Owner approval** (ratifies existing source)
- **Decision:** Recognize `packages/extraction/grc_extraction/` as a first-class subsystem:
  a **pure hexagonal port/abstraction layer** (10 ABC ports, profiles, registry, artifacts)
  with **no** concrete adapters in the core, distinct from the `extraction` *domain* bounded
  context. Concrete adapters (PDF/OCR/segmenter/classifier/extractor/mapper/ingestion) are to
  live in outer infrastructure packages.
- **Reason:** This subsystem is already implemented in source (Handbook milestone 6) but is
  not covered by any of the 16 existing ADRs and is absent from `PROJECT_STATE.md`. Handbook
  §12.17 says implementation alone does not create a decision record — so it must be logged
  and ratified.
- **Alternatives:** (a) fold extraction into the RAG package — rejected: extraction precedes
  and is independent of retrieval in the roadmap; (b) put adapters in the engine core —
  rejected: violates the "AI plugs in later without coupling" goal stated in the package.
- **Impact:** Establishes the contract surface M6 must complete; relates to ADR-0008
  (Knowledge & RAG) and ADR-0010 (Plugin architecture). **Requires a new ADR-0017.**
- **Reversibility:** High today (ports only, no adapters); falls as adapters land.

---

## ADL-0003 — Fourteenth domain bounded context: `extraction`

- **Date:** 2026-06-27
- **Status:** **Proposed — pending Product Owner approval** (ratifies existing source)
- **Decision:** Record that the Domain layer contains **14** bounded contexts, not 13 — the
  added context is `extraction` (`packages/domain/grc_domain/extraction/`), with its own
  entities, enums, events, value objects, repositories, and domain tests.
- **Reason:** `PROJECT_STATE.md` §4 stated "13 bounded contexts"; source inspection found 14.
  Corrects documentation drift (audit §10).
- **Alternatives:** None — this is a factual correction.
- **Impact:** PSR and context map updated; supports ADL-0002.
- **Reversibility:** N/A (records an existing fact).

---

## ADL-0004 — Tenant column realized as `organization_id`

- **Date:** 2026-06-27
- **Status:** **Proposed — pending Product Owner approval** (ratifies existing source)
- **Decision:** The multi-tenant scoping column is **`organization_id`** (the tenant
  aggregate is `Organization`), the concrete realization of CLAUDE.md §21's generic
  `tenant_id` guidance. Every tenant-scoped read/list/save is scoped by it; default deny.
- **Reason:** Already implemented and tested in persistence (`test_tenant_isolation.py`) and
  documented informally in `PROJECT_STATE.md` §8; promoted to a logged decision so future
  layers (API/auth/RAG) inherit one canonical tenancy key.
- **Alternatives:** literal `tenant_id` column — rejected: the domain's tenant aggregate is
  `Organization`, so `organization_id` is the faithful ubiquitous-language name.
- **Impact:** Binding for all future tenant-scoped tables and queries; relates to ADR-0014.
- **Reversibility:** Low once more tables/APIs depend on it (currently 20 tables already do).

---

## ADL-0005 — "Completed" defined by Evidence-First (tests + review)

- **Date:** 2026-06-27
- **Status:** **Proposed — pending Product Owner approval**
- **Decision:** A milestone or layer is **"Completed"** only with (1) source code, (2)
  passing automated tests at the appropriate level, and (3) architectural review — per
  Handbook §12.11 and §12.31–12.34. Layers with code but no tests are recorded as
  **"Implemented / Unverified."** Consequently the Application/Services layer (0 tests) and
  the 12 untested Core-Domain contexts are downgraded from "✅ complete" to *Implemented /
  Unverified* until tests exist.
- **Reason:** `PROJECT_STATE.md` marked layers "complete" without tests, which Evidence-First
  forbids (audit §3, §5, §10). Prevents documentation from advancing milestone status.
- **Alternatives:** keep "complete = code exists" — rejected: contradicts the constitution.
- **Impact:** PSR statuses corrected; creates a test-debt backlog (Mission aggregate, all
  service handlers) that gates future "Completed" claims.
- **Reversibility:** High (a status-definition policy).

---

## ADL-0006 — Mission repository is part of the `UnitOfWork` contract *(corrective)*

- **Date:** 2026-06-27
- **Status:** **Proposed — pending Product Owner approval** (no implementation yet)
- **Decision:** Declare that the `MissionRepository` is part of the application's
  `UnitOfWork` abstraction: the `UnitOfWork` ABC (`grc_services/shared/unit_of_work.py`)
  must expose a `missions` property, matching the nine `uow.missions` call sites in
  `missions/handlers.py` and the concrete `SqlAlchemyUnitOfWork.missions`.
- **Reason:** The ABC currently declares 16 repositories but omits `missions`, so the port
  does not satisfy its own consumers — a Liskov/contract violation and a likely `mypy`
  failure (audit §7.4, §8). This is an architectural seam, hence an ADL entry rather than a
  silent fix.
- **Alternatives:** access the Mission repository outside the UoW — rejected: breaks the
  single transactional boundary and the six-callers/Tools model.
- **Impact:** Closes the port/adapter hole; unblocks honest type-checking of the mission
  use cases. **Implementation deferred until approved** (this log changes nothing in code).
- **Reversibility:** High (additive interface method).

---

## ADL-0007 — `apps/web` classified as an out-of-roadmap presentation prototype

- **Date:** 2026-06-27
- **Status:** **Proposed — pending Product Owner approval**
- **Decision:** Treat `apps/web` (≈3,562 LOC, static compile-time data, no backend wiring)
  as an explicitly **out-of-roadmap presentation/investor prototype**. Freeze further UI
  build-out until the roadmap reaches its UI phase (post-M12), **unless** the Product Owner
  formally sanctions it as a parallel demo track with its own milestone.
- **Reason:** UI appears nowhere in the Handbook §8 order; building it ahead introduces
  breadth against "Roadmap Lock" (§12.22) and risks stakeholders mistaking hardcoded scores
  for working product (audit §7.3, §9).
- **Alternatives:** delete the demo — rejected: it has stakeholder value and is honestly
  labeled; continue expanding it freely — rejected: violates roadmap lock.
- **Impact:** Web work paused/scoped; documentation must label the demo as non-functional
  data.
- **Reversibility:** High (a scoping/labeling decision).

---

## ADL-0008 — Extraction adapters live in an outer package; production ingestion deferred

- **Date:** 2026-06-27
- **Status:** **Proposed — pending Product Owner approval** (records an implementation boundary)
- **Decision:** Two parts. (a) The concrete extraction adapters live in a new **outer
  infrastructure package** `packages/extraction-adapters` (`grc_extraction_adapters`), which
  depends on `grc_extraction` + `grc_domain` and is depended on by nothing — keeping
  `grc_extraction` a pure ports/coordinator layer per [ADL-0002](./ARCHITECTURE_DECISION_LOG.md).
  (b) The M6 milestone is **complete with a reference in-memory `KnowledgeIngestionPort`
  adapter**; the **production Postgres ingestion adapter is deferred** to a follow-on that first
  re-aligns the M5 knowledge persistence to the refactored M3 `KnowledgeSource` aggregate.
- **Reason:** The architecture mandates adapters in outer packages (not in `grc_extraction`). The
  production ingestion adapter requires the Knowledge persistence (model/mapper/migration/services)
  to be import-healthy, but it currently is not: `KnowledgeSource` dropped
  `source_type`/`ingestion_status` (now `knowledge_domain`) while the `knowledge_sources`
  table/model/migration and `grc_services/knowledge` + `grc_persistence/mappers/knowledge` still
  use the old shape. Re-aligning them is a **DB schema/migration change that re-opens "Completed"
  M5** and involves design choices — a Product Owner decision, not a silent rewrite.
- **Alternatives:** (a) put adapters inside `grc_extraction` — rejected: violates its pure-ports
  contract; (b) guess-rewrite the M5 schema now to ship the production adapter — rejected:
  re-opens a completed milestone and risks an incorrect aggregate shape without PO direction.
- **Impact:** M6 engine is complete and runnable end-to-end via the reference adapter. Unblocking
  the production adapter requires an approved M5 knowledge-persistence re-alignment (schema
  migration + model + mapper + repository + services). Until then the engine persists via the
  reference adapter only.
- **Reversibility:** High for (a); the deferred (b) is gated on the M5 decision.

---

## ADL-0009 — LLM / embedding provider selection & data-residency policy (gates M11–M12)

- **Date:** 2026-06-27 · **Resolved:** 2026-06-27
- **Status:** **Accepted — OpenAI** (Product Owner selected the OpenAI provider; `OPENAI_API_KEY`
  supplied via `.env`). Option (a): build the provider abstraction + real OpenAI adapters and
  complete M11–M12. The key is read from the environment (`os.environ["OPENAI_API_KEY"]`); it is
  never hardcoded, logged, or committed. Automated gates use deterministic **fake** providers
  (CLAUDE.md §22: mock LLM/vector calls in unit tests); the real OpenAI adapter is exercised only
  by opt-in live/eval suites. The data-egress implication (compliance text may be sent to OpenAI)
  is accepted by this decision and should be reflected in customer-facing data-processing terms.
- **Decision needed:** Which **LLM provider + model** powers grounded generation (M11 RAG) and
  agent reasoning (M12); which **embedding provider + model (and vector dimension)** powers
  semantic retrieval (M10's vector half) and the pgvector schema; plus the operating policy:
  **credentials/secret management, cost & latency budgets, rate limits, prompt-versioning, and —
  critically — the data-residency / data-egress policy** governing whether and how customer
  compliance data may be sent to an external model.
- **Why it cannot be made from the repository:** CLAUDE.md §4 gives a *code-level* default
  ("default to the latest Claude models") and mandates a swappable provider abstraction, but the
  repo contains **no** provider credentials, no embedding-model/dimension choice, no cost/latency
  policy, and no data-egress decision. For a GRC platform, sending the customer's compliance data
  to an external LLM is a **security/privacy/compliance decision** (CLAUDE.md §1: "Customer
  compliance data is among the most sensitive data they own"; §20: tenant isolation, data
  residency). This is precisely a product/architectural decision that must be made by the Product
  Owner, not inferred.
- **What is NOT blocked (already delivered decision-free):** the entire knowledge pipeline up to
  retrieval — Extraction Engine (M6), Framework Engine (M7), Knowledge Graph (M8), Search (M9),
  and **keyword** Retrieval (M10) — all pure, tested, and runnable without any model.
- **Options for the Product Owner:** (a) approve **Anthropic Claude** (per the CLAUDE.md default)
  for generation + a named embedding model, with an explicit data-egress policy and budgets — I
  then build the provider abstraction + the real adapters behind it and complete M11–M12; (b)
  approve a **provider abstraction + a deterministic offline reference generator/embedder only**
  (no external egress) so M11–M12 ship architecturally-complete-but-non-production, with the real
  provider deferred — analogous to [ADL-0008](./ARCHITECTURE_DECISION_LOG.md); (c) a different
  provider/policy.
- **Reversibility:** the provider sits behind an abstraction, so the *provider* choice is
  reversible; the **data-egress policy** is not lightly reversible once customer data has been
  sent externally.

---

*Living log. Entries are `Proposed` until the Product Owner approves them; approval flips the
status to `Accepted` and triggers any required `docs/adr/` companion. Supersede, never
silently edit, an `Accepted` entry.*
