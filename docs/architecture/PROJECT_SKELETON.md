# Project Skeleton — AI GRC Assistant

> **Status:** Approved structure, **partially implemented** (as of 2026-06-27). This document
> defines repository *shape* only — no business logic itself. For what is actually built, the
> authoritative trackers are [`PROJECT_STATE.md`](../../PROJECT_STATE.md) and
> [`ARCHITECTURE_AUDIT.md`](./ARCHITECTURE_AUDIT.md); see §15 for the corrected fill-in state.
>
> This document defines the *physical shape* of the repository: every top-level folder,
> why it exists, and how it maps to a pillar in [CLAUDE.md](../../CLAUDE.md). It is meant
> to be read alongside CLAUDE.md — that file says *what we build and why*; this file says
> *where everything lives*. The goal is a structure that can live for 10+ years: new
> agents, tools, frameworks, and workspaces are **added at the edges**, never by surgery
> on the core.

---

## 1. Guiding rules for the structure

These rules decide where any new file goes. They are derived directly from CLAUDE.md.

1. **The folder layout mirrors the architecture layers.** Interfaces, Orchestrator,
   Agents, Tools, Services, Domain, Infrastructure each have an obvious home. If you can't
   tell which layer a file belongs to, the design is wrong — not the file.
2. **Dependencies point inward.** `apps/` may depend on `packages/`; `packages/` may
   depend on more-inward `packages/`; the **domain depends on nothing**. Enforced by
   project config, not by hope.
3. **Deployable units live in `apps/`; reusable capability lives in `packages/`.** An app
   is a thin process boundary (a server, a worker). The real logic lives in packages so it
   is testable and reusable across all six Tool callers.
4. **Everything extensible is a registry or a data folder, not a code edit.** New Tools,
   Agents, Frameworks, Connectors, and Prompts register themselves or are dropped in as
   data. The core control flow never grows an `if framework == "..."`.
5. **Polyglot, but cleanly split.** Python (backend/AI) and TypeScript (frontend/shared
   types) coexist in one monorepo. Each package declares its language and its boundary; no
   package mixes both runtimes.
6. **Config and secrets are data, never code.** Environment, framework definitions, and
   prompts are versioned artifacts outside the business logic.

---

## 2. Why a monorepo

We use a **single monorepo** rather than many repos because the platform is one product
with tightly-coupled contracts:

- **One source of truth for contracts.** The API schema, domain vocabulary, and event
  shapes are shared between the Python backend and the TypeScript frontend. A monorepo
  lets a contract change and its consumers move in one reviewable PR.
- **Atomic cross-cutting changes.** Adding a Tool may touch the registry, a service, a
  test, and the UI that surfaces it. One PR, one CI run, one review.
- **Uniform standards.** One set of lint/format/type/test gates (CLAUDE.md §22–24) applied
  everywhere, instead of drift across repos.
- **Clear dependency governance.** The inward-pointing dependency rule (CLAUDE.md §6) is
  enforceable when everything is visible to one build graph.

Tooling assumption: a JS workspace manager (pnpm/turbo) for the TypeScript side, and a
Python workspace (uv/poetry with editable installs) for the Python side. The two are
orchestrated by a top-level task runner (e.g. `make` / `turbo` / `nx`). Exact tools are an
ADR, not a constraint of this layout.

---

## 3. Top-level layout (the six required roots + supporting roots)

```
ai-grc-assistant/
├─ apps/          # deployable units: web, api, orchestrator, worker, workflow
├─ packages/      # reusable libraries: domain, services, tools, agents, rag, … , ui, contracts
├─ frameworks/    # compliance frameworks AS DATA (NCA ECC, SAMA, PDPL, ISO, NIST, …)
├─ prompts/       # versioned prompt artifacts (never inline in code)
├─ docs/          # architecture, ADRs, runbooks, onboarding
├─ infra/         # Infrastructure-as-Code (cloud, network, data, IAM)
├─ docker/        # Dockerfiles & compose for local + image builds
├─ config/        # environment & application configuration (data, not secrets)
├─ scripts/       # dev/ops automation scripts
├─ tests/         # cross-cutting e2e, mission, and AI evaluation suites
├─ .github/       # CI/CD workflows, PR templates, CODEOWNERS
├─ CLAUDE.md      # the engineering constitution (already approved)
├─ README.md
└─ <workspace manifests: pnpm-workspace.yaml, pyproject.toml, turbo.json, Makefile>
```

