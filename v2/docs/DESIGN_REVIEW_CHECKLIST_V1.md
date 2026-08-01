# AI GRC Platform — Design Review Checklist (V1) · **APPROVED**
## *The design-review constitution*

> **This is not a checklist — it is the quality contract for the user experience.** It is the reference
> that stops the design from decaying as the product grows, exactly as `pytest` stops the code from
> decaying. No View is added or changed without passing through these gates, in order.
>
> **Derived from the real V1 Views** ([WIREFRAMES_V1.md](./WIREFRAMES_V1.md)) and the decisions above it
> (Spec · Domain Model · IA · Interaction Principles · Screen Flows · REST API) — not from theory.
>
> **Status:** ✅ **APPROVED** (owner) — the ninth and final Foundational Document. **Last updated:**
> 2026-07-22. **Enforced as a process by** [PRODUCT_DEVELOPMENT_PROCESS.md](./PRODUCT_DEVELOPMENT_PROCESS.md).

---

## 1. Purpose

- **Why this exists.** Every product decays under growth: screens multiply, states leak, implementation
  surfaces, trust erodes. This document is the objective, repeatable test that any View — today or years
  from now — must pass, so growth adds capability without adding entropy.
- **When to use it.** **Before approving any new View, or any change to an existing View.** A View that
  has not passed every gate is not "done" — it is a draft. Run it the way you run a test suite: fail
  loudly, fix, re-run.
- **How to use it.** Walk the View through **Gate 0 → Gate 7** in order. Answer every question **Yes/No**
  (a "No" is a finding). Assign each finding a **Severity**. Record the **Approval block**. A View with any
  🔴 open is **Rework required** — no exceptions.

---

## 2. Review Gates

Each View passes the gates **in sequence**. Gate 0 is the guard before all others — it can end the review
before it starts (by deleting the View).

### Gate 0 — Should this View exist at all? *(the anti-bloat guard)*

> **Could this View be derived instead of created?** If it is merely a different *view* of an object that
> already exists (as Deliverable is derived from Mission), do **not** mint a new View or a new Object.
> This protects the product from bloat exactly as the Scalability Rule protects the sidebar.

- [ ] **Test of Removal** — if we deleted this View, does a real user journey break? *(No broken journey ⇒
      the View is redundant — stop here.)*
- [ ] Is this View **not** a duplicate of an existing View's job (one user question = one View)?
- [ ] If it presents an existing object differently, is a *state/variant of an existing View* insufficient?
      *(If a variant suffices, use it — don't create.)*
- [ ] Does it introduce **no new domain object** that isn't already justified in the Domain Model?

*Pass Gate 0 ⇒ the View has earned its existence. Continue.*

### Gate 1 — Domain Alignment

- [ ] Does the View map to a **real Domain concept** (from the Conceptual Domain Model)?
- [ ] Does it use **the user's language**, never implementation language (Evidence, not "files"; Findings,
      not "step_results"; Plan steps as verbs, not tool names)?
- [ ] Does it respect the object's **Owner / Identity / Lifecycle** (e.g. a Deliverable belongs to a
      Mission; approval is on the Mission, not the deliverable)?
- [ ] Does it expose **nothing marked "not user-visible"** (Tool, Pipeline, CorpusChunk, Executor, Store,
      Event Bus)?

### Gate 2 — IA Alignment

- [ ] Does the View belong to a **Product Area** (a visible Primary Object) or a **Global Activity** — and
      not float outside the IA?
- [ ] Does it obey the **Scalability Rule** (a new *type* of Mission/Deliverable does **not** get its own
      sidebar area)?
- [ ] **List-vs-Detail rule** (for any list/index view): does every field earn its place by the test —
      *a fact the user needs to decide "open this item" stays in the list; a fact they need only after
      opening belongs in the detail view*? (Prevents a list from bloating into an ERP grid. Added
      2026-07-22 from the S1 review.)
- [ ] Is its **landing/entry** context-appropriate (reached from where the work naturally starts)?

### Gate 3 — Interaction Principles

- [ ] Everything starts from a **Mission** where applicable (Principle 1)?
- [ ] Does it **not hide the reasoning path**, and show **evidence** for recommendations (Principles 2, 3)?
- [ ] Are plans **steerable, not programmable** (remove/reorder/disable — never code) where a plan appears
      (Principle 4)?
- [ ] Does it **navigate by work, not by implementation** (Principle 5)?
- [ ] Is any deliverable **derived, never edited** (Principle 6)?
- [ ] Is human **approval explicit** where a consequential action occurs (Principle 7)?
- [ ] Does it **surface uncertainty** honestly (Principle 9) and **never block** on Time-to-Deliverable
      (Principle 10)?

### Gate 4 — State Machine Alignment

- [ ] Does the View render a **real state** (or states) from a Screen-Flow state machine?
- [ ] For a multi-state View, does **each state variant** correctly change *what is visible / actionable*
      (e.g. Mission Detail: Draft/Running/WaitingApproval/Completed/Failed)?
- [ ] Are all transitions **legal** (no action offered that the state machine forbids)?
- [ ] Does an illegal/absent state resolve to a defined **Empty/Error** state, never an undefined screen?

### Gate 5 — API Alignment

- [ ] Does **every Action/button map to a real API Event** (a Command or Query in the REST contract)?
- [ ] Does the View invent **no endpoint** that the contract doesn't define (or is not listed as a Domain
      §3 gap to build)?
