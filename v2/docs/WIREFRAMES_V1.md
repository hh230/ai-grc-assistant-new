# AI GRC Platform — Low-fidelity Wireframes (V1) · **APPROVED**

> **Views over the State Machine — not Screens.** A View renders one or more **states**; never a 1:1
> screen↔state coupling (Mission Detail is one View with five state variants). **Low-fidelity only** —
> structure, information, relationships; **no colours, no visual identity**. Every **button maps to an
> API Event**; every **View maps to a Screen-Flow State**.
>
> **Each View starts from a single user question** (the strongest framing — the primary *decision* is the
> natural answer to it; formalised as rule 11 in the Design Review Checklist). Each also carries an **ID
> line** (question · decision · delete-test) + a compact map (object · state · events · API · principles)
> + the **9-section template**. **Delete test:** if removing a View breaks no journey, it is redundant.
>
> **Status:** ✅ **APPROVED** (owner) with the five review edits. **Last updated:** 2026-07-22.

---

## View: Onboarding (Empty State)
> **User question:** *"How do I get started?"* · **Decision:** prepare the workspace · **If removed →
> breaks:** first-run (cold start → thin results).

| Object | State | Events | API | Principles |
|---|---|---|---|---|
| Workspace | no knowledge yet | Upload · Try sample | `POST /v1/documents` | 3, 10 |

1. **Goal** empty → first useful mission. 2. **Visible** checklist w/ progress. 3. **Actions** Upload ·
Try sample · Dismiss. 4. **Hidden** ingestion/chunking/embedding. 5–8. Empty=this · Loading="ingesting…" ·
Error=upload failed · Success=≥1 doc ready. 9. **Mobile** single column.
```
Let's prepare your workspace        ▓▓░░ 1/3
☑ Upload your first document   [ Upload ]
☐ Build your knowledge base
☐ Run your first mission
─ Connect sources (coming soon)   [ Try sample data ]
```

## View: Dashboard  *(edit #2 — attention-first, not reports)*
> **User question:** *"What needs my attention?"* · **Decision:** where to act next · **If removed →
> breaks:** the CISO / operator triage path.

| Object | State | Events | API | Principles |
|---|---|---|---|---|
| *(read model)* | — | open · New Mission | `GET /v1/dashboard` | 5, 7, 10 |

1. **Goal** answer "what needs me now?". 2. **Visible — in this order:** **Waiting approvals** → Running
→ Failed → Recently completed → **Coverage snapshot** (last, not first). 3. **Actions** open an item · New
Mission. 4. **Hidden** aggregation queries. 5–8. Empty="No missions yet" · Loading=skeletons · Error=retry
· Success=populated. 9. **Mobile** stacked.
```
Dashboard                                 [ + New Mission ]
▶ Waiting for you (3)   Gap·publish · Vendor·accept risk …
▶ Running (12)          Risk·Customer DB · Policy·AUP …
▶ Failed (1)            ISO·Access — retry
▶ Recently completed    Gap – Technological ↗
Coverage snapshot: 62%
```

## View: Missions (list)
> **User question:** *"Which mission do I open?"* · **Decision:** open/resume one · **If removed →
> breaks:** the practitioner's home; every path to a mission.

| Object | State | Events | API | Principles |
|---|---|---|---|---|
| Mission | any | open · New Mission · filter | `GET /v1/missions?…` | 1, 5 |

1. **Goal** find/resume any mission. 2. **Visible** rows: type · scope · **status** · updated; filters.
3. **Actions** open · New Mission · filter. 4. **Hidden** none. 5–8. Empty="New Mission" · Loading=rows ·
Error=retry · Success=rows. 9. **Mobile** cards.

## View: New Mission  *(states: Selecting Type → Scoping)*
> **User question:** *"What work do I want done?"* · **Decision:** define the mission · **If removed →
> breaks:** starting any work.

| Object | States | Events | API | Principles |
|---|---|---|---|---|
| Mission | SelectingType · Scoping | Create | `POST /v1/missions` (create+plan) | 1, 8, 10 |

