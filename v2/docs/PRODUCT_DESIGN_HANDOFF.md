# AI GRC Platform — Product Design Handoff (V2 → V1)

> **Purpose.** The autonomous engineering phase is complete. The project has crossed the boundary
> from **Platform Engineering** (objective, verifiable — done) to **Product Design** (subjective,
> product/UX/security decisions — next). This document hands off the built system to product design:
> what exists, what constraints it imposes, what is still open, and a recommended build order **after**
> the product is designed and approved. **No further implementation should begin until then.**
>
> **Last updated:** 2026-07-20 · **State:** Platform + all core capabilities + customer-knowledge
> integration + structured deliverables (Markdown/DOCX/PDF) complete and frozen.

---

## 1. Current architecture

Layered, mission-centric, dependencies pointing inward (CLAUDE.md §5–6). Everything a user asks for
becomes a **Mission** — a governed, auditable, resumable unit of work — driven through the frozen Core.

```
Request
  → AssistantRuntime            (intent → capability → mission plan)   [assistant-runtime]
    → MissionRuntime             (Engine + Store + Outbox, durable)     [mission-integration]
      → RegistryExecutor         (resolves each PlanStep → a Tool)      [pipeline-tool]
        → Tool Registry → Tool   (run_pipeline / search / framework / generate_text / …)
          → Services / Domain / Infra (Postgres, pgvector, event bus, LLM providers)
```

- **Core (frozen):** Event Bus, Pipeline Contracts, Mission Engine (lifecycle + two ports:
  `ExecutionPort`, `MissionStorePort`), Mission Store (Postgres, sync psycopg3 + Transactional
  Outbox), Human Approval (state + approve/reject + resume). ADRs 0035–0051.
- **AI pipeline (frozen):** retrieval → context → prompt → generation → validation, provider-agnostic
  (Claude/Gemini/Ollama/OpenAI behind a port). Tenant-scoped retrieval (`RetrievalScope.from_context`).
- **Product layer (built here):** the Assistant, the real tools, the capabilities, per-tenant
  knowledge, and the deliverables — all **consumers** of the frozen Core (no Core edits without ADR).

Every mission emits domain events and is fully reconstructable for audit (CLAUDE.md §19).

---

## 2. Completed capabilities

All in `assistant-runtime/builtin/`, all real (no echo), all reading the customer's own data where
relevant, all proven end-to-end in `grc-assistant`.

| Capability | Shape (steps → tools) | Reads customer data? |
|---|---|---|
| **Simple Question** (`ask`) | 1 grounded step → `run_pipeline` | via retrieval (global + tenant) |
| **ISO Controls** | 1 step → `framework_control_library` | no (framework catalog) |
| **Risk Assessment** | `collect_context`(local_search) → `assess_risk` → `generate_report`(generate_text) | **yes** |
| **Policy Generator** | `identify_controls`(framework) + `gather_guidance`(local_search) → `draft_policy`(generate_text) | **yes** |
| **Vendor Review** | `identify_supplier_controls`(framework) + `gather_vendor_context`(local_search) → `assess_vendor`(generate_text) | **yes** |
| **Gap Assessment** ⭐ | `identify_controls`(framework) + `gather_evidence`(local_search) → `compute_gap`(generate_text) | **yes** |

Composites **chain**: later steps synthesise *from* earlier steps' output (ADR 0051). Selection is a
reference keyword recognizer (`risk`/`iso`/`policy`/`vendor`/`gap`) behind a port — replaceable by an
LLM recognizer with no other change.

---

## 3. Completed tools (Real Tools layer)

Each an independent package consuming the frozen Platform; each satisfies the `Tool` contract and is
named by a plan step (ADR 0048).

| Tool(s) | Package | Wraps |
|---|---|---|
| `run_pipeline` | `pipeline-tool` | the AI Orchestrator (grounded RAG, cited) |
| `framework_control_library` | `framework-library` | frameworks-as-data: **ISO 27001:2022** (93), **CIS v8** (18), **NIST CSF 2.0** (22) |
| `read_pdf` · `read_docx` · `read_excel` | `document-tools` | `knowledge-importer` parsers (path-traversal-safe) |
| `local_search` · `vector_search` · `hybrid_search` | `search-tools` | `retrieval-engine` (tenant-scoped, fail-closed) |
| `generate_text` | `llm-tools` | `generation-engine` providers (raw generation) |
| per-tenant ingestion | `knowledge-runtime` | `knowledge-importer` chunker → tenant-scoped `CorpusChunk` |

*Embeddings* already exist in the Platform (`knowledge-importer`), consumed by ingestion + vector
search — not rebuilt.

---

## 4. Completed deliverables

`deliverables` package — a **standalone** transformation layer (`Mission → structured deliverable →
Markdown/DOCX/PDF`), depending only on `mission-engine` + `framework-library`. Not wired into the
Assistant; any consumer calls it.

- **Generic `Deliverable`** — one cited section per mission step, with provenance and confidence.
- **Gap Matrix — Evidence Mapping** ⭐ — `control ↔ status ↔ evidence`, evidence coverage %. Named
  *Evidence Mapping* (deterministic lexical) on purpose — **not** a compliance attestation.
- **Exports:** Markdown, **DOCX** (`python-docx`), **PDF** (`reportlab`) — each returns `bytes`.

---

## 5. Architectural constraints Product Design MUST respect

These are load-bearing; violating them means an ADR and/or a Core change.

