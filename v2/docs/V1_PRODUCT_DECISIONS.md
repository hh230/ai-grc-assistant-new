# V1 Product Decisions

> **Why this document exists.** V1 was built as a Spike (`v2/apps/mission-web-spike`). Its value is
> not its files — it is the product decisions it proved. This document states every one of them
> **independently of React, Vite, or any host**, so that deleting the Spike loses nothing.
>
> This is the document the Exit Criterion refers to: *"every decision in the Migration Map is
> represented inside the real system, and no decision depends on `mission-web-spike` existing."*
>
> - **Status:** ✅ Approved (Product Owner, 2026-07-23) · extracted in Wave 0
> - **Source:** the *Decision* column of [MIGRATION_MAP.md](./MIGRATION_MAP.md)
> - **Governed by:** [MIGRATION_ASSESSMENT.md](./MIGRATION_ASSESSMENT.md)
> - **Authority:** these are *product* decisions. Where they touch structure, the frozen Foundation
>   documents (`PRODUCT_SPEC_V1`, `INFORMATION_ARCHITECTURE_V1`, `WIREFRAMES_V1`,
>   `CONCEPTUAL_DOMAIN_MODEL_V1`, `INTERACTION_PRINCIPLES_V1`) remain the source of truth. Every
>   decision below was verified against them during the V1 Polish slice.
>
> **How to read a decision.** *What* we decided · *Why* · *Where it was proven*. If implementing it
> requires reading the Spike, the decision is under-stated here — fix this document, not the code.

---

## A. Cross-cutting

### A1 — Product language ≠ implementation language

The user never reads a Core identifier. Exactly one layer turns raw ids into the words the product
speaks, and the wire values never change.

| Status (wire) | Reads as |
|---|---|
| `created` | Created |
| `planned` | Planned |
| `executing` | **Running** |
| `awaiting_approval` | **Awaiting decision** |
| `resumed` | **Running** |
| `completed` | Completed |
| `failed` | Failed |
| `cancelled` | Cancelled |
| `archived` | Archived |

| Type (wire) | Reads as |
|---|---|
| `gap_assessment` | Gap Assessment |
| `risk_assessment` | Risk Assessment |
| `vendor_review` | Vendor Review |
| `policy_generator` | Policy Generator |
| `iso_controls` | **ISO Controls** (not "Iso Controls" — the acronym a compliance officer uses) |
| `simple_question` | **Ask** |

Three renamings hold everywhere in the product: **Deliverable → Result**, **Approvals → Decisions**,
**Knowledge → Evidence**. A generic `_`→title-case transform is not acceptable; it is what produced
"Executing" and "Iso Controls" in the first place.

*Why:* the Foundation froze these words; the implementation had drifted. *Proven in:* `src/labels.ts`.

### A2 — Honesty rules

- **Never fabricate a signal.** Where the Core produces no AI recommendation, the UI says
  *"not available yet"* rather than inventing one.
