# Product Development Process
## *The development constitution — how any feature gets built*

> **The product drives the code — as a process, not a slogan.** A feature is not "an idea → a design → some
> code." It is a **decision routed through the Foundation, approved, then implemented.** This one page is
> the law that keeps that true after the team grows — so the base decisions stay institutional and
> derivable, never held in one person's head.
>
> **Status:** governance (living). **Foundation state:** 🧊 **Product Design Foundation — Frozen**
> (2026-07-22). **Delivery phase:** ✅ **Foundation Phase complete (S1–S4)** → ▶️ **Product Expansion
> Phase (S5 onward)**. **Last updated:** 2026-07-22.

---

## The Foundation (the design-governance system)

Nine documents form a single closed loop from *why* to *how* — each derived from the one above it:

| # | Document | Answers |
|---|---|---|
| 1 | [Product Spec](./PRODUCT_SPEC_V1.md) *(+ Vision within)* | **Why** we build — and **what**. |
| 2 | *(Vision, inside the Spec)* | **Why** the product exists. |
| 3 | [Conceptual Domain Model](./CONCEPTUAL_DOMAIN_MODEL_V1.md) | **What** the product's concepts are. |
| 4 | [Information Architecture](./INFORMATION_ARCHITECTURE_V1.md) | **How** those concepts are organised. |
| 5 | [Interaction Principles](./INTERACTION_PRINCIPLES_V1.md) | **How** the product behaves. |
| 6 | [Screen Flows](./SCREEN_FLOWS_V1.md) | **How** states change (state machines). |
| 7 | [REST API Contract](./REST_API_CONTRACT_V1.md) | **How** states become events. |
| 8 | [Wireframes](./WIREFRAMES_V1.md) | **How** states are shown. |
| 9 | [Design Review Checklist](./DESIGN_REVIEW_CHECKLIST_V1.md) | **How** we stop any new design from drifting. |

*This is a Baseline Design: a newcomer can learn — from these docs alone — what we build, why, how it
should look, how it should behave, and how to avoid corrupting it.*

---

## How to build any new feature

Route the change to the **highest layer it touches**, change that layer's document **first**, then descend.
Never start at code.

1. **Does it need a new Domain concept?** → **Yes:** amend the **Domain Model** first (Owner/Identity/
   Lifecycle; user language). **No:** continue.
2. **Does it change the IA?** (a new Product Area / navigation) → **Yes:** amend **Information Architecture**
   first (respect the Scalability Rule — a new *type* of mission is not a new sidebar area). **No:** continue.
3. **Does it change behaviour or add/alter a state?** → **Yes:** amend the **Screen Flow** (state machine).
   **No:** continue.
4. **Does it add or change an event?** → **Yes:** amend the **REST API Contract** (events, not resources).
   **No:** continue.
5. **Does it add or change a View?** → run it through the **Design Review Checklist** (Gate 0 → Gate 7) and
   produce/update its **Wireframe**.
6. **After the affected documents are approved** → write the slice's **Execution Contract**
   (`docs/execution/`) — the executable acceptance criteria — **then** implement against it.

*If a change touches none of 1–5, it is pure implementation (a bug fix, a refactor) — no Foundation change,
just code + the normal code review.*

---

## The Execution Contract layer *(the bridge from design to code)*

The Foundation says *what the product is*. Before any slice is built, one more artifact says **what the
user will count as success** — so implementation is derived from experience, not from the technical layer.

- **The layer.** Not a new Foundational Document — the **bridge** between Design Review and Implementation:
  `Vision → Spec → Domain → IA → Interaction → Flows → API → Wireframes → Design Review → **Execution
  Contract** → Implementation`.
- **One page per slice**, in `docs/execution/S<n>_<NAME>.md`: **Goal · Given/When/Then · UX Metrics · APIs
  used · referenced Design Checklist · Done Definition**.
- **Authored just-in-time** — the contract for a slice is written **immediately before that slice**, never
  in bulk (its acceptance is informed by what earlier slices taught us).
