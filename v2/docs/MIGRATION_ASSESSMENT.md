# V1 → Platform Migration Assessment

> **What this is.** V1 is a **Spike that proved the product**, not the final application. This
> document governs how its results enter the real platform: it separates what the Spike *decided*
> from what the Spike *built*, and defines how, in what order, and until when we migrate.
>
> **What this is not.** Not a plan, not a roadmap, not a schedule. It says how a decision is made
> during the migration, and when we know we are done — never how to write the code.
>
> - **Status:** ✅ **Approved** (Product Owner, 2026-07-23) — treated as a **Reference Document**
> - **Reading order:** Principles → Facts → Map → Waves → Exit Criterion
> - **Companions:** [MIGRATION_MAP.md](./MIGRATION_MAP.md) (artifact → destination → action) ·
>   [V1_PRODUCT_DECISIONS.md](./V1_PRODUCT_DECISIONS.md) (the decisions themselves, source-independent)
> - **Related:** ADR 0052 (the Product API Host) · ADR 0053 (read models & projection) ·
>   ADR 0054 (the Application-layer contract) · [ROADMAP.md](./ROADMAP.md) ·
>   [execution/](./execution/) (the S1–S7 contracts whose acceptance criteria stay authoritative)

---

## 1. Migration Principles

Five rules govern every decision during the migration. On any disagreement, these are the reference.

1. **Migrate the decision, not the file.**
2. **Rebuild on the current platform, not on the Spike.**
3. **Never copy a development Adapter.**
4. **Anything that already exists in the real system is *wired*, never rebuilt.**
5. **Every screen is rewritten on the approved frontend host and its design system — no verbatim
   React is copied from the Spike.**

*Note on principle 5: the approved host is not yet decided (ADR 0052 deferred it — see §7, Open
Decision 1). The principle is phrased to hold either way.*

---

## 2. Facts

Observed directly in the repository. Every conclusion in this document must trace back to one of
these; disagreement means breaking a fact, not offering an impression.

| # | Fact | Reference |
|---|---|---|
| F1 | `create_app` composes `InMemoryMissionStore` by default | `v2/apps/grc-api/grc_api/app.py` |
| F2 | It composes `MissionEngine(store, EchoExecutor())`, and `EchoExecutor` returns `f"echo: {request.instruction}"` | `app.py` · `v2/packages/mission-engine/mission_engine/adapters.py:23` |
| F3 | It composes `InMemoryMissionListReadModel` and `InMemoryDocumentReadModel` | `app.py` |
| F4 | It composes `development_identity_provider()` — three fixed credentials mapped to tenants | `v2/apps/grc-api/grc_api/security.py` |
| F5 | `PostgresMissionStore` + Unit of Work + Transactional Outbox + Relay exist and are frozen; the package ships 3 `.sql` migrations and 12 test modules (86 tests per the ROADMAP) | `v2/packages/mission-store/` |
| F6 | `PostgresMissionListReadModel` and `PostgresDocumentReadModel` exist, each with `schema.py` and tests | `mission-read-model/…/postgres.py` · `document-read-model/…/postgres.py` |
| F7 | `RegistryExecutor` + `ToolRegistry` + five real tool packages exist, and `build_tool_backed_mission_runtime` composes them | `v2/packages/grc-assistant/grc_assistant/assembly.py` |
| F8 | **`grc-api/pyproject.toml` does not depend on `mission-store`, `mission-integration`, or `grc-assistant`** | `v2/apps/grc-api/pyproject.toml` |
| F9 | The Gap Assessment plan names three real tools, one per step (`framework_control_library` → `local_search` → `generate_text`) | `assistant-runtime/…/builtin/gap_assessment.py` |
| F10 | 12 of 18 REST contract endpoints are implemented. Missing: `PATCH /plan` · `POST /rerun` · `POST /resume` · `GET /deliverables` · `GET /frameworks` · `GET /frameworks/{id}` | `grc-api/grc_api/routers/` vs `REST_API_CONTRACT_V1.md` |
| F11 | `MissionRuntime.run_transition` builds connection + UoW + capture bus + engine **per transition**; `grc-api` holds one long-lived `MissionEngine` on `app.state` | `mission-integration/…/runtime.py` · `grc-api/…/app.py` |
| F12 | `mission-projection` is imported by no file; `grc-api/adapters.py` re-implements projection | repository-wide grep |
| F13 | The Spike contains **zero** test files | `v2/apps/mission-web-spike/` |
| F14 | `CURRENT_USER = { credential: "dev-approver-a", roles: [...] }` is hardcoded in frontend source and consumed by two hooks | `mission-web-spike/src/api/client.ts:209` |
| F15 | `timeAgo` is duplicated across 6 files; `titleCase` across 3 | grep |
| F16 | `SummaryStrip` fetches `page_size: 200` and counts statuses in the browser | `mission-web-spike/src/MissionsView.tsx` |
| F17 | The Spike README says "TEMPORARY · throwaway · Do not build product UI here" — seven product slices were built there | `mission-web-spike/README.md` · `execution/README.md` |
| F18 | `V1_POLISH.md` classifies frictions #6, #8, #9 as Echo artifacts, not defects, and defers re-verification until a real executor runs | `execution/V1_POLISH.md` |
| F19 | `apps/web` holds 413 TS files, `next-intl` with `ar.json`/`en.json`, `[locale]` routing, an edge auth gate in `middleware.ts`, and `@grc/ui` + `DESIGN_SYSTEM.md` | `apps/web/` |
| F20 | `_extract_text` decodes UTF-8 only, while `document-tools` (PDF/DOCX/XLSX) already exists | `grc-api/grc_api/document_adapters.py` |