`apps/`, `packages/`, `docs/`, `infra/`, `docker/`, and `config/` are the six structures
you asked for. `frameworks/`, `prompts/`, `scripts/`, `tests/`, and `.github/` are the
supporting roots a 10-year platform needs — each justified below.

---

## 4. `apps/` — deployable units (thin process boundaries)

Each app is a **process**, not a place for logic. Apps wire packages together, expose a
boundary (HTTP, queue consumer, workflow worker, browser), and own nothing reusable.

```
apps/
├─ web/            # Next.js (App Router) — the Workspace-first UX (CLAUDE.md §18)
│  ├─ app/         # routes/segments (SHELL ONLY for now — no pages authored yet)
│  ├─ components/  # app-specific composition of packages/ui
│  ├─ features/    # workspace feature modules (missions, controls, risks, …) — empty shells
│  ├─ lib/         # client setup: query client, auth, api client (generated from contracts)
│  ├─ public/      # static assets, locales (i18n incl. Arabic/RTL)
│  └─ tests/       # component/integration tests
│
├─ api/            # FastAPI — the REST/GraphQL INTERFACE layer (CLAUDE.md §5 Interfaces)
│  ├─ src/         # routers, dependency wiring, middleware — calls Tools/Services only
│  ├─ openapi/     # generated/exported schema feeding packages/contracts
│  └─ tests/       # API contract & integration tests
│
├─ orchestrator/   # The AI ORCHESTRATOR service — the brain (CLAUDE.md §7)
│  ├─ src/         # mission planning, routing, memory, policy/guardrails, human gates
│  └─ tests/       # orchestration & policy tests
│
├─ workflow/       # Durable WORKFLOW ENGINE workers — runs missions reliably (CLAUDE.md §8)
│  ├─ src/         # workflow/saga definitions, activities = Tool invocations, retries
│  └─ tests/       # mission lifecycle / failure-path tests
│
└─ worker/         # Background & SCHEDULED JOBS runner (CLAUDE.md §9 caller #5)
   ├─ src/         # ingestion jobs, re-assessment schedules, digests, event consumers
   └─ tests/
```

**Why split into five apps instead of one?** Because they have different scaling, failure,
and security profiles. The API must be low-latency and stateless; the Orchestrator holds
mission control flow; the Workflow workers run long and must be durable; the job worker is
bursty and async. Separating them lets each scale and fail independently (CLAUDE.md §20),
while all of them call the **same Tools** in `packages/`.

**Rule:** if you are writing real logic inside `apps/`, stop — it belongs in a package.

---

## 5. `packages/` — reusable capability (where the system actually lives)

This is the heart of the platform. Packages are ordered here from **outermost (depends on
others)** to **innermost (depends on nothing)**, matching the inward dependency rule.