- [ ] Does it read progress by **poll** (`GET /missions/{id}`), not assume WebSocket/SSE (V1)?
- [ ] Do consequential actions carry the contract's guards (**role**, **idempotency**, legal transition)?

### Gate 6 — UX Quality

- [ ] Does the View answer **exactly one user question**? *(Rule 11 — the strongest framing; the primary
      decision is the natural answer to it.)*
- [ ] Does it expose **no more than one primary decision**?
- [ ] Are all four of **Empty / Loading / Error / Success** states defined?
- [ ] Is **Hidden Complexity** named (what the View deliberately does *not* show)?
- [ ] Are **Mobile** considerations stated?
- [ ] Does it reach its outcome in the **fewest steps** (Time-to-Deliverable)?

### Gate 7 — Trust & Transparency

- [ ] Does it show **citations/provenance** wherever it makes a GRC claim?
- [ ] For an output artifact, is there a **trust signal** (coverage · framework · #sources · human-review
      status), and honest framing (*Evidence Mapping*, not "compliance attestation")?
- [ ] **Trust-Bar rule** — does every view that **ends in a user decision** open with a **Trust Bar**?
      (Mission Detail, Deliverable/Result, Vendor Review, Policy Review — yes; pure navigation views like
      Mission List and Dashboard — no.) A decision surface tells the user *how far to trust it* first.
      (Added 2026-07-22 from the S2 review; product-identity rule.)
- [ ] Is it **tenant-scoped and Fail-Closed** (another tenant's data is impossible, not merely hidden —
      cross-tenant ⇒ `404`)?
- [ ] Is the model **honest about what it is** (assists auditable GRC work; never claims to *decide*
      compliance)?

---

## 3. Severity

Not every finding is equal. Classify each **No** so review effort is spent where it matters.

| | Severity | Meaning | Gate to merge? |
|---|---|---|---|
| 🔴 | **Blocker** | Violates Vision, Domain, or the State Machine (e.g. exposes a tool name; offers an illegal transition; leaks cross-tenant data). | **No** — Rework required. |
| 🟠 | **Major** | Confuses the user or breaks an Interaction Principle (e.g. two primary decisions; a button with no API event; missing evidence on a claim). | No — fix before approval. |
| 🟡 | **Minor** | Deferrable improvement (e.g. a missing Loading refinement; copy tightening). | Yes — with a tracked follow-up. |
| 🔵 | **Enhancement** | A future idea, out of V1 scope (e.g. notifications, connectors). | Yes — logged, not built. |

**Rule:** any open 🔴 ⇒ the View **cannot** be approved. Any open 🟠 ⇒ **Approved with changes** at best,
and only once each has an owner and a fix.

---

## 4. Approval

Every review ends with a recorded block — this is the audit trail of the design itself.

```
View:      <name>
Gates:     0✅ 1✅ 2✅ 3✅ 4✅ 5✅ 6✅ 7✅
Findings:  <n> 🔴 · <n> 🟠 · <n> 🟡 · <n> 🔵
Status:    Approved | Approved with changes | Rework required
Reviewer:  <name>
Date:      <YYYY-MM-DD>
Version:   <doc/View version>
```

- **Approved** — all gates pass; no 🔴/🟠 open.
- **Approved with changes** — passes with tracked 🟠/🟡 that have owners and dates.
- **Rework required** — any 🔴, or unowned 🟠. Back to design.

---

## 5. Reference application — the V1 Views through the gates

*Proof the constitution is derived from reality, not theory: every approved V1 View passes Gate 0's Test of
Removal and answers one question.*

| View | Gate 0 — breaks if removed | One user question | Notable gate check |
|---|---|---|---|
| Onboarding | first-run cold start | "How do I get started?" | G6 empty-state *is* the view |
| Dashboard | operator/CISO triage | "What needs my attention?" | G6 one decision = where to act |
| Missions | every path to a mission | "Which mission do I open?" | G2 Product Area = Missions |
| New Mission | starting any work | "What work do I want done?" | G4 states Selecting→Scoping |
| Mission Created | confirm-before-execute | "Run it or adjust it?" | G0 variant of Draft, but distinct UX moment ✅ |
| **Mission Detail** | executing & governing all work | "What is happening?" | G4 five state variants; G1 no tool names |
| Deliverable | delivering & trusting the outcome | "Can I trust this output?" | G7 Trust Bar; G3 no edit (derived) |
| Knowledge | feeding missions customer data | "What evidence do we have?" | G1 Evidence language, not files |
| Approvals | the reviewer decision path | "What decisions are waiting?" | G3 explicit approval; G5 Approver role |
| Library / Settings | reference / admin | "What does the framework require?" / "How does this workspace behave?" | minimal in V1 |

*Every V1 View: passes Gate 0, answers one question, maps to a state and to API events. None redundant.*

---

## Where this sits

1. ✅ Vision · 2. ✅ Spec · 3. ✅ Domain Model · 4. ✅ IA · 5. ✅ Interaction Principles · 6. ✅ Screen
Flows · 7. ✅ REST API · 8. ✅ Wireframes · **9. Design Review Checklist (this)** → 10. Frontend
Components → 11. Backend additions (Domain-Model §3 gaps).

*From here the work is implementation, not new base decisions. This document reviews every screen and
feature that comes after — the same way code review reviews every commit.*
