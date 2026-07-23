# Slice S6 — Approvals (the decisions waiting for me)

> The hardest slice by *product*, not code: the first screen where **Mission · User · Role · Decision**
> meet. Derived from the **Approvals** View ([../WIREFRAMES_V1.md](../WIREFRAMES_V1.md)) and the
> Approvals queue query ([../REST_API_CONTRACT_V1.md](../REST_API_CONTRACT_V1.md) §4). **Status:** ✅
> **CLOSED** (owner sign-off 2026-07-23, *Approved with changes* — all 5 UX changes applied & verified
> live). UI = **"Decisions"**; the 5-Second Decision Rule; `Open Mission →` + `Review evidence →`;
> recent decisions when nothing waits. **No architectural/contract change** (first slice with none) —
> the whole decision is reused from S2. **Last updated:** 2026-07-23.

---

## Product Question *(the one line every card must serve)*

> ### "What decisions are waiting for me?"

This is **not** a task list, and **not** a Mission list — it is a list of **decisions**. The unit is a
**Decision**; the mission is only its context. A card that reads like a mission row (`Vendor Review ·
Approve · Reject`) has lost the product; a card that reads like a decision (*"Publish Vendor
Assessment — waiting 2 hours — 5 documents of evidence — Approve / Reject"*) has kept it.

**The UI is called "Decisions"** — never "Approvals", "Queue", or "Pending approvals". The user *takes
decisions*, they do not *work a queue*. The implementation keeps its precise internal name
(`ApprovalQueueProjection`, `GET /v1/approvals`), but the product word is **Decisions** — the same
product-language ≠ implementation move as **Deliverable → Result** and **Other → Unclassified**.

---

## Reality Gate — what the system actually provides (before any commit)

*Two questions this time, per the owner.*

**1) Source of Truth — where does an approval come from?** The Core **Mission aggregate**
(`mission.approval: ApprovalRequest`, ADR 0044). It carries: `reason` (the proposed action — with the
consequential step embedded), `requested_at` (→ **waiting since**), `id`, `is_pending`, and `decision`.
The **evidence** behind it is the mission's step results (their citations). The mission lives in the
**Mission Store**.

**2) Can approvals be composed from `MissionReadModel` alone? — NO.**

| A Decision card needs | On `mission-read-model`? | Where it actually lives |
|---|---|---|
| *which* missions are waiting | ✅ `status = awaiting_approval` | the read model (this it CAN do) |
| proposed action (the decision) | ❌ | `mission.approval.reason` (Core) |
| waiting since | ❌ | `mission.approval.requested_at` (Core) |
| the decision id (to act) | ❌ | `mission.approval.id` (Core) |
| evidence (N documents) | ❌ | the mission's step-result citations (Core) |

So the read model can say *who* is waiting but nothing a **decision** needs. **→ a new Approval
Projection is required, and fully justified** (guard 7) — the first read component whose whole reason is
"`MissionReadModel` cannot answer this business question." Exactly the owner's expectation.