- **Explain a legitimate zero.** A result with no evidence must say *why* ("No relevant evidence was
  found for this mission yet") and what to do ("Add evidence to improve this result"). This copy is
  required even in production, where zero is rare.
- **Say what unlocks a disabled control**, so a disabled button never reads as broken.
- **Name things by what they are.** Execution steps are called *Execution*, not *Findings*, until
  they genuinely are findings.
- **Fast work must still read as work** — a brief, honest beat of feedback when an action completes
  faster than the user can perceive.

*Why:* trust is the product; a fabricated or unexplained signal costs more than a missing one.
*Proven in:* the Work Surface's Decision Card, the Result page, and the New Mission form.

### A3 — Declared limits of trust

Two statements travel with any coverage figure, verbatim in meaning:

- **"Evidence Mapping — not a compliance attestation."**
- **"Based on completed Gap Assessments only."**

*Why:* the product maps evidence to controls; it does not attest compliance. The line must be visible
where a number could be mistaken for a score. *Proven in:* the Result presenters and the Dashboard.

---

## B. Information architecture

### B1 — Four Product Areas, Dashboard is the landing

**Dashboard · Missions · Decisions · Evidence.** A persistent rail switches between them; the
Dashboard is where a user arrives.

### B2 — Navigation keeps context

A mission opened from Decisions returns to Decisions; one opened from the Dashboard returns to the
Dashboard. The back affordance names its destination.

*Why:* the four areas are four questions, and a user who left one to inspect a detail is still
answering that question. *Proven in:* `src/App.tsx`.

---

## C. Dashboard — "What needs my attention right now?"

### C1 — Attention, not analytics

The Dashboard answers one question. It carries **no** user counts, document counts, or storage
figures. *Dashboard ≠ Analytics.*

### C2 — A fixed order

**Waiting → Running → Failed → Recently completed → Coverage snapshot (last).**

- **Waiting is the primary call to action whenever it is greater than zero** — the eye lands there
  first.
- **Recently completed shows *what* finished** (the last two), not a number.
- **Coverage is last, and it is a snapshot**, never a score, and it carries the A3 caveat.

### C3 — Every card has a journey

No card is decorative: each navigates to the filtered work it represents. The Coverage card leads to
the filtered Gap Assessments — never to a "report".

### C4 — A quiet system still says something

With nothing waiting, running, or failed, the page shows a positive statement rather than emptiness.

*Proven in:* `src/dashboard/DashboardView.tsx`.

---

## D. Missions list

### D1 — The summary strip is an entry point to filtering

Status counts are shown as controls: selecting one filters the list. **The counts are computed
server-side** — the Spike computed them in the browser, which was a workaround, not a decision.

### D2 — The whole row is the click target

A mission row offers exactly one primary decision: open this mission.

### D3 — An empty state that guides

"No missions match" is followed by the two ways out: clear the filters, or start a new mission.

*Proven in:* `src/MissionsView.tsx`.

---

## E. Mission detail — the Work Surface

### E1 — One surface, not several pages

Mission detail is **one** workspace. Its tabs are views of a single mission state — not independent
pages with their own routing or source of truth.

### E2 — Each tab answers one question

| Tab | Question |
|---|---|
| Summary | what is this? |
| Plan | what will it do? |
| Execution | what has it done? |
| Evidence | why? |
| Decisions | what decision is needed? |
| Result | what did it produce? |

Tab keys may remain the Core's; the words the user reads are the product's (A1).

### E3 — A Decision Card, not two buttons

Where a mission pauses, the surface states **why it paused**, the **proposed action**, the **AI
recommendation** (honestly, per A2), and **how much evidence** stands behind it — and only then
offers the decision.

### E4 — Approve/Reject render only for an Approver

Not a 403 after the click. **This is a display rule only** — authorization must additionally be
enforced in the command (ADR 0054 §1). Hiding a control is not enforcement.

### E5 — A Trust Bar at the top

Evidence count · human review state · last updated. The question "can I trust this?" starts on the
Work Surface, not only on the Result.

*Proven in:* `src/mission/MissionDetailView.tsx`.

---

## F. Result

### F1 — The user's word is "Result"

The domain's "Deliverable" never appears in the interface.

### F2 — A fixed, evidence-first order

**Trust Bar → content → Export (last).** The frame comes before the content; the export comes after
the reader has seen what they are exporting.

### F3 — The page never switches on result type

A registry maps a result's kind to its presenter, and the presenter decides both how content renders
and which export formats it offers. **A new result type is an addition, never a page edit** — the
frontend mirror of the backend's builder registry.

### F4 — A Gap Assessment reads evidence-first

Coverage block → Exceptions/Gaps → narrative sections. Gaps are named as gaps.

*Proven in:* `src/result/ResultPage.tsx`, `src/result/presenters.tsx`.

---

## G. Decisions — "What decisions are waiting for me?"

### G1 — The unit is a decision, not a mission

Each card is one decision; the mission is context. A card carries enough to decide in seconds: the
proposed action, the mission, how long it has waited, and the evidence count.

### G2 — One click to the evidence

"Review evidence" opens the mission's Evidence view directly — deciding without seeing the evidence
should never be the path of least resistance.

### G3 — Report the decision's effect, in human terms

After Approve or Reject, say what the decision *did* ("… has resumed", "… was stopped") — the thing
the user was waiting to learn — not the raw current status.

### G4 — The page stays alive when the queue is empty

A positive statement, followed by the decisions already made.

*Proven in:* `src/decisions/DecisionsView.tsx`, `src/decisions/presenter.ts`.

---

## H. Evidence — "What evidence do we have?"

### H1 — The collection is the unit, never the file

Evidence is presented as named collections with counts; the flat file list is not the model. Folders
and formats are not the organizing idea — the evidence's *role* is.

### H2 — Six kinds, in display order

| Kind (wire) | Reads as |
|---|---|
| `policy` | Policies |
| `procedure` | Procedures |
| `standard` | Standards |
| `soc_report` | SOC Reports |
| `risk_register` | Risk Registers |
| `other` | **Unclassified** |

### H3 — "Unclassified" is displayed but never chosen

It is the system's bin for evidence it could not classify — never an author's choice. It is excluded
from the upload picker while remaining a display bucket. The wire value stays `other`.

### H4 — Empty collections are not shown

So "Unclassified" appears — last — only when something is actually unclassified.

### H5 — Upload is a focused panel, not a strip

A titled panel with labelled fields: the evidence type (the collection the file joins), then the
file.

### H6 — An empty state that explains the point

"Upload your policies, procedures, standards, and reports — missions work on your own evidence."

*Proven in:* `src/knowledge/KnowledgeView.tsx`, `src/knowledge/collections.ts`.

---

## I. New Mission — "What work should we start?"

### I1 — Two steps, and no Draft

A form (type + scope), then a **Mission Created review station**. The form is presentation state; it
is never a persisted entity. The Core creates a real Mission, not a draft.

### I2 — The review station is where the human reviews before execution

It answers "what did I create?" first — mission, scope, framework, step count, number of human
approvals — then "how?" with the execution plan. **Start** is the sole primary action; **Back** is
the only other one.

### I3 — Six mission types, named for the work

Gap Assessment · Risk Assessment · ISO Controls · Policy Generator · Vendor Review · Ask. Each is
offered with a one-line description of the work it does. The ids match the server's Mission Catalog;
**the catalog is the source of truth** — the Spike's local copy was a workaround.

### I4 — The framework is shown, never picked

For the types that genuinely assess against a standard, the product states which one, as a sentence
("This Gap Assessment will evaluate your evidence against ISO/IEC 27001:2022"), on the form and again
on the review station. Types that assess against no standard show nothing.

**No picker is invented for data the system does not have.** Today exactly one framework exists as
data; we show the truth.

### I5 — Creation is safe to double-submit

One click never creates two missions.

*Proven in:* `src/newmission/NewMissionView.tsx`, `src/newmission/missionTypes.ts`, `src/labels.ts`.

---

## J. Onboarding

### J1 — A first-use layer, not a changed Dashboard

A brand-new user meets an attention-focused Dashboard with nothing to attend to — the wrong question
for someone who has not started. So the Dashboard is **not** changed; a narrative layer is shown on
top, at first entry only, then dismissed for good.

### J2 — What it says

What the product is · what a Mission is · the three first steps (add evidence → start a mission →
review the result, with citations).

### J3 — Its primary action is "Add evidence"

Because a mission with no evidence produces the empty result the user would otherwise hit first.
Secondary: start a mission. Tertiary: skip.

### J4 — "Seen it" belongs to the account

The one-time flag is recorded on the user's account, not in browser storage.

*Proven in:* `src/onboarding/FirstRunOverlay.tsx`, `src/App.tsx`.

---

## K. Decisions that are architectural, recorded here only as pointers

These were proven in the Spike but are **not** product decisions; they live in
[MIGRATION_ASSESSMENT.md](./MIGRATION_ASSESSMENT.md) §3.2:

- REST is the frontend's only contract — the ViewModel never exceeds the API boundary.
- A framework-agnostic Presenter/ViewModel layer holds load-error state, polling, and permissions.
- A presenter registry makes a new result type an addition.
- Poll only while a subject is active; never block.
- Grouping a flat list into collections is presentation — there is no collections endpoint.