```
packages/
│  ── Python: AI & orchestration capability ────────────────────────────────
├─ agents/            # MULTI-AGENT layer (CLAUDE.md §11)
│  ├─ knowledge/      # Knowledge Agent (retrieval & grounding specialist)
│  ├─ policy/         # Policy Agent
│  ├─ compliance/     # Compliance Agent
│  ├─ risk/           # Risk Agent
│  ├─ report/         # Report Agent
│  ├─ workflow/       # Workflow Agent
│  ├─ base/           # shared Agent contract/base class, agent registry
│  └─ tests/
│
├─ tools/             # TOOLS — first-class units of business capability (CLAUDE.md §9)
│  ├─ registry/       # the TOOL REGISTRY (CLAUDE.md §10): registration, discovery, versions, authz
│  ├─ contracts/      # the Tool contract: typed I/O base, side-effect profile, idempotency
│  ├─ catalog/        # one folder per tool (e.g. analyze_control_gap/, map_frameworks/) — shells
│  └─ tests/          # tools tested DIRECTLY (CLAUDE.md §9 caller #6)
│
├─ rag/               # RAG subsystem (CLAUDE.md §12)
│  ├─ ingestion/      # intake, parsing, chunking, embedding, indexing pipeline
│  ├─ retrieval/      # query build, hybrid search, re-ranking, context assembly
│  ├─ interfaces/     # swappable embedder/vector-store/reranker interfaces
│  └─ tests/
│
├─ framework-engine/  # FRAMEWORK ENGINE — frameworks as DATA, not code (CLAUDE.md §13)
│  ├─ model/          # canonical framework model (framework→domain→control→requirement)
│  ├─ loader/         # loads definitions from /frameworks, validates, versions
│  ├─ mapping/        # cross-framework control-to-control mapping & coverage
│  └─ tests/
│
├─ llm/               # LLM PROVIDER ABSTRACTION (CLAUDE.md §4, §7)
│  ├─ providers/      # adapters (anthropic/, openai/, …) behind one interface
│  ├─ budgets/        # token/cost/latency budgets, retry, fallback
│  └─ tests/
│
│  ── Python: core platform ────────────────────────────────────────────────
├─ services/          # SERVICES LAYER (CLAUDE.md §14): coordinates domain + transactions
│  └─ tests/
│
├─ domain/            # DOMAIN LAYER — DDD bounded contexts (CLAUDE.md §15), PURE, zero framework deps
│  ├─ controls/       # each = aggregates, entities, value objects, domain events, invariants
│  ├─ policies/
│  ├─ risks/
│  ├─ evidence/
│  ├─ frameworks/     # framework domain concepts (distinct from the engine that loads data)
│  ├─ missions/       # Mission aggregate + Mission Lifecycle (CLAUDE.md §8)
│  ├─ tenancy/        # tenant & identity domain concepts
│  ├─ reporting/
│  └─ tests/
│
├─ persistence/       # INFRASTRUCTURE: repositories, ORM mappings, MIGRATIONS
│  ├─ repositories/   # repository implementations (no ORM leaks upward)
│  ├─ migrations/     # Alembic migrations (schema only — no models authored yet)
│  └─ tests/
│
├─ events/            # EVENT-DRIVEN ARCHITECTURE (CLAUDE.md §16)
│  ├─ bus/            # event bus interface + adapters (Kafka/NATS/Redis Streams)
│  ├─ schemas/        # domain event definitions (past-tense facts)
│  ├─ outbox/         # transactional outbox for reliable publish
│  └─ tests/
│
├─ plugins/           # PLUGIN ARCHITECTURE (CLAUDE.md §17): SDK + discovery/loading
│  ├─ sdk/            # interfaces a 3rd-party Tool/Agent/Framework/Connector implements
│  ├─ connectors/     # connector interfaces + anti-corruption layer slots
│  └─ tests/
│
├─ observability/     # logging, tracing, LLM-call audit, metrics (CLAUDE.md §19)
├─ security/          # authz primitives, tenant-scoping guards, secret access wrappers
├─ config/            # typed settings loader (reads /config + env/secret manager)
│
│  ── TypeScript: shared frontend capability ────────────────────────────────
├─ ui/                # shared design-system components (CLAUDE.md §18) — presentational only
├─ contracts/         # SHARED CONTRACTS: types/schemas generated from API/domain, used by web
└─ i18n/              # shared localization resources & RTL helpers
```