### 2.1 Terminology — say this precisely

> **`grc-api` is a Product API that is currently composed with a Development Composition.**

This distinction must survive for whoever reads this a year from now:

| **Not a Spike — real and decided** | **Is a Spike — the composition only** |
|---|---|
| The API itself (ADR 0052) | The composition in `create_app` |
| The endpoints and routers | The Executor (`EchoExecutor`) |
| The contracts and schemas | The Storage (in-memory adapters) |
| The Application layer (ADR 0054) | The Identity (`DevelopmentIdentityProvider`) |
| The read models as a design (ADR 0053) | The `dev.py` seeding |

### 2.2 Conclusion

From F1–F9 and F11: the larger part of the work appears to be **wiring the backend before rebuilding
the frontend** — because the real adapters already exist and are tested but unwired (F5, F6, F7),
because their absence is structural rather than configurational (F8), and because the product today
executes plans that name real tools using an echo executor (F2 + F9).

From F11 specifically: **wiring the durable path is an architectural decision, not a wiring task** —
the two composition models are incompatible.

---

## 3. What the Spike holds — the four-way classification

### 3.1 Product decisions

The Spike's real yield. Independent of React and Vite; migrated as decisions and re-expressed in the
target. Enumerated in full, with sources, in [V1_PRODUCT_DECISIONS.md](./V1_PRODUCT_DECISIONS.md).

### 3.2 Architecture decisions

**Already decided and present — honoured, not migrated:** ADR 0052 (single composition-root API
host) · ADR 0053 (read models are the CQRS read side; projection is an Application-layer, synchronous
concern) · ADR 0054 (commands hold policies; CQRS enforced by dependencies; typed `CommandResult`;
typed errors → HTTP codes; `CommandContext` first) · injectable composition seams throughout
(`create_app(...)`) · a single identity seam (`IdentityProvider`, bearer as transport only,
`require_tenant` fail-closed).

**Proven by the Spike and to be adopted as patterns in the real frontend:**

- **REST is the frontend's only contract** — the ViewModel never exceeds the API boundary: no
  aggregate, no DB row, no ORM. This was the Spike's one stated rule, and it held.
- **A framework-agnostic Presenter / ViewModel layer** owning load-error state, polling, and
  permissions, keeping views declarative.
- **A Presenter Registry for polymorphic results** — the frontend mirror of
  `DeliverableBuilderRegistry`; a new result type is an *addition*, never a page edit.