- **Acceptance appears twice** — once as **definition** (before code) and once as **verification** (the
  slice isn't done until it passes). This inverts the sequence: `Acceptance Contract → Backend → API →
  Frontend → Acceptance Verification`, not `Read Model → … → Acceptance`.

## The Reality Gate *(fill it before the first commit of every slice)*

Every Execution Contract opens with a **Reality Gate**: *before any code, investigate what the current
system **actually provides** for this slice — the Core, the builders, the storage, whatever layer the
slice depends on — and build the contract on **reality, not assumption.**

**The first question — the Source of Truth.** Before "what can it do?", ask **"what is the Source of
Truth for this slice?"** — the one component that *owns* the state this slice reads and writes. Naming it
first anchors every other decision (which port, which projection, what fail-closed means). It is often the
more important question:

| Slice | Source of Truth |
|---|---|
| S1 Mission List | **Mission Store** |
| S2 Mission Detail | **Mission Aggregate** |
| S3 Result | **Deliverable Builders** |
| S4 Knowledge | **Knowledge Runtime** (ingestion) **+ Document Projection** (the read side S4 builds) |

Then the supporting questions:

- Ask **"what can the system do today?"**, never "what do we want to do?"
- Ask **"what does the system actually store?"**, never "what do we want the UI to show?"

**The composition question — the bridge to Foundation Reuse.** Finally, ask:

> **Can this slice be composed from existing projections?**

- **Yes → do not build a new projection.** Compose the existing ones (this is Foundation Reuse in
  action) and the Reuse Ratio stays high honestly.
- **No → the new component is legitimate — but it must be *justified* under guard 7** (New Component
  Justification): it answers a genuinely different business question, it is not a duplicate taken the
  easy way. A dashboard is a different question than a mission list; a coverage metric cannot be
  derived from the mission read model alone — those earn a new component. "It was easier" never does.

This question is what keeps a new projection from being spun up for convenience, while still welcoming
one when the business question is genuinely new — the exact seam between the Reality Gate and Foundation
Reuse.

This is not a new gate — it is the **one name** for the gates that already earned their keep: S1's
Capability Gate (found `type`/`scope` aren't on the aggregate), S2's Lifecycle Gate (found FAILED is
terminal → `retry` = re-run), S3's Core + Builder Capability Gates (found the Core provides *more* than
assumed), S4's Knowledge Gate (found `evidence_kind` missing from the `Document` contract). **Four for
four before the first commit** — the Reality Gate is a methodology *metric*, not luck. Filling it early
is exactly what keeps the Architecture & Product Freeze honest — a slice that assumes more than reality
provides is the drift the Freeze exists to catch.

## The Foundation Phase is complete *(S1–S4 built the language, not just features)*

The first four slices did more than ship views — they **established the system's language**, and that
language is now the reference every later slice speaks:

| Slice | What it established (the durable language) |
|---|---|
| **S1** | **Read Models** — the tenant-scoped, fail-closed projection pattern (`*-read-model`). |
| **S2** | the **Application layer** and its frozen contract vocabulary (ADR 0054). |
| **S3** | the **Result** + the **Builder / Presenter registries** (new type = an addition). |
| **S4** | **Evidence** (Collections as the unit) + the named **Reality Gate**. |

That is the **Foundation Phase — complete.** From **S5 the project enters the Product Expansion
Phase**: a new slice should **speak this language, not reinvent it**. The next effort goes to product
*capability*, not to reshaping the base — which was the whole point of building the Foundation first.

> **Product Expansion adds questions before it adds behavior.** (Owner, after S6.) S5 and S6 each
> added a **new question → a new read (Projection)** — but **no new Command, no new Aggregate, no new
> Domain**. The product grew by asking the same language different questions. The first slice that
> genuinely *adds behavior* is the create flow (S7); until then, expansion is new reads over a frozen
> core.

## Foundation Reuse *(open every Product-Expansion slice with it — S5 onward)*

Right after the Reality Gate, every Execution Contract from S5 opens with a short **Foundation Reuse**
block — four questions that make reuse explicit *before* any code:

| Question | e.g. (S5 Dashboard) |
|---|---|
| Which existing **Read Model** do I reuse? | Mission / Document |
| Which existing **Query** do I reuse? | MissionDetail / Result / Documents |
| Which existing **Presenter / registry** do I reuse? | Trust Bar / a Registry / Collections |
| What is **genuinely new** here? | the Dashboard read model only |

Read it as a smell test: **mostly reuse ⇒ the Foundation is working; mostly invention ⇒ the slice is
re-inventing what exists — stop and ask why.**

### Foundation Reuse Ratio — the fifth methodology guard

Each Product-Expansion slice records a simple ratio in its Retrospective:

```
New components:     2
Reused components:  11
Foundation Reuse:   85%
```

The target is **not 100%**, and — crucially — a high ratio is **not automatically good**. A retro that
reads `Reuse 92% · New: none` can mean the base is healthy *or* that the system has gone **rigid** and
can no longer absorb a genuinely new concept. The number is only a prompt; the **why** is the signal.

### New Component Justification — the sixth guard *(the number's conscience)*

So the ratio is never recorded alone. Every **new** component gets one line of justification in the
Retrospective — the Open/Closed Principle is not measured in file count, it is measured by one question:
**is this new because it is a new *concept*, or because it was *easier* than reusing what exists?**

```
New Component Justification

DashboardQuery      ✓ answers a new business question (no existing query fits).
DashboardPresenter  ✓ the UI is genuinely new.
No existing component was duplicated.
```

…and when something *was* taken the easy way, it is named honestly, not hidden behind a good ratio:

```
DashboardReadModel  ⚠ duplicates MissionReadModel — refactor candidate for S6.
```

Framed this way the guard cuts **both** ways at once: against **re-invention** (a duplicate must be
flagged, not laundered into the "new" count) *and* against **rigidity** (a real new concept is welcome —
it just has to be justified). The rule is **"every new component must be justified,"** never "new is
bad." The Foundation should *stabilise* the system, not *freeze* it against genuine product evolution.

**The seven guards, after S4:** Product Freeze · Architecture Freeze · Application Contract Freeze ·
Reality Gate · Foundation Reuse · Foundation Reuse Ratio · New Component Justification. The last is not a
gate — it is the one-line *reason* attached to anything that was not reused.

## The Slice lifecycle *(every slice is a Learning Unit, not just a build unit)*

```
Execution Contract → Backend → API → Frontend → Acceptance Verification → Slice Retrospective → Closed
```

A slice does **not** close at verification. It closes after a **Slice Retrospective** — a short half-page
answering four questions, appended to the slice's Execution Contract:

1. **Did we need to edit any Foundational Document?** Yes / No — *if yes, which, and why?*
2. **What did we learn that wasn't visible before implementation?** One or two notes only.
3. **Does this affect the next slice?** Yes / No.
4. **Decision:** **Close Slice** or **Rework**.

From **S5 on**, the Retrospective also records the **Foundation Reuse Ratio** (new vs. reused
components) *and* a one-line **New Component Justification** for each new component — the fifth and sixth
guards, watching that Product-Expansion slices build *on* the Foundation without either rebuilding it
(re-invention) or refusing genuine new concepts (rigidity).

This operationalises the **Architecture & Product Freeze**: if every answer is "No", the freeze proved
correct; if a change was needed, the document was fixed *first*, then implementation continued. The first
slice always surfaces hidden assumptions — capturing them here makes the next slice better without turning
the process into meetings.

---

## The View lifecycle (mandatory for every new/changed View)

```
Proposal → Gate 0 → Gate 1 → … → Gate 7 → Approved → Wireframe → Implementation
```

**Not:** `idea → design → code`. Gate 0 first (*could this be derived instead of created?*); an open
🔴 Blocker stops the lifecycle. A View reaches code **only** with an Approval block recorded.

---

## When to update the Foundation

- **Update a document only when a design decision actually changes** — never during day-to-day
  implementation. The docs are the *source of truth*, not a work log.
- A change to the **pillars, the Tool contract, the agent roster, the Framework model, or the Mission
  Lifecycle** additionally requires an **ADR** and a CLAUDE.md update (per §23).
- Record each approval (Status · Reviewer · Date · Version). Code and the Foundation must never drift; when
  they disagree, one is a bug — fix it.

---

## Architecture & Product Freeze *(the anti-drift rule)*

As of **2026-07-22 the Product Design Foundation is Frozen.** From here the documents are the reference and
implementation is the derivative. The operating rule for every sprint:

> **A sprint starts and ends without editing any Foundational Document — unless implementation is found to
> contradict it.**

- Implementation **matches** the docs → **do not touch the docs.**
- Implementation **reveals a document is wrong** → **stop implementation, fix the document** (with the
  owner's approval — and an ADR + CLAUDE.md update if it touches a pillar), **then continue.**
- **Never** change a document *"because the implementation is easier that way."* Convenience is not a
  reason to move the product; a discovered contradiction is.

This prevents **Product Drift** exactly as ADRs prevent **Architecture Drift**. When code and the
Foundation disagree, one of them is a bug — and the default assumption is that the code is.

---

## Application Contract Freeze *(the anti-over-abstraction rule)*

As of **2026-07-22 the Application-layer contract language is Frozen.** The vocabulary reached during
S2–S3 is the language (ADR 0054): `MissionAccess · MissionWorkflow · ProjectionPort · FrameworkProvider
· DeliverableProvider · Exporter/ExportService · DeliverableBuilder · DeliverableBuilderRegistry`, plus
`CommandContext · CommandResult · CommandContext` and the typed error taxonomy. The goal of ADR 0054 was
never the *most* contracts — it was a **stable language**, and that is reached.

> **No new `Protocol`, `Port`, or `Builder` is added to the Application layer unless implementation
> reveals that an existing contract is genuinely insufficient.**

- A real need surfaced by code → add the contract (that is the layer earning it, as `MissionAccess` /
  `MissionWorkflow` were).
- A contract added "because we might need it one day" → **rejected**; that is the first sign of
  over-abstraction, the mirror image of Product/Architecture Drift.

Just as the Freeze rule catches *drift*, this catches *bloat*. The precedent for a legitimate change is
`retry` / `type-scope`: implementation exposed a genuine gap, so the contract (or a doc) moved — never a
speculative addition.

---

*This document exists so that "the product drives the code" survives growth, turnover, and time. It is the
process that makes the other nine documents binding.*