**Reading guide.** A request enters an app → calls a **Tool** (`tools/`) → which calls a
**Service** (`services/`) → which operates the **Domain** (`domain/`) → which persists via
**persistence/**. Agents (`agents/`) only ever act through `tools/`. The Orchestrator app
plans across agents and tools using the **registry** and the **framework-engine**. This is
exactly the layering of CLAUDE.md §5, made physical.

**Why `domain/` is innermost and pure.** It is the part that must survive framework
churn, model swaps, and vendor changes for a decade. It imports nothing from FastAPI,
SQLAlchemy, or any LLM SDK (CLAUDE.md §15). Everything else can be replaced around it.

---

## 6. `frameworks/` — compliance standards as data

This root is the physical expression of CLAUDE.md §13: **frameworks are data, not code.**
The `framework-engine` package *loads* and *interprets*; this folder *holds the
definitions*. Adding NCA ECC v3 or a brand-new regulator is a PR that touches **only this
folder** (plus mapping data) — never the engine and never control flow.

```
frameworks/
├─ schema/                 # the canonical definition schema all frameworks must satisfy
├─ nca-ecc/                # one folder per framework, versioned inside
│  ├─ v2.0/                # domains, controls, requirements, evidence expectations (data files)
│  └─ metadata.yaml        # id (framework:nca_ecc), region, language(s), status
├─ sama/
├─ pdpl/
├─ iso-27001/
├─ nist-csf/
├─ cis/
├─ cobit/
├─ coso/
└─ mappings/               # cross-framework control-to-control mappings (data, CLAUDE.md §13)
   ├─ iso-27001__nist-csf.yaml
   └─ nca-ecc__iso-27001.yaml
```

---

## 7. `prompts/` — versioned prompt artifacts

CLAUDE.md §5/§22 forbid inline prompts. Prompts are reviewable, versioned files, named
exactly as the convention requires (`control_gap_analysis.v3`).

```
prompts/
├─ agents/        # prompts grouped by agent (knowledge/, compliance/, …)
├─ tools/         # prompts a specific AI tool uses
├─ shared/        # shared system/guardrail fragments
└─ CHANGELOG.md   # why each prompt version changed (audit trail)
```

---

## 8. `docs/` — the institutional memory

```
docs/
├─ architecture/      # this file, the C4/diagrams, layer deep-dives
├─ adr/               # Architecture Decision Records (CLAUDE.md §23) — one file per decision
├─ onboarding/        # "first day" guide pointing at CLAUDE.md + this skeleton
├─ runbooks/          # operational playbooks (incident, rollback, data residency)
├─ api/               # generated API reference (when the API exists)
└─ frameworks/        # how-to: authoring a framework definition
```

Why a dedicated `adr/`: any change to the CLAUDE.md pillars, the Tool contract, the agent
roster, the Framework Engine model, or the Mission Lifecycle **requires an ADR**
(CLAUDE.md §23). This folder makes that process have a home.

---

## 9. `infra/` — Infrastructure as Code

```
infra/
├─ modules/           # reusable IaC modules (network, database, vector store, queue, …)
├─ environments/      # local / staging / production compositions (CLAUDE.md §23)
│  ├─ staging/
│  └─ production/
├─ iam/               # least-privilege roles & policies (CLAUDE.md §20)
└─ observability/     # tracing/logging/alerting infra wiring
```

Separate from `docker/`: `infra/` provisions *cloud* resources (the where-it-runs);
`docker/` builds *images and local environments* (the what-it-runs-in). Conflating them is
a common 10-year mistake.

---

## 10. `docker/` — images and local environment

```
docker/
├─ web.Dockerfile
├─ api.Dockerfile
├─ orchestrator.Dockerfile
├─ workflow.Dockerfile
├─ worker.Dockerfile
├─ base/                  # shared base images (python-base, node-base) for reproducibility
└─ compose/
   ├─ docker-compose.yml          # full local stack (db, pgvector, bus, apps)
   └─ docker-compose.deps.yml     # just dependencies for fast local dev
```

---

## 11. `config/` — configuration as data (no secrets)

```
config/
├─ default.yaml        # base settings
├─ local.yaml          # local overrides
├─ staging.yaml
├─ production.yaml
├─ policies/           # guardrail/budget policy definitions the Orchestrator enforces
└─ feature-flags/      # flag definitions (CLAUDE.md §23 — gradual rollout)
```

Secrets never live here — they come from the environment/secret manager (CLAUDE.md §22).
This folder holds only non-sensitive, environment-shaped configuration, read by
`packages/config`.

---

## 12. `scripts/` and `tests/`

```
scripts/
├─ dev/        # bootstrap, seed-frameworks, run-stack
├─ ci/         # lint/type/test/security-scan entrypoints used by .github
├─ db/         # migrate, reset (wraps Alembic — no models authored yet)
└─ release/    # versioning, changelog, deploy helpers

tests/
├─ e2e/        # end-to-end across apps (browser + API)
├─ missions/   # full Mission Lifecycle tests incl. human-gate & cancel paths (CLAUDE.md §8, §22)
├─ eval/       # AI EVALUATION suites: grounding/accuracy rubrics (CLAUDE.md §22)
│  └─ datasets/
└─ contract/   # cross-service contract tests (API ↔ web ↔ tools)
```

Package-local unit tests live **inside each package** (`packages/*/tests/`). The top-level
`tests/` root is only for **cross-cutting** suites that span multiple apps/packages — the
mission and evaluation tests that CLAUDE.md §22 makes mandatory.

---

## 13. Final folder tree (consolidated)

```
ai-grc-assistant/
├─ apps/
│  ├─ web/            { app, components, features, lib, public, tests }
│  ├─ api/            { src, openapi, tests }
│  ├─ orchestrator/   { src, tests }
│  ├─ workflow/       { src, tests }
│  └─ worker/         { src, tests }
│
├─ packages/
│  ├─ agents/         { knowledge, policy, compliance, risk, report, workflow, base, tests }
│  ├─ tools/          { registry, contracts, catalog, tests }
│  ├─ rag/            { ingestion, retrieval, interfaces, tests }
│  ├─ framework-engine/ { model, loader, mapping, tests }
│  ├─ llm/            { providers, budgets, tests }
│  ├─ services/       { tests }
│  ├─ domain/         { controls, policies, risks, evidence, frameworks, missions,
│  │                    tenancy, reporting, tests }
│  ├─ persistence/    { repositories, migrations, tests }
│  ├─ events/         { bus, schemas, outbox, tests }
│  ├─ plugins/        { sdk, connectors, tests }
│  ├─ observability/
│  ├─ security/
│  ├─ config/
│  ├─ ui/             (TypeScript)
│  ├─ contracts/      (TypeScript)
│  └─ i18n/           (TypeScript)
│
├─ frameworks/        { schema, nca-ecc, sama, pdpl, iso-27001, nist-csf, cis, cobit,
│                       coso, mappings }
├─ prompts/           { agents, tools, shared, CHANGELOG.md }
├─ docs/              { architecture, adr, onboarding, runbooks, api, frameworks }
├─ infra/             { modules, environments, iam, observability }
├─ docker/            { *.Dockerfile, base, compose }
├─ config/            { *.yaml, policies, feature-flags }
├─ scripts/           { dev, ci, db, release }
├─ tests/             { e2e, missions, eval, contract }
├─ .github/           { workflows, PR template, CODEOWNERS }
├─ CLAUDE.md
├─ README.md
└─ <workspace manifests>
```

---

## 14. How future developers extend the platform

The whole point of this layout: growth happens **at the edges**, by adding to a registry
or a data folder. None of the four flows below requires editing core control flow.

### 14.1 Add a new **Agent** (e.g. a Vendor-Risk Agent)

1. Create `packages/agents/vendor_risk/` implementing the shared **Agent contract** from
   `packages/agents/base/`.
2. Declare the Tools and data scopes it needs (least privilege) and **register** it in the
   agent registry.
3. Add its prompts under `prompts/agents/vendor_risk/` (versioned).
4. Add agent tests in `packages/agents/vendor_risk/tests/`.
5. The Orchestrator composes it into missions automatically — **no core change**
   (CLAUDE.md §11, §17). It acts only through registered Tools.

### 14.2 Add a new **Tool** (e.g. `assess_vendor_risk`)

1. Create `packages/tools/catalog/assess_vendor_risk/` implementing the **Tool contract**
   from `packages/tools/contracts/` (typed I/O, tenant/auth context, side-effect profile,
   idempotency if consequential).
2. The Tool calls a **Service** in `packages/services/` — never the DB or an LLM SDK
   directly.
3. **Register** it in `packages/tools/registry/` with name + version
   (`assess_vendor_risk.v1`), permissions, and cost/latency hints.
4. Add a **direct** Tool test in `tests/` (caller #6 — no UI/LLM needed).
5. It is now callable by all six callers (Orchestrator, API, UI, Workflow, Jobs, Tests)
   with no further wiring (CLAUDE.md §9, §10).

### 14.3 Add a new **Framework** (e.g. NCA ECC v3, or a new regulator)

1. Add `frameworks/<framework-id>/<version>/` with its definition files conforming to
   `frameworks/schema/` (domains → controls → requirements → evidence expectations).
2. Add `metadata.yaml` (stable id like `framework:nca_ecc`, region, languages, status).
3. Add cross-framework mappings under `frameworks/mappings/` as data.
4. The `framework-engine` loader picks it up; assessments can pin its version.
5. **Zero architectural change, zero code edit** — if it required code, the engine has a
   bug (CLAUDE.md §13).

### 14.4 Add a new **Workspace** (a new object-centric area of the UX)

1. Add a feature module under `apps/web/features/<workspace>/` (e.g. a Vendor-Risk
   workspace) composing components from `packages/ui/`.
2. Consume typed data through `packages/contracts/` (generated from the API) — the
   frontend never talks to the DB.
3. Surface the relevant **Tools/Missions** as first-class, navigable objects with their
   citations, confidence, and human gates (CLAUDE.md §18, §19).
4. Add localization (incl. Arabic/RTL) via `packages/i18n/`.
5. Add component/integration tests under `apps/web/features/<workspace>/`. The backend
   capability already exists as Tools — the workspace is a **view onto** them, not new
   business logic.

---

## 15. What is intentionally NOT in this skeleton yet

> **Update (2026-06-27):** this document describes the *original* approved skeleton. Several
> homes have since been filled. The authoritative, source-verified status is in
> [`PROJECT_STATE.md`](../../PROJECT_STATE.md) and
> [`ARCHITECTURE_AUDIT.md`](./ARCHITECTURE_AUDIT.md). The bullets below are corrected to match
> verified source so this document no longer contradicts the code.

Per the original approval gate, the skeleton defined **homes, not contents**. Current state:

- **Business logic — partially implemented.** The Domain and Application/Services folders are
  **no longer empty** (`packages/domain/grc_domain/`, `packages/services/grc_services/`); the
  Knowledge Extraction Engine abstractions exist (`packages/extraction/`).
- **No APIs** — `apps/api` still has no routers authored (unchanged).
- **Database models — implemented.** `persistence/` has 20 ORM models and a real Alembic
  migration (`0001_initial_schema.py`).
- **UI — a static prototype, not workspace pages.** `apps/web` has a presentation dashboard
  rendering hardcoded demo data (no backend wiring); the mission/workspace UX is not built.

Remaining homes are filled in small, reviewable PRs that satisfy the Definition of Done
(CLAUDE.md §24), in the order set by the Handbook §8 roadmap and
[`ARCHITECTURE_DECISION_LOG.md`](../../ARCHITECTURE_DECISION_LOG.md) (ADL-0001).

---

*Companion to CLAUDE.md. Propose changes to the structure via ADR + PR.*
