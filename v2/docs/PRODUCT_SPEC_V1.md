# AI GRC Platform — Product Specification (V1) · **APPROVED**

> **The top reference for the project.** The product document (not a technical one): it defines *how
> the customer experiences the platform*, and every product-surface artifact (API, UI, RBAC,
> workflows) is **derived from it**. **Governance:** no API, UI, or workflow changes unless this
> document changes first — **the product leads the code, not the other way around.**
>
> **Legend:** ✅ **DECIDED** · 🔷 **PROPOSED** (open) · ❓ **OPEN**.
> **Status:** V1 decisions locked by the owner. **Last updated:** 2026-07-20.

---

## 1. Product Vision — one page

**Rasheed is an *AI GRC Workspace powered by AI Missions*.** ✅

A workspace where GRC practitioners get their compliance and risk work done — risk assessments, gap
analyses, policy drafting, vendor reviews — by launching **AI Missions** that gather evidence from the
organization's **own documents**, perform the analysis and drafting, and produce **auditable
deliverables**, with a **human in the loop** for anything consequential.

- **The product is the Workspace.** The unit of work is the **Mission**. The AI is the **engine**.
  **Chat is a fast way to *start* a mission — not the product.**
- **Not** "ChatGPT for GRC", **not** "Jira with AI" — the space between: a **mission-centric workspace
  driven by AI**.
- **Honest promise:** *"AI helps you perform **auditable** GRC work on **your own evidence**."* Never
  *"AI assesses your compliance."*

---

## 2. Product Principles

1. **Every meaningful piece of work is a Mission. Every Mission produces a Deliverable. Every
   Deliverable is auditable.** ✅ *(the founding principle)*
2. **The product never hides what it is doing.** ✅ *(the real difference from a chatbot)* — the
   **plan** is visible, the **evidence** is visible, the **sources** are visible, the **reason** for a
   recommendation is visible, the **approvals** are visible. No black box.
3. **Grounded in the customer's own evidence**, not general knowledge — every factual claim is cited;
   we say "insufficient evidence" rather than guess.
4. **The human decides, the AI proposes.** Consequential actions pause for human sign-off.
5. **Honest by design.** We describe exactly what the system does (e.g. *evidence mapping*), and never
   overclaim (never *"compliance attestation"*). Trust is the product.
6. **Auditable by default.** Every mission is reconstructable — inputs, sources, model/prompt version,
   approvals (who/when).
7. **Workspace-first.** Missions, deliverables, and evidence are durable, navigable objects; chat is
   an entry point, not the record of work.
8. **Fast feel.** V1 missions feel near-instant; long-running work becomes asynchronous *later* — never
   blocking the workspace, and we don't build that infrastructure before we need it.
9. **Multi-tenant, isolated by construction.** Cross-tenant access fails closed.

---

## 3. Value Proposition

- **For the GRC Practitioner (primary/user):** collapse hours of manual evidence-gathering, drafting,
  and report assembly into minutes — grounded in *your* documents, cited, auditable.
- **For the CISO / Head of GRC (secondary/buyer):** visible **coverage and gaps**, **audit-ready
  exportable** deliverables, and **human sign-off** — throughput for the team, assurance for you.
- **Differentiator:** mission-centric AI that works on *your* evidence with **provenance**, **human
  gates**, and **full transparency** — not a generic chatbot, not a static register.

---

## 4. Personas

### Primary — **GRC Practitioner** ✅ *(designs V1)*
Spans **GRC Analyst · Compliance Officer · Risk Officer · Internal Auditor · Cyber Governance
Specialist** — one daily cycle: gather evidence → run assessments → review controls → write policies →
track work → produce reports. Uses the system **hours a day**. Goals: do the work faster, with
defensible, exportable output. Frustrations: manual evidence hunting, copy-paste reports, repeating
analysis per framework.

