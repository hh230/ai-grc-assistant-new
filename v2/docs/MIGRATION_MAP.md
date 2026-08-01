# Migration Map — Artifact → Decision → Destination → Action

> **The mechanical half of the migration.** For every artifact that exists today, this says where it
> goes and which **one** of seven actions applies to it. There is no "port some of it and adjust the
> rest" — an artifact gets exactly one action.
>
> Governed by [MIGRATION_ASSESSMENT.md](./MIGRATION_ASSESSMENT.md) (principles, facts, waves, exit
> criterion). The decisions in the *Decision* column are stated source-independently in
> [V1_PRODUCT_DECISIONS.md](./V1_PRODUCT_DECISIONS.md).
>
> **Status:** ✅ Approved (Product Owner, 2026-07-23) · **Coverage:** all 30 Spike files + the
> Development Composition

---

## Action vocabulary — seven, closed

| Action | Meaning |
|---|---|
| **Wire** | Already exists, tested and ready — connect it via a composition argument. No new code |
| **Replace** | A development adapter is swapped for its real counterpart, which already exists |
| **Rewrite** | The screen is written afresh on the approved host; only the decision migrates |
| **Rebuild** | A pattern is re-expressed using the target platform's tooling |
| **Translate** | Becomes translation entries (ar + en) |
| **Fix-at-source** | The patch is deleted and the cause is fixed in the backend |
| **Delete** | No decision, no destination |

---

## C1 — Frontend: `v2/apps/mission-web-spike` (30 of 30 files)

| Spike artifact | Decision it proved | Destination | Action |
|---|---|---|---|
| `App.tsx` | Four Product Areas · Dashboard is the landing · back keeps context | Layout + a real router | Rewrite |
| `MissionsView.tsx` | Clickable summary strip · filters · whole row is the click target · an empty state that guides | Missions list route | Rewrite |
| ↳ `SummaryStrip` | The counter is an entry point to filtering | Server-side counts (read model) | Fix-at-source |
| `mission/MissionDetailView.tsx` | One Work Surface · tabs are views of one state · Decision Card · Trust Bar · "Execution", not "Findings" | Mission detail route | Rewrite |
| `mission/presenter.ts` | ViewModel pattern · poll only while active · `canApprove` | Detail hook + server-state tooling | Rebuild |
| `mission/useMissionDetail.ts` | A thin bridge holding no logic | same as above | Rebuild |
| `result/ResultPage.tsx` | Trust Bar → content → Export · explain zero evidence | Result route | Rewrite |
| `result/presenters.tsx` | **Presenter Registry** — a new result type is an addition | Result presenters module | Rebuild |
| `result/useResult.ts` | A completed result is static — no polling | Server-state tooling | Rebuild |
| `decisions/DecisionsView.tsx` | The queue's unit is a decision · a card sufficient to decide in five seconds · outcome banner · falls back to recent decisions | Decisions route | Rewrite |
| `decisions/presenter.ts` | `canDecide` · records the decision's effect · refresh removes the item | Decisions hook | Rebuild |
| `decisions/useDecisions.ts` | — | same as above | Rebuild |
| `knowledge/KnowledgeView.tsx` | Collections, not files · a focused upload panel · an empty state that explains | Evidence route | Rewrite |
| `knowledge/collections.ts` | Six kinds in display order · "Unclassified" is shown but never chosen · empty collections hidden | Evidence feature + translations | Rebuild + Translate |
| `knowledge/presenter.ts` | Poll only while ingesting | Evidence hook | Rebuild |
| `knowledge/useKnowledge.ts` | — | same as above | Rebuild |
| `dashboard/DashboardView.tsx` | Attention, not analytics · the fixed order · every card has a journey · the trust caveats | Dashboard route | Rewrite |
| `dashboard/useDashboard.ts` | — | Server-state tooling | Rebuild |
| `newmission/NewMissionView.tsx` | Two steps · a review station · no Draft · the framework is shown, not picked | New mission route | Rewrite |
| `newmission/missionTypes.ts` | The six types and their blurbs | Mission Catalog (server) + translations | Fix-at-source + Translate |
| `onboarding/FirstRunOverlay.tsx` | One-time orientation with two entry paths | Component + a flag on the account | Rewrite |
| **`labels.ts`** | **Product language ≠ implementation language** | `messages/ar.json` + `messages/en.json` | **Translate** |
| `api/client.ts` (types + methods) | REST is the only contract · `Idempotency-Key` · export returns bytes | API client module | Rebuild |
| ↳ `CURRENT_USER` | — | The real authentication session | **Delete** |
| `styles.css` (445 lines) | — | The approved design system | **Delete** |
| `timeAgo` ×6 | Relative-time phrasing | One localized formatter (`Intl.RelativeTimeFormat`) | Rebuild |
| `titleCase` ×3 | — | — | Delete |
| `prettyTitle` · `cleanReason` · `evidenceCount` | — | API returns `type`/`scope` and a clean reason; the count moves into the read model | **Fix-at-source** |
| `main.tsx` · `index.html` · `package.json` · `tsconfig*` · `vite.config.ts` | — | — | Delete |
| `dist/` · `tsconfig.tsbuildinfo` | — | — | Delete + untrack |
| `README.md` | The Spike's charter and its one rule | Quoted in the decisions document | Keep-as-reference |

---

## C2 — Backend: the Development Composition

Every destination in this table **already exists**. This is the part principle 4 governs: wire, do
not rebuild.

| Artifact | Real destination (already exists) | Action |
|---|---|---|
| `EchoExecutor` | `RegistryExecutor`, via `build_tool_backed_mission_runtime` | **Replace** |
| `InMemoryMissionStore` | `PostgresMissionStore` + UoW + Outbox | Replace — **needs Gate A (F11)** |
| `InMemoryMissionListReadModel` | `PostgresMissionListReadModel` | **Wire** |
| `InMemoryDocumentReadModel` | `PostgresDocumentReadModel` | **Wire** |
| `TenantKnowledgeBase` (in-memory corpus) | pgvector via `retrieval-engine` | Wire |
| `DevelopmentIdentityProvider` | A session / OIDC provider — the same seam | Replace |
| `grc_api/dev.py` + `_ScriptedExecutor` + `_CitingExecutor` + `_counter_clock` | — | Delete (after Wave 1) |
| `_extract_text` (UTF-8 only) | `document-tools` (PDF/DOCX/XLSX) | Wire |
| Vite proxy `/v1` | A route handler or rewrite on the approved host | Rebuild |
| `mission-projection` (orphaned — F12) | Wired in place of `adapters.py`, or removed | **Decide** |
| Approver role enforcement | Inside the `mission-application` commands (ADR 0054 §1) | **Build — a real gap** |
| The 6 missing endpoints (F10) | `grc-api/grc_api/routers/` | Build |

---

## C3 — Do not touch: already real

`mission-engine` · `mission-store` · `mission-integration` · `event-bus` · the pipeline packages ·
`tool-registry` · `pipeline-tool` · `framework-library` · `document-tools` · `search-tools` ·
`llm-tools` · `assistant-runtime` (the six capabilities) · `grc-assistant` · `mission-application` ·
`deliverables` · `knowledge-runtime` · `retrieval-engine` · the `grc-api` routers, schemas, errors,
and security — **and the whole of `apps/web`: authentication, Arabic/RTL, the design system, and
multi-organization support.**
