# AI GRC Platform — Information Architecture (V1) · **APPROVED**

> **What it answers:** *"If the user wants to find something, where do they expect to find it?"* — not
> "what goes in the sidebar." The IA is built in **three layers** and the Navigation is the **result**
> of the first two, never the starting point.
>
> **Derivation:** Objects come from the approved **Conceptual Domain Model** (only objects with
> *User Visibility = ✅*). Activities come from the **Personas** and the **First-10-Minutes**. Navigation
> is derived **only** from Objects + Global Activities. Nothing here is a new decision — it is an
> **aggregation of already-approved ones**.
>
> **Governing rule (owner):** *No element may appear in Navigation unless it maps to a **Product Area**
> (whose Primary Object is user-visible) or a **Global Activity**.* Contextual activities live **inside**
> their object, never in the nav.
>
> **Scalability rule (owner):** *A new sidebar area may be introduced **only** if it represents a new
> **top-level product concept**.* A new **type** of Mission or Deliverable does **not** earn an area — it
> lives inside its existing area. This is what keeps the navigation small as the product grows.
>
> **Status:** ✅ **APPROVED** by the owner. **Last updated:** 2026-07-20.

---

## Layer 1 — Product Areas *(where the user goes — derived from the Domain, not the Domain itself)*

**The IA shows Product Areas, not Domain Objects.** An area is a **place** in the product; it is
*derived from* the domain but is **not** identical to it — a screen is not an object. Each area names
its **Primary Object** (linking it to the domain without conflating), and *Dashboard* is a read-model
view — not a domain object at all.

| Product Area | Primary Object | What the user finds there |
|---|---|---|
| **Dashboard** | *(a read model — no domain object)* | status at a glance: open / waiting-approval / completed, coverage %, recent deliverables |
| **Missions** | **Mission** | all their missions (filter by type/status); the practitioner's home |
| **Deliverables** | **Deliverable** | the produced outputs (each links back to its mission) |
| **Knowledge** | **Document** | the tenant's uploaded documents + ingestion status *(Sources — later)* |
| **Library** | **Framework** | the framework catalogs (ISO 27001 / CIS / NIST) → Frameworks → Controls |
| **Approvals** | **Approval** | the cross-mission queue of items waiting for a decision |
| **Settings** | **User & Role** | users, roles, workspace configuration *(Admin)* |

*An area ≠ its object: **Knowledge** is not **Document**, **Library** is not **Framework**, **Dashboard**
is not a domain object. The area is the place; the Primary Object is what lives there.*

**Domain objects that appear *inside* an area (never top-level):**