1. **Goal** capture intent → create the mission (which lands on Mission Created). 2. **Visible** type
picker → scope + document picker. 3. **Actions** pick type · set scope · attach docs · **Create** · Cancel.
4. **Hidden** plan factory, tools. 5–8. Empty=soft cold-start warning · Loading="building plan…" ·
Error=empty scope · Success=mission created. 9. **Mobile** stacked wizard.
```
Selecting Type            Scoping
○ Ask                     Scope: [________________]
● Gap Assessment    →     Documents: [ + attach ]
○ Risk / Policy / …          • acme-soc2.pdf
                                       [ Create → ]
```

## View: Mission Created (Confirm)  *(edit #5 — new View; internal state = Draft)*
> **User question:** *"Is this mission correct — run it or adjust it?"* · **Decision:** **Run** or
> **Adjust Plan** · **If removed → breaks:** the confirm-before-execute moment (trust + steering).

| Object | State | Events | API | Principles |
|---|---|---|---|---|
| Mission | Draft | Steer Plan · Run | `PATCH /v1/missions/{id}/plan` · `POST …/run` | 1, 4, 10 |

1. **Goal** a confident go/adjust decision before running. 2. **Visible** a *summary card* — Mission type
· Scope · Framework · Knowledge (N documents) · **Estimated duration** (heuristic) · the human-readable
**Plan**. 3. **Actions** **Run Mission** (primary) · **Adjust Plan** (remove/reorder/disable → back to
steering). 4. **Hidden** tools per step. 5–8. Empty=n/a · Loading=n/a · Error=empty plan · Success=run
starts. 9. **Mobile** summary stacks above the plan.
```
Mission · Gap Assessment                     [ Adjust Plan ]
Scope: ISO 27001   Knowledge: 12 documents   Est: ~2 min
Plan:
  ✓ Gather controls
  ✓ Gather evidence
  ✓ Compute gaps
                                             [ ▶ Run Mission ]
```