**Composable from existing projections?** *No* for the decision detail (above) → a new projection. But
it is **read-only, computed on read** (like S5's Dashboard Projection): it **composes**
`mission-read-model` (to *find* the waiting missions) + the **Mission Store** (to *detail* each one) —
**no new stored table, no projector, no write path.** Materialize only if performance later demands.

**No frozen-contract change needed (a first).** `GET /v1/approvals?status=waiting` **already exists** in
§4, and the S2 `approve`/`reject` command is **reused unchanged** (the aggregate decides its one active
request, so the URL's `{step_id}` is just the decision reference — the same the Work Surface already
uses). The queue item is a **cross-mission composite view** (the Approval + its mission context +
`waiting_since`), which §4 already frames as "cross-mission items" — so it is a view shape, **not** a
change to the §2 `Approval` entity. The contract was right this time.

**To build:** an **`ApprovalQueueProjection`** (computed-on-read: `mission-read-model` + the store) + the
queue-item view/schema + the **Approvals** frontend view (a list of Decision cards). The `approve` /
`reject` actions and the Decision (gate) card are **reused from S2**.

---

## Foundation Reuse *(speak the language, don't reinvent it)*

| Question | Answer |
|---|---|
| Which **Read Model** do I reuse? | **`mission-read-model` (S1)** — to find `awaiting_approval` missions; the **Mission Store** — for each one's approval detail + evidence |
| Which **Query / Command** do I reuse? | **`ApproveMissionStepCommand` / `RejectMissionStepCommand` (S2)** — the decision *actions*, unchanged; the read-model query pattern |
| Which **Presenter / component** do I reuse? | the **Decision (gate) Card** (S2), **status chips**, the **Presenter→Client** layering, the **left rail** (S4), Mission Detail navigation (open the mission for full context) |
| What is **genuinely new**? | `ApprovalQueueProjection` (the cross-mission decision read — a new business question) · the queue-item view/schema · the **Approvals view** (list of Decision cards) — **no new stored table, no new command** |

Expected: **mostly reuse** (the decision *actions* and the *card* are S2's), with the one big new read
component the owner predicted — the **Approval Projection** — fully justified.

---

## Design rules (owner)

1. **The unit is a Decision, not a Mission.** The card *is* a decision; the mission is context. Anatomy:
   ```
   Publish Vendor Assessment        ← the decision (proposed action)
   Vendor Review                    ← mission, as context
   Waiting since 2 hours            ← requested_at
   5 evidence documents             ← the step results behind it
   [ Approve ]  [ Reject ]          ← the primary decision
   Open Mission →                   ← secondary: go to the Work Surface for full context
   ```
2. **The 5-Second Decision Rule.** If a user must open Mission Detail to understand *what they are
   approving*, the card has failed. The card carries the minimum sufficient to decide — proposed
   action · mission (context) · waiting since · evidence count — and no more; the *details* stay in
   Mission Detail. (This is the List-vs-Detail rule, applied to decisions.)
3. **Approve/Reject is not the only CTA.** A user who is not ready to decide needs a way out:
   **`Open Mission →`** is a *secondary* CTA on every card — it opens the mission's Work Surface (S2)
   for the full plan/findings/evidence. This is what wires S6 naturally back to S2.
4. **Reuse the S2 decision, don't rebuild it.** Approve / Reject call the *same* command and Decision
   card the Work Surface uses — the queue is a new *view onto* the same decision, not a second decision
   path.
5. **A queue of decisions, read-only + computed-on-read.** The `ApprovalQueueProjection` composes
   existing sources; it stores nothing and never mutates a mission (writes stay in the S2 command).
6. **Deciding here returns you to the list** — after Approve/Reject, the item leaves (the mission
   resumed); the page reflects "what's *still* waiting", its one question.
7. **Order by age — the longest-waiting decision first.** The page asks *"what has waited longest for
   me?"*, not *"what is newest?"* — so the queue sorts by `waiting_since` ascending (oldest first). An
   explicit rule, not an implementation detail.
8. **When nothing waits, the page stays alive** — a positive banner plus the last couple of decisions
   *already made* (approved / rejected), a read-only history (the same pattern as the Dashboard's
   "Nothing needs attention"). No new command — a decided decision is just the S2 outcome, read back.

---

**Goal.** An Approver opens Approvals and sees every decision waiting for them across all missions — each
card a self-contained decision (proposed action, waiting time, evidence, Approve/Reject) — and acts on
it in place, tenant-scoped.

**User question (rule 11):** *"What decisions are waiting for me?"* · **Primary decision:** approve or
reject this item. *(A decision queue — each card ends in a real decision, so a compact **evidence line**
is shown per card; the full Trust Bar lives on the mission's Result, one click away.)*

---

**Given / When / Then**

```
Given   a tenant T with missions paused at approval gates (and another tenant T2 with its own),
When    an Approver opens Approvals,
Then    they see one **Decision card per waiting approval**, each showing the proposed action, its
        mission (as context), how long it has been waiting, and its evidence count — never a bare
        mission row;
And     Approve / Reject on a card calls the reused S2 command; on success the card leaves the queue
        (the mission resumed) and the count drops;
And     T never sees T2's decisions (fail-closed);
And     opening a card's mission link goes to that mission's Work Surface for full context;
And     no step ids, tool names, or pipeline internals appear — only the decision and its evidence.
```

---

**UX Metrics** (targets — a "No" is a finding)

- Clicks to reach Approvals: **1** (rail).
- Clicks to decide: **1** (Approve / Reject on the card).
- The unit reads as a **decision**, not a mission row (design review Gate 1/6).
- Cross-tenant leakage: **0** (asserted by test).

---

**APIs used** (from the REST API Contract — all already present; nothing invented)

- `GET /v1/approvals?status=waiting` → this tenant's waiting decisions (the Approval Projection).
  Approver (role guard declared; enforcement deferred, like the other guards).
- `GET /v1/approvals?status=decided` → the recent decisions already made (read-only history for the
  empty state; design rule 8). Same endpoint, a query variant — not a contract change.
- `POST /v1/missions/{id}/approvals/{step_id}/approve` · `.../reject` — the **reused S2 command**.

---

**Referenced Design Checklist** — View: **Decisions** *(IA area still "Approvals"; the user-facing word is "Decisions")*

- **Gate 0** delete test: removing it removes the cross-mission decision queue — an Approver has no
  single place to act; a real journey breaks.
- **Gate 1** **user language — a *decision*, not a mission**; "waiting since", "evidence", Approve/Reject.
- **Gate 5** every action ↔ a real endpoint (the queue read; the reused approve/reject command).
- **Gate 6** one question ("what decisions are waiting for me?"); Empty/Loading/Error/Success defined.
- **Gate 7** tenant-scoped, fail-closed; no step-id/tool/pipeline internals surfaced.

---

**Done Definition**

- [ ] An **`ApprovalQueueProjection`** — read-only, computed-on-read (tenant-scoped, fail-closed);
      composes `mission-read-model` (find `awaiting_approval`) + the Mission Store (per-mission approval
      detail + evidence). **No new stored table / projector / write path.**
- [ ] `GET /v1/approvals?status=waiting` returns the tenant's Decision items (proposed action · mission
      context · waiting-since · evidence count · the decision id to act on).
- [ ] Approve / Reject **reuse** the S2 command; on success the item leaves the list.
- [ ] Frontend **Decisions** view (UI word, not "Approvals"/"Queue") — a list of **Decision cards**
      (not mission rows) satisfying the 5-Second Decision Rule; each with a secondary **`Open Mission →`**
      (to S2); reuses the S2 Decision-card styling + commands; Presenter→Client; Empty/Loading/Error/
      Success.
- [ ] Tests green: `uv run pytest` · ruff · mypy --strict (DB-gated skip where Postgres absent).
- [ ] Design Review Checklist → **Approved**; **Slice Retrospective** appended (Reuse Ratio + New
      Component Justification).
- [ ] **No Foundational Document edited** (the §4 endpoint already exists) — unless implementation
      contradicts one → stop / fix / resume.

---

**Approval block** *(filled at verification)*

```
View:      Decisions
Gates:     0✔ 1✔ 2✔ 3✔ 4✔ 5✔ 6✔ 7✔
Findings:  0 🔴 · 0 🟠 · 5 🟡 · 0 🔵
Status:    Approved with changes (owner) → all 5 applied & verified → CLOSED
Reviewer:  Owner (mam0022)
Date:      2026-07-23
Version:   S6 v1
```

**Findings & disposition** *(all frontend/product; no backend contract change beyond a read-only
recent-decisions query on the existing `GET /v1/approvals`)*
- 🟡 **Order by age** (longest-waiting first) → **done + stated as design rule 7** (was already the
  implementation; now explicit in the contract).
- 🟡 **Evidence needs a path, not just a number** → **done**: a `Review evidence →` link on the card
  opens the mission's Work Surface on its **Evidence tab** (decision stays 5-second; evidence is one
  click).
- 🟡 **"No decisions waiting" shouldn't end the page** → **done**: it becomes "✓ Nothing waiting for
  your decision" + **Recent decisions** (last two, approved/rejected) — the page stays alive (design
  rule 8; a read-only `?status=decided`, no new command).