1. **Mission-centric.** The unit of work is a Mission with an explicit lifecycle (Created → Planned →
   Executing → *Awaiting Approval* → Completed / Failed / Archived). The product **must** present
   missions as first-class, navigable objects (CLAUDE.md §8, §18). Chat, if used, *opens/steers*
   missions — it is not the model of record.
2. **Human-in-the-loop gates.** A consequential step pauses the mission at a human gate; the Core
   supports approve/reject/resume (ADR 0044). The UX must surface the proposed action + its evidence
   and capture the decision (who/when). *(No shipped capability marks a step consequential yet — that
   is a product choice: which actions require sign-off.)*
3. **Tenant isolation is absolute** and **fail-closed** — a query never crosses tenants; a
   cross-tenant retrieval refuses rather than leaks. Every product surface must carry tenant context.
4. **Grounding + provenance are mandatory.** Outputs cite sources; deliverables carry per-section
   citations/confidence. The UI must show sources and confidence, and must not present uncited GRC
   claims as fact (CLAUDE.md §12, §19).
5. **Frozen Core.** No changes to Event Bus, Pipeline Contracts, Mission Engine/Store, Human Approval
   without a superseding ADR. Extend via tools/capabilities/consumers.
6. **Linear steps, limited inter-step flow.** Steps run in order; a step sees prior steps' output
   (ADR 0051) but there is no DAG/fan-out. Deep multi-agent orchestration is a future ADR.
7. **Durable, resumable missions.** Persistence is Postgres (sync psycopg3) + Transactional Outbox;
   single-writer per mission today (no mission lease yet — durable multi-worker needs an ADR).
8. **Provider-agnostic AI.** No product code imports an LLM SDK; generation/retrieval are behind ports.

---

## 6. Product decisions that remain open (human-led)

None of these has a single correct answer; each shapes what customers experience and pay for.

- **Personas & top jobs.** Who is V1 for — GRC analyst, CISO, external auditor? What is their
  first-10-minutes job?
- **UX model.** Workspace-first (CLAUDE.md §18 leans here) vs chat-centric — and the concrete shape
  (mission list, board, detail view).
- **Core flows.** How a mission is started, monitored, approved; where deliverables appear; how a
  user goes *question → mission → deliverable → export*.
- **Document upload UX** and when per-tenant ingestion is triggered (drag-drop, connectors, batch).
- **Auth & tenancy onboarding.** OIDC/SSO choice, org/user provisioning, session model.
- **RBAC role model** — *who can do what*: run missions, approve gates, upload evidence, export,
  administer. (`ToolSpec.required_roles` exists but is **not enforced** — the enforcement mechanism is
  engineering; the **role model is a product/security decision**.)
- **Approvals UX.** Who approves which actions; notification and escalation behaviour.
- **Dashboards & reports.** What a customer sees at a glance (coverage %, open gaps, mission status,
  trends) — one dashboard or several, per role.
- **Deliverable presentation & download** in-product.
- **Notifications** (email/Slack) — which events, which channels.
- **Team collaboration** — assignment, comments, ownership.
- **API contract** — should be **derived from** the chosen UX and integrations, not invented first.

---

## 7. Recommended V1 build order — *after* Product Design is approved

Do **step 0 first**; it makes the rest near-mechanical because everything derives from it.

0. **Write the Product Specification (V1)** — a *product* doc (personas, first-10-minutes, UX model,
   core flows, deliverable presentation, approvals, dashboard, team model). *This is the most
   important document in the project; it is human-led and is the input to everything below.*
1. **Auth, tenancy & the RBAC role model** — the security foundation; needs the role model decided.
   Then wire enforcement of `ToolSpec.required_roles` (a policy hook at the executor/orchestrator).
2. **Document upload + per-tenant ingestion wiring** — connect `knowledge-runtime` to a real store
   (migrate the in-memory `TenantKnowledgeBase` to **pgvector** via the existing `PgVectorProvider`).
3. **REST API** — mission lifecycle (create/list/monitor/approve), capabilities, deliverables +
   export, upload. Shape derived from the Product Spec.
4. **Workspace UI** — missions, approval gates, deliverables with citations/confidence, export/download.
5. **Deliverable selector** (`deliverable_for(mission)` in the `deliverables` package) + export
   endpoints.
6. **LLM intent recognizer** — replace the keyword recognizer (same port).
7. **Dashboards & notifications.**
8. **Durable execution** — mission lease + multi-worker relay + scheduler (each its own ADR).
9. **Production readiness** — Docker, Kubernetes, CI wired for the `v2/` packages (currently the
   per-package `uv` projects are **not** in repo-root CI), monitoring, security review, performance,
   scaling, disaster recovery.

### Carried-forward technical debt (address during the above, not before)
- **Capability ↔ retrieval-strategy coupling** — capabilities name a specific search tool
  (`local_search`); introduce a unified **Knowledge Tool** (`retrieve_knowledge`) that hides the
  strategy (local/vector/hybrid, customer/public) but **records it in provenance**. (ROADMAP §Debt.)
- **Risk Register with scores** — deferred; likelihood/impact are not deterministically derivable and
  must not be invented. Needs structured LLM output, designed with the product.
- **Overclaim guard** — the system knows the customer's *documents*, not structured entities (assets,
  users, CMDB, cloud, IAM, inventory). If V1 promises "knows your environment", that scope is new work.

---

*End of handoff. Autonomous engineering is paused here by decision. The next action is the Product
Specification (V1), produced with the product owner — not code.*