| Domain object | Appears inside | Note |
|---|---|---|
| **Mission Type** | *New Mission* (a choice) | one of the six; not an area |
| **Plan** (⚠️ partial) | a Mission | human-readable, steerable summary |
| **Findings** (step results view) | a Mission | transparency (Principle #2) |
| **Control** | a Framework / a Deliverable | inside Library or a Gap Matrix |
| **Evidence** (citations) | Findings / a Deliverable | Documents-in-context, not an area |

*Excluded entirely (Visibility = ❌): Tool, Pipeline/Orchestrator, CorpusChunk, RegistryExecutor, Event
Bus, Mission Store — never surfaced anywhere (founding rule).*

---

## Layer 2 — Activities *(what the user does)*

Activities are **verbs**, not objects. Classified two ways: **by persona** (frequency drives priority)
and **Global vs Contextual** (this decides what may enter Navigation).

### By persona

| **GRC Practitioner** (primary — daily) | **CISO / Head of GRC** (secondary — periodic) |
|---|---|
| Start a mission · Upload evidence · Search · Steer a plan · Run a mission · View findings · Export a deliverable · Resume a mission · Browse frameworks | Monitor the dashboard · Review & approve at a gate · Request / export a report · Manage users & roles |

*Navigation optimises for the practitioner's frequent activities; the CISO's periodic ones must still be
reachable in one step (Dashboard, Approvals).*

### Global vs Contextual

| **Global** (may enter Navigation — one home each) | **Contextual** (live *inside* an object — never in Navigation) |
|---|---|
| **Start a Mission** (global action) | Steer plan · Run · View findings · Resume — *inside a Mission* |
| **Search / Command bar (⌘K)** | **Export a Deliverable** — *inside a Deliverable / its Mission* |
| **Upload evidence** → lands in Knowledge | **Review / approve** *this* gate — *inside an Approval* |
| **Monitor Dashboard** | **Generate report** — *an action within a mission, not a page* |
| **Browse Library** · **Manage Settings** | — |

*(This directly enforces the governing rule: Export, Resume, Generate Report, Review-Approval are
**contextual** → they are **not** navigation items.)*

---

## Layer 3 — Navigation *(derived only from Objects + Global Activities)*

### Primary navigation — left sidebar (the navigable areas)
```
Dashboard
Missions
Deliverables
Knowledge          (Documents · Sources ▸ later)
Library            (Frameworks ▸ Controls)
Approvals
Settings           (Users & Roles ▸ Admin)
```

### Global affordances (always available, one home each — not areas)
- **＋ New Mission** — the primary action, prominent everywhere.
- **⌘K Search / Command bar** — find anything; also the **chat-entry to start a mission** ("run a gap
  assessment for…").

### Landing — by context (from the Product Spec)
- New tenant / no knowledge → **Onboarding** ("Let's prepare your workspace").
- Practitioner with missions → **Missions**.
- CISO / manager with no missions of their own → **Dashboard**.

### Contextual activities mapped to their host (NOT in nav)
| Object (screen) | Contextual activities available there |
|---|---|
| **Mission** | steer plan · run · view findings · approve gate · resume · **export its deliverable** |
| **Deliverable** | export (MD/DOCX/PDF) · open its mission |
| **Knowledge** | upload · view ingestion status · (delete) |
| **Approval** (from the queue or a mission) | approve · reject |
| **Library / Framework** | browse controls |

---

## Layer 4 — Validation Checklist *(turns the IA from opinion into something reviewable)*

| Check | Pass? |
|---|---|
| Every navigation element maps to a **Product Area** (visible Primary Object) or a **Global Activity**? | ✅ (Dashboard/Missions/Deliverables/Knowledge/Library/Approvals/Settings = Areas; New Mission/Search = Global Activities) |
| Would a *new* sidebar area represent a **new top-level concept** (not a new type of Mission/Deliverable)? | ✅ *(scalability rule — no area for sub-types)* |
| Every **Global Activity** has exactly **one** home? | ✅ (New Mission = one global button; Search = ⌘K; Upload = inside Knowledge; Monitor = Dashboard) |
| Every **Contextual Activity** sits **inside the correct object**? | ✅ (Export/Resume/Findings → Mission/Deliverable; Approve → Approval; Upload → Knowledge) |
| No **implementation** concept (Tool/Pipeline/Chunk…) appears anywhere? | ✅ (Visibility = ❌ excluded by construction) |
| Can the **Practitioner** complete the **top-5 tasks** with minimal navigation? | ✅ — *Start mission* (1 global click) · *Upload evidence* (Knowledge) · *Search* (⌘K) · *Get & export a deliverable* (inside the mission) · *Resume/monitor a mission* (Missions → detail) |
| Can the **CISO** reach **Approvals** and the **Dashboard** directly? | ✅ — both top-level; CISO lands on the Dashboard |

---

## Where this sits

1. ✅ Vision · 2. ✅ Product Spec · 3. ✅ Conceptual Domain Model · **4. Information Architecture (this)**
→ 5. Interaction Principles (one page) → 6. Screen Flows → 7. Wireframes → 8. REST API → 9. Frontend →
10. Backend additions.

*The Navigation above is a **result** of the Objects and Global Activities, not a starting point — so it
stays small and coherent as the product grows: a new area may be added only when a new **visible object**
or **global activity** is approved.*