### Secondary — **CISO / Head of GRC** ✅ *(buys & monitors)*
Does **not** execute missions. Reviews results, **approves**, monitors metrics, requests reports.
Goals: posture/coverage visibility, audit-readiness, team throughput, sign-off control. V1 must show
them a good dashboard, approvals queue, and exportable reports.

*(Later — external auditor (read-only), workspace admin — out of V1.)*

---

## 5. Empty State (Onboarding) — solving the cold start ✅

A mission on an **empty knowledge base** gives thin results. Frameworks (ISO/CIS/NIST) are pre-loaded
as data, but **the customer's evidence must be uploaded first.** So the first screen after a tenant is
created is **not** "New Mission" — it is **"Let's prepare your workspace"**: a **dismissible checklist
with clear progress** (not a long wizard), persisting until the tenant has ingested knowledge.

```
Prepare your workspace                                    ▓▓▓░░  1 of 3

☑ Upload your first document        (policies, evidence, prior reports)
☐ Build your knowledge base         (we ingest & index it — tenant-private)
☐ Run your first mission

   Connect sources — Microsoft 365, cloud, ticketing        (coming soon)
```

- Framework catalogs (ISO/CIS/NIST) are **already available** — no import step.
- Offer a **"Try with sample data"** path for evaluation/demo.

---

## 6. First 10 Minutes (primary persona, workspace already prepared) ✅

1. Log in → land on the screen that fits **context** (see §8 landing rule) — for an active
   practitioner, the **Workspace**.
2. See recent missions, knowledge status, and a prominent **New Mission**.
3. Click **New Mission**.
4. Pick a **mission type**: Risk Assessment · Vendor Review · Gap Assessment · Policy Generator · Ask.
5. Provide **scope/subject** and **attach or select** relevant documents.
6. **Review the Mission Plan** — human-readable, and **steerable**:
   > ✓ Collect evidence ✓ Review controls ✓ Compare evidence ✓ Generate findings ✓ Produce deliverable
   The user may **remove**, **reorder**, or **disable** a step (steering) — never edit the internal
   logic (not programming). Never raw tool names.
7. **Run Mission.**
8. **Watch progress** (steps completing, ~seconds; progress via polling).
9. If a step is **consequential** → an **Approval gate** appears (proposed action + its evidence) →
   approve / reject.
10. Get the **Deliverable** — view in-app (sections + citations + coverage) → **export** Markdown /
    DOCX / PDF → **download**.

---

## 7. Mission Lifecycle UX (mapped to the frozen Core) ✅

| Core state | Workspace label | What the user sees |
|---|---|---|
| Created / Planned | **Draft** | the plan, not yet run — **steerable** (remove/reorder/disable steps) |
| Executing | **Running** | live step progress (polled) |
| Awaiting Approval | **Waiting for approval** | a gate card: proposed action + evidence |
| Completed | **Completed** | the deliverable, ready to view/export |
| Failed | **Failed** | reason + retry |
| Archived | **History** | reconstructable record |

Every **mission detail** view shows: goal · the human-readable plan · step results **with citations** ·
approvals (who/when) · the deliverable · export. Transparency (Principle 2) + audit (Principle 6),
made visible. **Plan steering = remove / reorder / disable a step, not editing internal logic.** ✅

---

## 8. Workspace Information Architecture ✅

Top-level areas (left sidebar): **Dashboard · Missions · Deliverables · Knowledge · Library** ·
*(Admin, minimal)*.

- **Dashboard** — status at a glance (open / waiting-approval / completed, coverage %, recent
  deliverables). Natural home for the **secondary** persona.
- **Missions** — the list/board (filter by type/status). The **primary** persona's home.
- **Deliverables** — a **top-level index**, and **every deliverable links back to its owning mission**
  (it is *not* a bare download center — a deliverable is always tied to the mission that produced it).
- **Knowledge** — uploaded documents + ingestion status *(connected sources later)*.
- **Library** — browse the framework catalogs (ISO 27001 / CIS / NIST).

