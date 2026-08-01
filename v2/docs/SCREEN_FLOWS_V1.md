# AI GRC Platform — Screen Flows (V1)

> **Built as State Machines, not screen sequences.** Each flow is *States · Events · Transitions ·
> Guards · Results*, not "screen A → B → C". This makes the UI and the API derivable, and — critically —
> it **matches the existing Mission Runtime** (Created → Planned → Executing → Awaiting Approval →
> Completed / Failed) instead of inventing a new flow. Every state/event/guard below maps to a real Core
> operation.
>
> **Template (every flow):** 1 Purpose · 2 Entry States · 3 Main States · 4 Events · 5 Guards · 6 Exit
> States · 7 Success Criteria · 8 Related Principles.
>
> **The three flows are the whole journey:** New Mission → Mission Detail → Deliverable View.
> **Status:** draft for approval. **Last updated:** 2026-07-20.

---

## Flow 1 — New Mission

**1. Purpose.** Turn a user's intent into a **runnable, steered Mission** — the single entry to all work
(Principle 1).

**2. Entry States.** Global **＋New Mission**; the **⌘K command bar** ("run a gap assessment for…"); the
Onboarding checklist ("Run your first mission"); a "New" action on Dashboard or Missions.

**3. Main States.**
```
Selecting Type ──select──► Scoping ──set scope / attach docs──► Plan Review (Draft)
                                                                    │ steer (remove/reorder/disable)
                                                                    ▼
                                                                Ready to Run ──run──► ►► Mission Detail (Running)
        (any state) ──cancel──► Discarded
```
- **Selecting Type** — pick one of the six Mission Types (Ask · Gap · Risk · Policy · Vendor · ISO).
- **Scoping** — enter the subject/scope; attach or select Documents (Evidence, by reference).
- **Plan Review (Draft)** — the system builds the plan (the type's plan factory) → shows the
  **human-readable, steerable** plan. *Core:* `create` + `plan` (Mission = Created → Planned).
- **Ready to Run** — the plan is confirmed.

**4. Events.** select type · set scope · attach/select documents · **steer plan** (remove / reorder /
disable a step) · run · cancel.

**5. Guards.** scope present (else a neutral default) · plan has ≥ 1 step (steering can't empty it) ·
role = **Practitioner** · *soft warning* if the knowledge base is empty (cold-start — Principle 10 wants
a meaningful result). `run` maps to `POST /missions` (create+plan) then `POST /missions/{id}/run`.

**6. Exit States.** **Running** → Mission Detail (on run). **Discarded** (on cancel — no mission persists).

**7. Success Criteria.** A Mission exists in **Running** with a confirmed, steered plan — in the fewest
possible steps.

**8. Related Principles.** 1 (starts from a Mission) · 4 (steerable, not programmable) · 2/3 (plan +
sources visible) · 8 (tenant-scoped documents) · 10 (minimal steps, fast).

---

## Flow 2 — Mission Detail

**1. Purpose.** Monitor a running mission, **decide at approval gates**, see the **findings with
evidence**, and reach its deliverable — the transparency surface (Principle 2).

**2. Entry States.** From New Mission (on run); the Missions list; Dashboard "recent"; the **Approvals
queue** (deep-link to a specific gate); *(a notification — later)*.

**3. Main States** — *these are the Mission lifecycle exactly:*
```
Draft ──run──► Running ──step completes──► Running
                 │
                 ├─ needs approval? ──yes──► Waiting for Approval ──approve──► Running (resumes)
                 │                                        └────────reject────► Failed
                 ▼ (no more steps)
             Completed ──view / export──► ►► Deliverable View
                 ▲
   Running ──error──► Failed ──retry──► Running
```
- **Running** — progress **polled**; each finished step shows **Findings** (what/why) + **citations**.
- **Waiting for Approval** — a gate card: the **proposed action + its evidence**. *Core:* ADR 0044
  (await → approve/reject → resume).
- **Completed** — the deliverable is ready. **Failed** — reason + Retry.

**4. Events.** run · poll (progress) · **approve** · **reject** · retry · open findings/citation · open
deliverable.

**5. Guards.** **approve/reject require the Approver role** · resume happens only after approval · the
approval is bound to a **specific step** · retry only from Failed · progress is **poll** (`GET
/missions/{id}`), never a blocking wait (Principle 10).

**6. Exit States.** **Deliverable View** (Completed → view/export) · Missions list (back) · **History**
(archived).

**7. Success Criteria.** The mission reaches **Completed** with its deliverable available; *or* a gate is
explicitly decided; *or* a failure is shown and understood.

**8. Related Principles.** 2 (reasoning path visible) · 3 (evidence) · 7 (approval explicit) · 9
(uncertainty surfaced) · 10 (never blocks) · 8 (tenant-scoped).

---

## Flow 3 — Deliverable View

**1. Purpose.** View, verify, and **export** the mission's deliverable — the sellable, auditable
artifact. This is the *end* of Time-to-Deliverable (Principle 10).

**2. Entry States.** From Mission Detail (Completed); the Deliverables index; Dashboard "recent
deliverables".

**3. Main States.**
```
Viewing ──open citation──► ►► Document (the cited source)
   │   ──open mission──► ►► Mission Detail
   │
   └─ export (md / docx / pdf) ──► Downloaded (file bytes)
```
- **Viewing** — the deliverable's **sections** (findings / the Gap Matrix — *Evidence Mapping*) with
  **citations**, coverage %, and provenance. *There is **no edit affordance** — a deliverable is
  derived, not edited (Principle 6).* *Core:* `deliverables` package, derived from the completed Mission.
- **Downloaded** — export returns file **bytes** (MD / DOCX / PDF); the caller downloads.

**4. Events.** view · open a citation (→ source Document) · open the mission · export (md/docx/pdf).

**5. Guards.** the deliverable exists **only when the mission is Completed** (it is derived) · export in
any of the three formats · **no edit** (view + export + open-mission only).

**6. Exit States.** **Document** (a cited source) · **Mission Detail** (its mission) · a **download**.

**7. Success Criteria.** The user reads the deliverable, **verifies at least one citation**, and
**exports/downloads** it — the "deliverable produced & trusted" end state.

**8. Related Principles.** 6 (derived, never edited) · 3/2 (evidence + reasoning visible) · 5 (navigate
by work) · 9 (uncertainty/coverage honest — *Evidence Mapping*, not attestation) · 10 (fast to export).

---

## Why this closes the design

These three state machines define the **entire behaviour** of V1: how work is *started* (Flow 1),
*executed and governed* (Flow 2), and *delivered* (Flow 3). Every state maps to the frozen Mission
Runtime; every event maps to a real operation. From here, **Wireframes render these states**, the **API
exposes these events** (`POST /missions` → plan · `PATCH /plan` → steer · `POST /run` · `POST
/approvals/{step}` · `GET /missions/{id}` poll · `GET …/deliverable/export`), and implementation is
**derivation, not new decisions**.