- **Poll only while active** — polling stops on a terminal state; never a blocking wait.
- **Grouping is presentation** — no `GET /collections`; the client groups a flat document list.
- **`Idempotency-Key` on create** — a double submit never creates two missions.

### 3.3 Prototype only — never migrated

The Vite host and its config; committed build output (`dist/`, `tsconfig.tsbuildinfo`); the
hand-rolled `Nav` union used as navigation; `styles.css` (self-described "low-fidelity … no visual
identity"); the hardcoded `CURRENT_USER` credential (F14); six copies of `timeAgo` and three of
`titleCase` (F15); the browser-side `SummaryStrip` count (F16); `localStorage`-based onboarding; the
`START_DWELL_MS` sleep; the string-surgery helpers `prettyTitle` and `cleanReason`; client-side
`evidenceCount`; and the `dev.py` seeding with its scripted executors. The Spike ships no tests
(F13), so nothing migrated from it carries a safety net.

### 3.4 Already in the real system — wire it, do not rebuild it

**Backend / platform.** `mission-engine` · `mission-store` (Postgres + UoW + Outbox + Relay) ·
`mission-integration` (`MissionRuntime`) · `event-bus` · the pipeline packages · `tool-registry` ·
`pipeline-tool` (`RegistryExecutor`) · `framework-library` · `document-tools` · `search-tools` ·
`llm-tools` · `assistant-runtime` (six real capabilities) · `grc-assistant` (the composition that
replaces Echo) · `mission-application` · `deliverables` · `knowledge-runtime` · `retrieval-engine` ·
the `grc-api` routers, schemas, errors, and security · **and the Postgres read-model adapters, which
are written, tested, and simply not wired.**

**Frontend.** Everything in `apps/web` the Spike lacks entirely (F19): real authentication,
Arabic/RTL and locale routing, the design system, multi-organization support, server-state tooling,
error reporting, and migrations.

### 3.5 Needs re-implementation, not copying

The seven screens (rewritten on the approved host); the label layer (becomes `ar.json` + `en.json`
entries — **every label needs an Arabic translation that does not exist today**); navigation (real
URLs, so back, deep-link, and share work); the API client (real session, not a hardcoded bearer); the
Presenters (pattern kept, transport delegated to the host's server-state tooling); polling; the
Result presenter registry; a single localized relative-time formatter; the Trust Bar's evidence count
(moved server-side into the read model); **role enforcement — a genuine gap, since the Spike only
hides buttons while ADR 0054 §1 requires authorization inside the command**; the onboarding flag
(moved onto the account); and the backend fixes that delete the client's string surgery.

---

## 4. Migration Waves

Not a plan and not milestones. **A definition of each wave's end state**, so everyone knows when to
stop.

| Wave | Goal | Done when |
|---|---|---|
| **0** | Decisions become a reference independent of the files | Every entry in the Map's *Decision* column has a line in `V1_PRODUCT_DECISIONS.md` — i.e. deleting the Spike tomorrow would lose no decision |
| **1** | The backend becomes real | `EchoExecutor`, `InMemory*`, and `development_identity_provider` appear nowhere in the production path · a mission survives a process restart · a Gap Assessment returns coverage derived from real customer evidence · frictions #6/#8/#9 re-verified (F18) |
| **2** | The API is complete | 18/18 REST contract endpoints · `prettyTitle` / `cleanReason` / `evidenceCount` / the `SummaryStrip` count are gone from the client because the server supplies them · an Approve by a non-Approver returns 403 **from the command**, not from a hidden button |
| **3** | The first real screen | Missions live on the approved host with a real URL (back · share · deep link), in Arabic and English, behind a feature flag — and with no line of React copied from the Spike |
| **4** | The whole product | The seven screens pass their existing execution contracts (S1–S7 + V1 Polish) · `dev.py` deleted · `mission-projection` resolved · **`mission-web-spike` is deletable with nothing broken and nothing lost** |

### 4.1 Gates — opened by decisions, not by code

| Gate | Precedes | Decision |
|---|---|---|
| ~~**A**~~ | Wave 1 | ✅ **CLOSED 2026-07-23** — [ADR 0055](../../docs/adr/0055-v2-mission-execution-lifecycle-ownership.md), Accepted: *the transaction boundary is the **command**; execution sits outside it.* The investigation also produced discovery **C2** (a whole `execute()` inside one transaction would span every tool and LLM call — invisible under Echo). **Wave 1 may open** |
| **B** | Wave 3 | The frontend host decision ADR 0052 deferred — the decision that makes principle 5 readable literally |

### 4.2 The one ordering constraint

**Wave 3 does not begin before Wave 1 closes.**

Waves 1 and 2 may overlap. But starting the frontend on an echo backend is *precisely* what produced
the current situation (F2 + F17 + F18): a convincing product standing on `dev.py`. Beginning the UI
before Wave 1 closes rebuilds the Spike on a nicer host — and breaks principle 2 without anyone
noticing.

### 4.3 Wave 1 — sequence and commit granularity

Owner-set constraints (2026-07-23, at Gate A closure). Constraints, not a plan: they bound *how* the
wiring may land, not what to write.

1. **The durable path is tested first.** Every suite today proves the Development Composition — the
   very thing Wave 1 replaces. The first safety net must prove the **production** composition;
   until it exists, no wiring is measurable and a green suite means nothing about the new path.
2. **Then, in this order:** wire the read models → replace the store → replace the executor.
3. **Never two components in one commit.** *Wire Read Models*, *Replace Store*, and *Replace
   Executor* are three separate commits. Landing them together makes a failure unattributable —
   store, executor, or projection — and forfeits cheap revert. Each commit must stand alone, carry
   its own value, and be revertible on its own.

---

## 5. Risks of a direct copy

Conclusions, each traceable to a fact.

| # | Risk | Basis |
|---|---|---|
| R1 | **You would ship the echo demo.** The product's realism comes from `dev.py`'s scripted seeding; copying the UI first yields a beautiful, empty product | F2, F18 |
| R2 | **Generational mixing** — dropping Spike React into the existing web tree puts a hardcoded bearer client beside a real session system, and makes the deferred host decision by accident | F19, ADR 0052 |
| R3 | **Two incompatible composition models for the same mission** — naive wiring yields either a dual write or an untransacted mission | **F11** |
| R4 | **Silent loss of tenant isolation / auth** — a hardcoded `dev-approver-a` reaching a deployment authenticates every visitor as an Approver on `tenant-a`; and role guards are declared but unenforced | F4, F14 |
| R5 | **Arabic/RTL cannot be retrofitted cheaply** — every Spike string is an English literal, several are string-surgery output, and the layout assumes LTR | F19 |
| R6 | **Copying re-creates duplication the system already resolved** | F12, F15 |
| R7 | **No test net travels with the Spike**, and backend suites stay green on in-memory adapters while behaviour changes underneath | F13 |
| R8 | **Presentation compensating for backend gaps hardens into contract** | F16, F20 |
| R9 | **The Spike's charter was already breached once** — treating the resulting files as an asset repeats that error at a larger scale | F17 |
| R10 | **Committed build artifacts** would be carried into the real tree | `dist/` |

---

## 6. Open decisions — reserved to the Product Owner

1. **The frontend host** — `apps/web` (reuses auth, Arabic/RTL, the design system, and
   multi-organization support — the four most expensive things, all absent from the Spike; and the
   frontend consumes REST only, so it imports no old package) versus a new `v2/apps/web` (a clean
   generational boundary, at the cost of rebuilding all four). *Recommendation: `apps/web`.*
2. **How `grc-api` composes the durable path** (R3 / F11) — Gate A; deserves an ADR before any code.
3. **The fate of the previous generation** (`apps/api`, `packages/*`) and of the existing `apps/web`
   routes that V1's four-area information architecture does not include: replaced, or coexisting?

---

## 7. Exit Criterion

> The migration ends when every decision in the Migration Map is represented inside the real system,
> no decision depends on `mission-web-spike` existing, and **no production path depends on the
> Development Composition**. At that point deleting the Spike is cleanup, not a product change.

The middle clause closes a real hole: without it, every decision could be migrated and the Spike
deleted while the product still runs on Echo — the criterion satisfied literally, the migration
unfinished in fact.