- 🟡 **`Open Mission` must keep context** → **done**: opening a mission from Decisions returns to
  **Decisions** (not the Mission List), via a context-carrying back target.
- 🟡 **Record the methodology line** → **done** (Retrospective + Foundation phase note): *"Product
  Expansion adds questions before it adds behavior."*

---

**Slice Retrospective** *(filled at close — the Learning Unit; guards 5–7)*

1. **Did we edit any Foundational Document?** **No.** The §4 `GET /v1/approvals` endpoint already
   existed; the `?status=decided` recent-decisions read is a query variant, not a contract change. The
   contract was right — a maturity marker.
2. **What did we learn that wasn't visible before implementation?**
   - **The methodology line the whole phase earned:** *"Product Expansion adds questions before it
     adds behavior."* S5 and S6 each added a **new question → a new read (Projection)**, but **no new
     Command, no new Aggregate, no new Domain.** After S4, the product grew by asking the same
     language different questions — exactly the aim of building the Foundation first.
   - A small Reality-Gate correction: **reject → `CANCELLED`**, not `FAILED` (the REST note said
     "Failed"); `FAILED` is executor error, `CANCELLED` is human rejection. So recent-decided scans
     completed + **cancelled**. Caught in one test; no contract change.
3. **Does this affect S7 (New Mission)?** S7 is different — it is the first slice that **adds
   behavior** (creating work), so expect it to *use* new Core operations (`engine.create`/`plan`),
   the first genuinely new command-side of the Product-Expansion phase. Reuse stays high on the read
   side; the write side is the new part.
4. **Decision:** **Close Slice.**
5. **Foundation Reuse Ratio:** `New: 5 · Reused: 13 · Ratio ≈ 72%` — headline: **the decision itself
   (approve/reject) is 100% S2; no new command, no new aggregate, no new domain.** Reused: the two S2
   commands · the Decision (gate) card + styling · `client.approve/reject` · mission-read-model · the
   Mission Store · Presenter→Client · status chips + `timeAgo` · the left rail · Mission-Detail
   navigation · the view→schema mapping · grc-api host plumbing.
6. **New Component Justification** *(the cleanest use of the guard yet):*
   ```
   ApprovalQueueProjection  ✓ answers "what decisions are waiting?" (+ recent decided) —
                              MissionReadModel cannot; computed-on-read (no table/projector/command).
   DecisionItemView /       ✓ the decision read shapes (a decision, not a mission view).
     RecentDecisionView
   DecisionsPresenter/View  ✓ the UI is genuinely new (a decision queue, not a mission list).
   (approve/reject and the Decision card are REUSED from S2 — no duplicate; no new command)
   ```
