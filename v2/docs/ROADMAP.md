# Rasheed V2 — Roadmap

> **Purpose.** A single, durable map of what V2 *is*, what is **done and frozen**, and what is
> **deliberately deferred** — so a handoff or a return after months starts from a coherent picture,
> not from reading every slice. This is a living index; each line points to the ADR that owns the
> real decision.
>
> **Last updated:** 2026-07-23 · **State:** V2 **Platform** and **Product Core** frozen; **V1 FINISHED**
> — slices S1–S7 + the V1 Polish slice all closed; a Zero-Assumption Product Review walked it as a new
> user and every fix was language/narrative/feedback, none architectural. Next is **V2, on a stable base**.
> **Real Tools layer complete** (framework-library, document-tools, search-tools, llm-tools — all
> consuming the frozen Platform). **All four Capabilities are real *and coherent***: ISO Controls, Risk
> Assessment, Policy Generator, Vendor Review — the composites **chain** (gather → synthesise) via
> **inter-step context (ADR 0051)**. **Product roadmap P1 + integration DONE:** runtime per-tenant
> ingestion (`knowledge-runtime`) + the capabilities now **read the customer's own data** — each
> composite gathers via `local_search` over the tenant knowledge base (`build_grc_orchestrator` /
> `build_grc_tool_registry`), proven E2E (Risk reads customer evidence, Policy reads customer
> guidance, Vendor reads vendor evidence; tenant isolation fail-closed). The system can now work on
> **the customer's own knowledge** (their ingested *documents* — not yet structured entities: assets,
> users, CMDB, cloud posture, IAM, inventory), not just the general library. **P3 in progress:** the
> standalone `deliverables` package turns a completed mission into structured, exportable output — a
> generic audit-ready `Deliverable` (sections + provenance) and the flagship **Gap Matrix — Evidence
> Mapping** (`control ↔ status ↔ evidence`, coverage %), exported to **Markdown, DOCX, and PDF**.
> (Named *Evidence Mapping*, not "assessment": the deterministic status is *evidence found in the
> corpus*, not a compliance attestation — the LLM `compute_gap` step is the assessment narrative.)
>
> **⏸ AUTONOMOUS ENGINEERING PAUSED HERE (2026-07-20).** PDF export was the **final autonomous
> engineering slice**. The project has reached the boundary between **Platform Engineering** (done —
> objective, verifiable) and **Product Design** (next — subjective, product/UX/security decisions with
> no single correct answer). No further implementation begins until the product is designed and
> approved. See **[PRODUCT_DESIGN_HANDOFF.md](./PRODUCT_DESIGN_HANDOFF.md)**. Do **not** start the REST
> API, Workspace/UI, Authentication, RBAC, Sessions, Dashboards, Notifications, Background Workers, the
> deliverable selector, or any new capability/tool autonomously — these shape the product and are
> human-led.
>
> **▶ Product Design underway — [PRODUCT_SPEC_V1.md](./PRODUCT_SPEC_V1.md) is APPROVED (2026-07-20) and
> is now the highest reference in the project.** Governance: *product leads code* — no API/UI/workflow
> is built or changed unless the spec changes first. Positioning: **"AI GRC Workspace powered by AI
> Missions"**; primary persona **GRC Practitioner**; V1 ships **exactly the six existing capabilities**,
> no new ones. Implementation begins only after the V1 screen flows are agreed and the API is derived
> from them (build order in [PRODUCT_DESIGN_HANDOFF.md](./PRODUCT_DESIGN_HANDOFF.md) §7).
>
> **Design docs (the derivation chain):** [PRODUCT_SPEC_V1.md](./PRODUCT_SPEC_V1.md) (approved) →
> [CONCEPTUAL_DOMAIN_MODEL_V1.md](./CONCEPTUAL_DOMAIN_MODEL_V1.md) (the product-language ↔ Core
> contract; its **§3 Gaps** is the design-derived engineering backlog — Mission-list/Deliverables-index
> read ports, Documents store, Dashboard read-models, pgvector persistence, Auth + RBAC enforcement,
> connectors/async/notifications) → [INFORMATION_ARCHITECTURE_V1.md](./INFORMATION_ARCHITECTURE_V1.md)
> (approved; 3-layer **Product Areas** → Activities → Navigation + validation checklist + scalability
> rule; nav derived only from areas + global activities) →
> [INTERACTION_PRINCIPLES_V1.md](./INTERACTION_PRINCIPLES_V1.md) (approved; 10 behavioral tie-breakers) →
> [SCREEN_FLOWS_V1.md](./SCREEN_FLOWS_V1.md) (approved; New Mission · Mission Detail · Deliverable View —
> each a **state machine** mapping to the frozen Mission Runtime) →
> [REST_API_CONTRACT_V1.md](./REST_API_CONTRACT_V1.md) (approved; derived from flow **events** not
> resources; ends with the backend backlog = Domain-Model §3 gaps) →
> [WIREFRAMES_V1.md](./WIREFRAMES_V1.md) (**APPROVED**; low-fidelity **Views over the state machine**;
> per-view *user question* + ID line + 9-section template; ≤1 primary decision; delete-test; Mission
> Detail = Work Surface, Trust Bar on Deliverable, Knowledge in GRC-evidence language, new Mission
> Created view) →
> [DESIGN_REVIEW_CHECKLIST_V1.md](./DESIGN_REVIEW_CHECKLIST_V1.md) (**APPROVED**; the design-review
> constitution: Gate 0 derive-don't-create + Gates 1–7 + Severity 🔴🟠🟡🔵 + Approval block; every
> new/changed View must pass it, like pytest for UX). **← Product Design Foundation COMPLETE (9 docs).**
> Enforced as a process by [PRODUCT_DEVELOPMENT_PROCESS.md](./PRODUCT_DEVELOPMENT_PROCESS.md) (development
> constitution: route each change to the highest Foundation layer it touches, approve the doc, then code;
> **Architecture & Product Freeze** anti-drift rule; "the product drives the code").
>
> **🧊 Product Design Foundation — FROZEN (2026-07-22).** Implementation is now the derivative, per
> [V1_EXECUTION_PLAN.md](./V1_EXECUTION_PLAN.md): enabling layer (Read Models · Auth+Tenant · Document
> Store — the Domain §3 gaps, no RBAC expansion yet) → **vertical slices** (1 Mission List · 2 Mission
> Detail · 3 Deliverable · 4 Knowledge · 5 Dashboard · 6 Approvals · 7 New Mission). **Each slice starts
> from an Execution Contract** ([docs/execution/](./execution/) — the acceptance-first bridge layer:
> `Execution Contract → Backend → API → Frontend → Acceptance Verification`, not starting from Read
> Models), then is reviewed via the Design Review Checklist. **S1 ✅ CLOSED** (Mission List:
> mission-read-model + mission-projection + v2/apps/grc-api + temp mission-web-spike). **S2 ✅ CLOSED**
> (2026-07-22 — Mission Detail / Work Surface: read View Model + the frozen Application layer
> [ADR 0054: policies · CQRS-by-dependency · CommandContext · Ports · MissionCommand template] +
> approve/reject commands/adapters/endpoints + a frontend Presenter→Client layering; **retry redefined
> as re-run→S7** via the Freeze rule when the Core proved FAILED terminal). **S3 ✅ CLOSED**
> (2026-07-22 — the Result: the frozen Application-layer language [ADR 0054 + **Application Contract
> Freeze**: `DeliverableProvider · FrameworkProvider · Exporter/ExportService · DeliverableBuilder
> Registry`] · a Gap Assessment Result with real coverage over the `deliverables` package · MD/DOCX/PDF
> export · a frontend `ResultPresenterRegistry`; evidence-first, "Result" not "Deliverable"). **S4 ✅
> CLOSED** (2026-07-22 — Knowledge = **Evidence Collections**: a new `document-read-model` [in-memory +
> Postgres, tenant-scoped fail-closed, `list_collections`] · `GET`/`POST /v1/documents` with
> `knowledge-runtime` ingestion + a **Document Projection** [`DocumentIngestionService` composition
> adapter] · a frontend Knowledge view [collections → open → documents, Upload, status pills]; the
> **Reality Gate caught its 4th design error pre-commit** [`evidence_kind` + `size` added to the REST
> Contract's `Document` via the Freeze rule]; owner review: `Other` → **Unclassified**).
>
> ✅ **FOUNDATION PHASE COMPLETE (S1–S4)** — these four slices built the system's *language*, not just
> features: S1 Read Models · S2 Application layer + contract vocabulary · S3 Result + Builder/Presenter
> registries · S4 Evidence + the Reality Gate. ▶️ **PRODUCT EXPANSION PHASE starts at S5**: slices now
> *speak* that language: each Execution Contract opens with a **Foundation Reuse** block, and the
> Retrospective records a **Foundation Reuse Ratio** + a one-line **New Component Justification** per new
> component (guards 5–7; the ratio's *why*, cutting against both re-invention and rigidity — "every new
> component is justified," never "new is bad"). Seven guards total: Product/Architecture/Application
> Freeze · Reality Gate · Foundation Reuse · Reuse Ratio · New Component Justification. **S5 ✅ CLOSED**
> (2026-07-23 — Dashboard "what needs my attention": a computed-on-read **DashboardProjection**
> [no table/projector] composing a **MissionSummaryProvider** over the reused mission-read-model + an
> independent **CoverageRollupProvider** over the reused ResultQuery · `GET /v1/dashboard` [a Projection
> read, added to §4] · a frontend Dashboard landing [attention-first; Waiting = primary CTA; Coverage
> *snapshot* clickable → Gap Assessments]; **first Product-Expansion slice — used the S1–S4 language
> without reinventing it** [Reuse ≈ 73%, New 4 all justified, no new stored projection/write path]). The
> first slice the owner reviewed "as a product, not a feature." **S6 ✅ CLOSED** (2026-07-23 — Decisions
> = "what decisions are waiting for me?": a new **ApprovalQueueProjection** [computed-on-read over
> mission-read-model + the store, incl. recent-decided history] · reuses `GET /v1/approvals` **and the
> S2 approve/reject command + Decision card UNCHANGED** · a frontend Decisions view [decision cards, not
> mission rows; Review-evidence + Open-Mission; context-preserving back]; **the first slice with NO
> architectural or contract change — the whole decision is reused**; Reuse ≈ 72%, New 5 all justified).
> Proved the phase thesis: **"Product Expansion adds questions before it adds behavior"** (S5/S6 = new
> question → new read, no new command/aggregate/domain). **S7 ✅ CLOSED** (2026-07-23 — New Mission =
> "what work should we start?": the first slice that *adds behavior* — `CreateMissionCommand` +
> `StartMissionCommand` (Template Method REUSED) over a `MissionDefinitionProvider` [type → `(goal,
> plan)` via the catalog] + `MissionCreator` [the Core `create`+`plan` seam] · `POST /v1/missions`
> [Idempotency-Key] + `POST /v1/missions/{id}/run` · a **Mission Created review station** [summary +
> plan → **Start**, no Draft, no auto-run]. **The Reality Gate's best result yet: it disproved the
> "we need a Draft" assumption *from the Core's code* before any was written** — the Core has no DRAFT
> state, `create()` returns a real Mission, so the form stayed Presentation State. Reuse ≈ 61% [New 7 ·
> Reused 11 — deliberately the lowest: the write side is new, the read side fully reused]).
>
> ✅ **V1 PRODUCT SURFACE COMPLETE (S1–S7).** Every screen answers exactly one product question
> ([V1_ONE_QUESTION_REVIEW.md](./V1_ONE_QUESTION_REVIEW.md)). *Why* V1 has this shape — the six
> deliberate refusals (no Draft · Result≠Deliverable · Dashboard-Projection≠God-Endpoint · Evidence
> Collections≠Documents · Decisions≠Approvals · questions-before-behavior) — is told as a short story
> in [WHY_V1_LOOKS_THE_WAY_IT_DOES.md](./WHY_V1_LOOKS_THE_WAY_IT_DOES.md).
>
> ✅ **V1 FINISHED (2026-07-23).** A **Zero-Assumption Product Review** walked the whole product as a new
> user; almost every friction was **language / narrative / feedback**, none architectural. One final
> **V1 Polish** slice ([execution/V1_POLISH.md](./execution/V1_POLISH.md) — *not a feature, not S8*)
> closed them, frontend-only: the product now speaks one language (Result not Deliverable, Decisions not
> Approvals, Running not Executing, ISO not Iso, via a shared label map), a first-use overlay answers
> "where do I begin?", zero-evidence results say why, a decision reports its human effect, and a Gap
> Assessment states the framework it assesses against (shown, not a picker — V2). The trust "bug" (#9)
> was proven a C2 (echo-executor) artifact, not a defect. The project has moved from *forming the
> system* to *polishing the product*. **Next is V2, on a stable base** — no rebuild required.

---

## The two layers

- **Platform (the AI pipeline)** — Phases 1–14.8. The pure, synchronous, provider-agnostic core:
  retrieval → context → prompt → generation → validation, with pipeline contracts, the AI
  Orchestrator composition root, the Event Bus + pipeline audit, and provider adapters. *Complete.*
- **Product (missions)** — Phase 15+. Everything that turns the platform into governed, auditable
  units of GRC work: the Mission Engine, its durable store, the transactional outbox/delivery path,
  human approval, and the integration runtime that wires them end-to-end. *Core complete.*

---

## Completed & frozen

| Area | Package(s) | ADR | Status |
|---|---|---|---|
| **AI Platform pipeline** (retrieval→context→prompt→generation→validation) | `retrieval-engine`, `context-builder`, `prompt-orchestrator`, `generation-engine`, `answer-validation`, `ai-orchestrator`, `pipeline-contracts` | 0035–0039 | ✅ Frozen (Phases 1–14.8) |
| **Event Bus + audit + provider adapters** | `event-bus`, `pipeline-tracing`, adapters | 0039 | ✅ Frozen |
| **Persistence mechanism** (sync psycopg3 + raw parameterized SQL + `.sql` migrations) | — (policy) | **0045** (reconciles 0012) | ✅ Accepted |
| **Mission Engine** (aggregate + lifecycle + two ports + events) | `mission-engine` | 0042 | ✅ Accepted — implemented |
| **Mission Store** — Slices 1–4 (persistence, idempotency, Unit of Work, Transactional Outbox) | `mission-store` | 0043 | ✅ Accepted — frozen |
| **Integration Runtime** (composition root: Engine→Store→UoW→Outbox→Relay→Delivery→Audit) | `mission-integration` | — (glue over 0042/0043) | ✅ Frozen |
| **Human Approval** — Slice 1 (state), Slice 2 (approve/reject + events), Slice 3 (resume orchestration) | `mission-engine`, `mission-store`, `mission-integration` | 0044 | ✅ Accepted — implemented (S1–3) |

**Quality bar at freeze:** all V2 mission-layer suites green against real PostgreSQL
(event-bus 35 · mission-engine 76 · mission-store 86 · mission-integration 12 = **209**); `ruff` and
`mypy --strict` clean on all source; **0** `TODO`/`FIXME` in code.

---

## Applications (Phase 1+) — built *on top of* the frozen Core, as consumers

The Core is frozen, so new value is delivered as **applications that consume `MissionRuntime`**, not
as features inside the Core. Every GRC "application" is a set of **Mission types** reached through the
Assistant, not a separate stack.

| Phase | Application | Shape | ADR | Status |
|---|---|---|---|---|
| **1** ⭐ | **AI GRC Assistant** — the gateway that turns a request into the right Mission (**Capability Catalog → Mission Catalog** · Session · Conversation · `AssistantRuntime`) | Product-layer package `assistant-runtime` consuming `MissionRuntime` | **0046** | 🟢 **Slices 1–3 done** (Architecture · Capability & Mission Catalog · **First Capability: Simple Question**, full loop green E2E, 24 tests) |
| **1a** | **Simple Question** — the first, built-in capability (single read-only step) | `assistant_runtime/builtin/` capability + Mission type | 0046 (Slice 3) | 🟢 Done |
| **1b** | **Risk Assessment** — the first *composite* capability, now **real**: `collect_context → assess_risk → generate_report`, every step a grounded `run_pipeline` pass (cited, not echo) | A Capability + Mission type in `builtin/` | **0047** | 🟢 **Real & coherent** — gather→synthesise, chained via ADR 0051, proven E2E |
| 1c | **Vendor Review** — real composite: `identify_supplier_controls` (framework-library, ISO A.5.19–A.5.23) + `assess_vendor` (grounded `run_pipeline`, cited) | Capability + Mission type in `builtin/vendor_review.py` | (no ADR — consumer) | 🟢 **Real & coherent** — controls+context→assessment, chained (ADR 0051), E2E |
| 1d | **ISO Controls** — the first capability backed by a **real tool**: its step routes (via `PlanStep.tool`, ADR 0048) to the Framework Library control-lookup tool and returns real ISO 27001 controls | Capability + Mission type in `builtin/iso_controls.py` | (no ADR — consumer) | 🟢 **Done** — E2E green through the real `RegistryExecutor` (no Echo) |
| 1e | **Policy Generator** — real composite: `identify_controls` (framework-library, cited ISO controls) + `draft_policy` (grounded `run_pipeline`, cited) | Capability + Mission type in `builtin/policy_generator.py` | (no ADR — consumer) | 🟢 **Real & coherent** — controls+guidance→draft, chained (ADR 0051), E2E |
| 1f | **Gap Assessment** ⭐ — the flagship: `identify_controls` (framework, *required*) + `gather_evidence` (`local_search`, the customer's *actual* evidence) + `compute_gap` (`generate_text`, coverage vs. gaps) | Capability + Mission type in `builtin/gap_assessment.py` | (no ADR — consumer) | 🟢 **Real** — framework + **customer evidence** → gap, E2E |

*Ordering (2026-07-17 ruling): build **3–4 real capabilities first** (Risk → Vendor → ISO → Policy),
each a small MVP with its own short **capability ADR** (0047 is the template), then return to the
Assistant's **Conversation Runtime / Response Layer / streaming / Session UX** (ADR 0046 Slices 4–6)
— designed on real usage, not assumptions. Each capability is a new Capability + Mission type in the
catalogs (ADR 0046 §4), not new plumbing.*

**Execution Platform — already exists and is frozen (correction, 2026-07-17).** The real
`ExecutionPort` and Tool Registry were built in Phase 15 (steps 2–3): `tool-registry`
(`ToolRegistry`/`ToolSpec`/`Tool`) and `pipeline-tool` (`RegistryExecutor` — the frozen-port adapter
that resolves a step → Tool via the Registry — plus `PipelineTool`, the first real tool). The
earlier "prerequisite / until it lands" wording was inaccurate. **Step A (done):** the new
`grc-assistant` composition package wires `RegistryExecutor` + `ToolRegistry` into the Assistant's
`MissionRuntime` (`build_tool_backed_mission_runtime`), proven E2E — a Simple Question now returns a
**grounded pipeline answer, not an echo**. **Step B — per-step tool selection — is done and frozen
(ADR 0048, 2026-07-20):** the additive `PlanStep.tool` / `StepRequest.tool` fields, the engine
pass-through, the `RegistryExecutor` honour, and the codec round-trip all shipped, backward-compatible
(`tool=""` ⇒ today's single-tool behaviour), with a multi-tool plan routing `collect → assess → report`
each to its own tool end-to-end. **Real GRC tools have started (Phase 3):**

- **ADR 0049** — the shared `ToolStepResult` tool-step contract (and the generic `PAYLOAD_INSTRUCTION`
  key) moved to `tool-registry`, the pure package every tool depends on, so a **leaf tool speaks the
  contract without the LLM/orchestrator stack**. Additive to `tool-registry`, neutral to
  `pipeline-tool` (public API unchanged). Frozen.
- **ADR 0050 — `framework-library`, the first real GRC tool.** Frameworks as data (CLAUDE.md §13):
  `FrameworkLibrary` loads framework definitions from JSON; `ControlLibraryTool` is a deterministic,
  read-only lookup (by code / theme / title keyword) returning matched control ids as provenance.
  Bundled: the **complete ISO/IEC 27001:2022 Annex A** (93 controls). Runtime deps = `tool-registry`
  + `pipeline-contracts` only (no LLM). A mission returns real ISO controls through the real
  `RegistryExecutor`, the step named by `PlanStep.tool`. Frozen.

**More frameworks shipped as data (no code change, no ADR — a Tool/data addition):** `framework:cis`
(CIS Critical Security Controls v8, 18 controls) and `framework:nist_csf` (NIST CSF 2.0, 22 categories
themed by Function) now load from `framework-library/data/` alongside ISO 27001 — proving the §13
claim with real content (framework-library: 28 tests).

**First real capability wired (2026-07-20):** the **ISO Controls** capability
(`assistant_runtime/builtin/iso_controls.py`) resolves to a Mission whose step routes — via
`PlanStep.tool` (ADR 0048) — to the Framework Library tool and returns **real ISO 27001 controls**,
proven E2E through the real `RegistryExecutor` (grc-assistant `build_grc_tool_registry` now assembles
both the Pipeline Tool and the Control Library tool). No new layer, no ADR — a pure consumer of the
frozen platform.

**Document tools shipped (2026-07-20) — `document-tools` package:** three real read-only tools
`read_pdf` / `read_docx` / `read_excel` that **consume the frozen `knowledge-importer` parsers** (no
re-implementation). Each reads one document from under a path-traversal-safe document root and returns
the extracted text as a `ToolStepResult`; failure is fail-safe (`ok=False`). Proven E2E through the
real `RegistryExecutor` against real PDF/DOCX/XLSX files (13 tests). No LLM, no Core change.

**Search tools shipped (2026-07-20) — `search-tools` package:** `local_search` (lexical),
`vector_search` (semantic), `hybrid_search` (fused) — all **wrap the frozen `retrieval-engine`** (no
re-implementation). Each maps the step instruction to a **tenant-scoped** `RetrievalQuery`, runs the
engine, and returns cited results as a `ToolStepResult`; tenant isolation is fail-closed (10 tests).

**LLM tool shipped (2026-07-20) — `llm-tools` package:** `generate_text` **wraps the frozen
generation stack** — it builds a provider-agnostic `LLMRequest` and calls an injected
`GenerationProvider` (the `generation-engine` Claude/Gemini/Ollama/OpenAI adapters, or the
`GenerationEngine` around one). Raw generation for drafting/summarizing (no citations, by design;
grounding is the Pipeline/Search tools' job). Fail-safe on provider error. 9 tests. No SDK, no Core.

**Embeddings — already exists in the Platform (correction, rule 7, 2026-07-20):** the roadmap listed
"Embeddings" as a tool to build, but the embedding providers already exist in `knowledge-importer`
(`EmbeddingProvider` port + `LocalDeterministicProvider` + `OpenAIEmbeddingProvider`) and are consumed
by the ingestion pipeline (indexing) and, as the query embedding, by semantic **`vector_search`**. A
raw-embedding *mission-step* tool has no coherent consumer (a vector is not a step output; semantic
retrieval is `vector_search`). **Not rebuilt** — consumed where it belongs.

**Corrected order (2026-07-20 ruling) — do NOT jump to Integrations after Real Tools:**

1. **Real Tools** (in-platform, consume-not-rebuild) — ✅ framework-library, document-tools,
   search-tools, llm-tools; Embeddings already in the platform. *No missing tool blocks the
   capabilities.*
2. **Real Capabilities** — ✅ **done (2026-07-20):** every capability is real, driving existing real
   tools E2E through the real `RegistryExecutor`: **ISO Controls** (framework-library), **Risk
   Assessment** (3× grounded `run_pipeline`), **Policy Generator** (framework-library + grounded
   `run_pipeline`), **Vendor Review** (framework-library + grounded `run_pipeline`). No echoes, no
   stubs. Capability→tool names single-sourced in `assistant_runtime/builtin/tool_names.py`.
3. **External Integrations** (Jira, ServiceNow, Microsoft, Google) — **only after** the capabilities
   are real (they now are), and **only when an existing Workflow actually needs one** (a real
   consumer), never pre-emptively. No integration without a capability that consumes it. *Nothing in
   the current capabilities requires an external system yet, so no integration is built.*

### Inter-step data flow — RESOLVED (ADR 0051, 2026-07-20)

Previously a fixed limitation: mission steps ran independently and the app layer was forbidden to fake
a work-around. A real need landed (coherent composite capabilities), so it was solved **in the Core, the
proper way** — **ADR 0051**: an additive, transient `StepRequest.prior_results` carries the completed
steps' output to the next step; `RegistryExecutor` renders it into `PAYLOAD_PRIOR_CONTEXT`; the
`generate_text` tool synthesises *from* it. No persistence change, fully backward-compatible.

**Consequence for capabilities — they now chain (gather → synthesise):**

- **Risk Assessment**: `collect_context` (grounded `run_pipeline`) → `assess_risk` (`generate_text`,
  from the evidence) → `generate_report` (`generate_text`, from evidence + assessment).
- **Policy Generator**: `identify_controls` (framework) + `gather_guidance` (`run_pipeline`) →
  `draft_policy` (`generate_text`, from the controls + guidance).
- **Vendor Review**: `identify_supplier_controls` (framework) + `gather_vendor_context`
  (`run_pipeline`) → `assess_vendor` (`generate_text`, from the controls + context).

Each is proven **coherent** E2E in `grc-assistant` (the synthesis step's output visibly contains the
prior steps' text). Tool selection rule stands: `run_pipeline` for grounded gather, `generate_text` for
synthesis *from* gathered material.

## Platform review — Real Tools & Real Capabilities complete (2026-07-20)

A full pass over the repo before Enterprise Features. **The end-to-end product path is real:** a
request → the Assistant → a Capability → a Mission → real tools through the frozen `RegistryExecutor`
→ real, cited GRC output. No echoes, no stubs anywhere in the capability path.

**Real Tools (each an independent package consuming the frozen Platform — no Core change, no ADR):**

| Package | Tool(s) | Wraps / source | Tests |
|---|---|---|---|
| `pipeline-tool` | `run_pipeline` | AI Orchestrator (grounded RAG: retrieve→generate→validate→cited) | 18 |
| `framework-library` | `framework_control_library` | frameworks-as-data (ISO 27001:2022 · CIS v8 · NIST CSF 2.0) | 28 |
| `document-tools` | `read_pdf` · `read_docx` · `read_excel` | `knowledge-importer` parsers (path-traversal-safe) | 13 |
| `search-tools` | `local_search` · `vector_search` · `hybrid_search` | `retrieval-engine` (tenant-scoped, fail-closed) | 10 |
| `llm-tools` | `generate_text` | `generation-engine` providers (raw generation) | 9 |

*Embeddings* already exist in the Platform (`knowledge-importer` `EmbeddingProvider` +
`LocalDeterministic`/`OpenAI`), consumed by ingestion and `vector_search` — **not** rebuilt.

**Real Capabilities (all in `assistant-runtime/builtin/`, consumers only):** ISO Controls · Risk
Assessment · Policy Generator · Vendor Review — each drives real tools E2E (proven in `grc-assistant`).
`tool_registry` 27 · `assistant-runtime` 43 · `grc-assistant` 10 green.

**What remains before "V1 / Production" (nothing started unless noted):**

1. **External Integrations** — Jira · ServiceNow · Microsoft · Google. Deferred **by policy**: build
   one only when a real Workflow consumes it (§ Applications, ordering rule). None required yet.
2. **Enterprise Features** — RBAC (tool `required_roles` is declared but unenforced today; the
   authorization layer is a real gap), Scheduler, Notifications (Email/Slack), Background Workers,
   Metrics, Dashboards, Admin Portal, Audit Portal. These are the next major phase.
3. **Product surfaces** — REST API, Workspace UI, a Human-Approval service (the Core supports the
   gate; no UI/API yet).
4. **Known Core limitations (fixed decisions — Core ADR only when a real need lands):** no inter-step
   data flow (above); LWW-not-OCC, single-worker relay, no mission lease/scheduler (ADR 0043); Human
   Approval Slice 4 / advanced approval (ADR 0044).
5. **Production readiness** — Docker · Kubernetes · CI/CD for the v2 packages · monitoring · security
   review · performance/scaling · disaster recovery.

**CI note:** the v2 packages are per-package `uv` projects (their own `.venv`), **not** wired into the
repo-root CI (`.github/workflows/ci.yml` covers the V1 tree). Wiring v2 into CI is part of Production
readiness (item 5).

## Next / deferred (nothing started)

Each item is **already recorded as deferred** in the ADR named — this table just gathers them so the
backlog is visible in one place. Ordering is indicative, not committed.

### Human Approval — Slice 4 (Advanced Approval) — ADR 0044
- Multiple approvers / quorum · timeout · escalation · expiry · SLA · reject-and-replan.
- A dedicated **service-principal identity** for `ApprovalRequest.requested_by` (today the sentinel
  `"system"`), and the candidate **rename** of that field (`request_origin` / `requested_by_principal`)
  — a payload-shape change (version bump), tracked in ADR 0044 → *Future ADRs*.
- **Approver authorization (RBAC):** whether a principal *may* approve becomes a first-class policy —
  its own ADR at the orchestrator policy layer, not the aggregate.

### Durable / concurrent mission execution — ADR 0043 (assumptions 1–2, §10, §12)
- **Mission lease** (single-writer-per-mission across processes) — the prerequisite for durable
  multi-worker execution; today single-writer is guaranteed by ADR 0042's synchronous drive.
- **Enforced optimistic concurrency (OCC)** — the `revision` column + aggregate version already
  pre-pay the schema cost; enabling it extends the frozen port/aggregate → a new ADR.
- **Scheduler** — driving re-assessments / timeouts / deferred resumes on a schedule.

### Transactional Outbox — beyond Slice 4 — ADR 0043-S4 Rev.3
- **Retry / dead-letter / `attempts`** · **pruning / retention** · **multi-worker relay**
  (`FOR UPDATE SKIP LOCKED`). The relay is single-worker, at-least-once, no retry today.

### Reads & recovery — ADR 0043 (§2, §12)
- A **list / recovery read interface** ("this tenant's non-terminal missions") as an *additive*
  interface — never a change to the three-method `MissionStorePort`.

### Cross-cutting (no ADR yet — open, deliberately)
- **Unified durable audit projection.** Today there are two in-memory projections for two bounded
  contexts — pipeline (`event_bus.AuditTrailBuilder`) and mission (`MissionAuditSink`). This is
  **accepted as normal** (two projections for two contexts); **no ADR is opened** unless/until we
  decide to *unify* or *persist* audit. Listed here only so the choice is visible, not forgotten.
- **Product surfaces** — REST API, Workspace UI, notifications (Email/Slack), Human Approval service.
  All explicitly out of scope for the Core; they consume the frozen packages, they don't change them.

---

## Documentation state

- **ADRs** are status-reconciled with reality (0042/0043/0044 = *Accepted — implemented*; 0045 closes
  the ADR-0012 persistence contradiction). The ADR index ([docs/adr/README.md](../../docs/adr/README.md))
  is the source of truth for statuses.
- **Package READMEs** reflect the shipped behaviour (Human Approval implemented; Mission Store Slices
  1–4 frozen).
- **Known, tracked debt:** the `"system"` requester interim (ADR 0044); LWW-not-OCC (ADR 0043 §10);
  single-worker relay (ADR 0043-S4); pre-existing lint debt in `event-bus/tests` (41 × E501).
- **Technical debt — capability ↔ retrieval-strategy coupling (recorded 2026-07-20).** Composite
  capabilities currently name a **specific** search tool per step (`local_search` for customer-data
  gather, `run_pipeline` for Simple Question). This puts a *retrieval-strategy* choice — which is a
  **Platform** concern — inside the **Product** layer. It was a pragmatic work-around for the pipeline's
  framework-profile filtering that excludes customer documents; the *cause* lives in the platform's
  retrieval routing, not the capability. **Future fix (not now — it touches the Core):** introduce a
  single **Knowledge Tool** (`retrieve_knowledge`) the capability names instead, which internally
  chooses local / vector / hybrid and customer / public — so a capability declares *"I need relevant
  knowledge"* and the Platform decides *how*. The Knowledge Tool must still **record the strategy and
  sources it used in the result's provenance** (GRC auditability/reproducibility — hiding it is not
  acceptable). Servicing this debt is cheap: swap each plan step's tool name; no capability logic
  changes.

---

## Freeze status

**V2 Platform and Product Core are FROZEN as of 2026-07-17.** The frozen surface is: the AI pipeline
packages, `event-bus`, `pipeline-contracts`, `mission-engine`, `mission-store` (Slices 1–4),
`mission-integration`, and Human Approval Slices 1–3. Changes to these require a new/superseding ADR
and the same slice discipline (ADR → review → small slice → tests → review → freeze). New work starts
from the *Next / deferred* list above — not by editing the frozen core.