**Landing screen — by context, not fixed** ✅:
- New user / no knowledge yet → **Onboarding**.
- Practitioner with missions → **Workspace (Missions)**.
- Manager with no missions of their own → **Dashboard**.

---

## 9. Navigation ✅

- **Left sidebar:** Dashboard · Missions · Deliverables · Knowledge · Library · (Admin).
- **Global "New Mission"** button — always available.
- **Command bar / chat entry (⌘K):** *"assess the risk of…"*, *"run a gap assessment for…"* → **starts
  the matching mission** (via the intent recognizer). Chat-as-entry-point — a launcher, not a
  conversation surface (Principle 7).
- **Mission detail:** breadcrumb `Missions > [Mission]`.

---

## 10. Key Screens (the V1 set) ✅

1. **Onboarding / Empty State** (§5).
2. **Dashboard** (status, coverage, recent deliverables).
3. **Missions** list/board.
4. **New Mission** (type → scope → documents → steerable plan review).
5. **Mission detail** (progress · approval gate · step results with citations).
6. **Deliverable view** (sections · citations · coverage · export buttons).
7. **Deliverables index** (all deliverables, each linked to its mission).
8. **Knowledge** (upload · ingestion status).
9. **Approvals queue** (focused review list for the secondary persona).

*(Library browse and Admin — minimal.)*

---

## 11. API — derived from the UX ✅ *(shape; detailed contract during API design)*

REST, tenant-scoped, versioned (`/v1`); **derived from the screens above**.

- **Auth / session** — OIDC/SSO. Roles: **Practitioner · Approver · Admin** (§ RBAC).
- **Knowledge** — `POST /documents` (upload), `GET /documents`, ingestion status.
- **Missions** — `POST /missions` (type, scope, document refs) → returns the **plan**;
  `PATCH /missions/{id}/plan` (steer: remove/reorder/disable steps); `POST /missions/{id}/run`;
  `GET /missions` (list/filter); `GET /missions/{id}` (detail: steps, approvals);
  `POST /missions/{id}/approvals/{step}` (approve/reject); `POST /missions/{id}/cancel`.
- **Deliverables** — `GET /deliverables` (index); `GET /missions/{id}/deliverable`;
  `GET /missions/{id}/deliverable/export?format=md|docx|pdf`.
- **Dashboard** — `GET /dashboard` (aggregates).
- **Progress** — **polling** (`GET /missions/{id}`) in V1. **No** WebSocket/SSE. ✅

---

## RBAC (V1) ✅

Exactly **three** roles — **nothing more in V1**:
- **Practitioner** — creates, steers, and runs missions; uploads evidence; views/exports deliverables.
- **Approver** — everything a practitioner sees, plus **approve/reject** at human gates.
- **Admin** — user & role management, workspace settings.

*(`ToolSpec.required_roles` enforcement is wired to these three; advanced RBAC — quorum, escalation —
is out of V1.)*

## V1 scope / non-goals ✅

- **In V1 — exactly these six capabilities, no others:** **Ask · Gap Assessment · Risk Assessment ·
  Policy Generator · Vendor Review · ISO Controls.** Plus: document upload + ingestion · mission run +
  steerable plan + progress + approval gate · deliverable view + index + export (MD/DOCX/PDF) · basic
  dashboard · auth + the 3 roles.
- **Not in V1 (later):** external connectors (M365/cloud/IAM/ticketing) · async/background workers +
  notifications · advanced RBAC · multi-team collaboration · Risk Register with scores · structured
  entities (assets/users/CMDB) · unified Knowledge Tool (tech debt) · any new capability.

## Success metrics ✅

- **★ North star — Time to Deliverable:** from *mission created* → *first deliverable produced*. If we
  turn hours into minutes, the product has succeeded. **This is the primary metric.**
- Missions per practitioner per week.
- % of deliverables exported/downloaded.
- Evidence-coverage trend (the buyer's headline).

---

*Approved by the owner, 2026-07-20. This document is the highest reference in the project. Product
leads code: nothing on the product surface is built or changed until it is reflected here first.*