## View: Mission Detail — the **Work Surface** *(edit #1 — the anchor; five state variants)*
> **User question:** *"What is happening with this mission?"* · **Decision:** continue / approve / open
> the result · **If removed → breaks:** executing & governing all work (the product's centre).

| Object | States | Events | API | Principles |
|---|---|---|---|---|
| Mission | Draft · Running · WaitingApproval · Completed · Failed | Run · Poll · Approve · Reject · Retry | `GET /v1/missions/{id}` · `POST …/run` · `POST …/approvals/{step}/…` | 2, 3, 6, 7, 9 |

**A Mission is a small Workspace, not a page.** Everything about it is reachable here — no page-hopping:
**Plan · Progress · Findings · Approvals · Deliverable · Evidence · Activity Log** (sections/tabs on one
surface).

1. **Goal** run, decide, read, and reach the outcome in one place. 2. **Visible** header (type · scope ·
**status**) + the tabbed surface. 3. **Actions / state variants** (one View — the state changes what's
shown & actionable):
- **Draft** → Plan tab, steerable · action **Run**.
- **Running** → Progress (polled) + Findings streaming w/ citations · action watch/Cancel.
- **Waiting for Approval** → an inline **gate card** (proposed action + evidence) · **Approve** / **Reject**
  *(Approver)*.
- **Completed** → Findings + **Deliverable** tab ready.
- **Failed** → reason · **Retry**.

4. **Hidden** executor/tool routing, pipeline, chunk ids (only citations show). 5–8. Empty=n/a ·
Loading=poll spinner · Error=step failed→Failed · Success=Completed. 9. **Mobile** tabs collapse to a menu;
gate card full-width.
```
Gap Assessment · Technological                         [ WAITING ▍ ]
[ Plan | Progress | Findings | Approvals | Deliverable | Evidence | Activity ]
Progress ▓▓▓▓▓░░ 3/4
✓ Collect evidence  ⟶ [1][2] cited   ✓ Review controls ⟶ [3]
┌ Approval needed ─────────────────────────────────┐
│ Proposed: publish gap findings                    │
│ Evidence: acme-soc2.pdf §2 · A.8.5 · A.8.24       │
│              [ Reject ]         [ Approve ]        │
└───────────────────────────────────────────────────┘
```

## View: Deliverable  *(edit #3 — Trust Bar on top)*
> **User question:** *"Can I trust this output?"* · **Decision:** trust / export · **If removed →
> breaks:** delivering (and trusting) the outcome.

| Object | State | Events | API | Principles |
|---|---|---|---|---|
| Deliverable | Viewing | Export · Open citation · Open mission | `GET …/deliverable` · `…/export?format=` | 6, 3/2, 9 |

1. **Goal** read, verify, export — with trust established first. 2. **Visible — a persistent Trust Bar on
top**, then the content:
```
Evidence coverage ████████░░ 82% │ Framework ISO 27001 │ Sources 17 │ Human review: Approved
─────────────────────────────────────────────────────────────────────────────────────────
Gap Matrix — Evidence Mapping   _mapping, not a compliance attestation_       [ Export ▾ ]
| Control | Title        | Status | Evidence |
| A.8.5   | Secure auth  | cover. | doc-1 ↗  |
| A.8.24  | Use of crypto| gap    |  —       |                        [ Open mission ↗ ]
```
3. **Actions** open citation (→ Evidence/Document) · open mission · **Export (MD/DOCX/PDF)**. **No edit**
(derived, never edited). 4. **Hidden** derivation from step results. 5–8. Empty="available when the
mission completes" · Loading=render · Error=retry · Success=doc+export ready. 9. **Mobile** trust bar
wraps; table scrolls.
*(Trust bar answers "can I trust this?" before "what did the AI write?": coverage · framework · #sources ·
human-review status — Approved / Not required / Pending.)*

## View: Knowledge — **Evidence**, not a File Manager  *(edit #4)*
> **User question:** *"What evidence do we have?"* · **Decision:** is my evidence ready · **If removed →
> breaks:** feeding missions the customer's own data (P1).

| Object | State | Events | API | Principles |
|---|---|---|---|---|
| Document | list | Upload | `GET /v1/documents` · `POST /v1/documents` | 8, 3 |

1. **Goal** manage the tenant's evidence **in GRC language** — this is not Dropbox. 2. **Visible** grouped
by **evidence type**, not files/folders: **Policies · Procedures · Standards · SOC Reports · Risk
Registers** (a document's *file* is the implementation, hidden behind its evidence role). Each item shows
**ingestion status**. 3. **Actions** Upload · open · (delete). 4. **Hidden** the file, chunking, embedding,
pgvector. 5–8. Empty="Upload your first document" · Loading="ingesting…" · Error=failed(retry) ·
Success="ready". 9. **Mobile** grouped cards.
```
Evidence                                            [ Upload ]
Policies        Access Control Policy ....... ready
Procedures      Joiner-Mover-Leaver ......... ingesting…
SOC Reports     Acme Cloud SOC 2 ............ ready
Risk Registers  (none yet)
─ Connected sources (coming soon)
```

## View: Approvals (queue)
> **User question:** *"What decisions are waiting for me?"* · **Decision:** approve / reject · **If
> removed → breaks:** the reviewer / CISO decision path.

| Object | State | Events | API | Principles |
|---|---|---|---|---|
| Approval | WaitingApproval | Approve · Reject | `GET /v1/approvals?status=waiting` · `POST …` | 7, 3 |

1. **Goal** the reviewer's focused decision queue. 2. **Visible** rows: mission · proposed action · evidence
summary · age. 3. **Actions** open (→ Mission gate) · Approve · Reject *(Approver)*. 4. **Hidden** mission
internals. 5–8. Empty="Nothing waiting" · Loading=skeleton · Error=retry · Success=decided→clears.
9. **Mobile** cards.

## Views: Library · Settings *(minimal in V1)*
- **Library** — question *"What does the framework require?"*; browse Frameworks → Controls (read-only).
- **Settings** — question *"How does this workspace behave?"*; Users & Roles (Admin).

---

## The V1 View set (each answers one question · each passes the delete test)

Onboarding · Dashboard · Missions · New Mission · **Mission Created (Confirm)** · **Mission Detail (Work
Surface)** · Deliverable · Knowledge · Approvals · (Library · Settings — minimal). *Every View: one user
question → one primary decision; maps to Screen-Flow states + API events; none redundant.*

**Next:** the **Design Review Checklist**, derived from these real Views — including rule 11 (*every view
answers exactly one user question*), the delete test, and "every button ↔ an API event / every View ↔ a
Screen-Flow state".
