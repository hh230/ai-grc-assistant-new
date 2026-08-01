# Slice V1 Polish — the last slice before V1 is *Finished*

> **Not a feature. Not a refactor. Not S8.** One slice that gathers every **language, narrative, and
> trust** friction the Zero-Assumption ("fresh eyes") review surfaced across the seven V1 screens, fixes
> them, and — once closed — lets us call V1 **Finished**, not merely *complete*.
>
> **Why this exists.** V1's architecture is done; the fresh-eyes walk found ~14 frictions, and almost
> none were architectural. They sort into three families: **A — product language** (a wrong word), **B —
> narrative** (a missing part of the story), **C — trust** (a contradictory signal). This slice closes A
> and B; C turned out not to be broken (see the Reality Gate). **Status:** ✅ **CLOSED (owner Design
> Review = Approved, 2026-07-23)** — built frontend-only, verified live, plus 3 wording refinements
> applied. #4 answers the user's question ("What will this assess against?") rather than showing a bare
> label. With this slice closed, **V1 is Finished.** **Last updated:** 2026-07-23.

---

## Reality Gate (investigated before any commit)

**Source of Truth.** These are not new reads or writes — they are the *existing* surfaces speaking the
wrong word or telling half the story. The Source of Truth for each item is the screen/label that already
exists; the fix is to make it match a decision the Foundation **already** froze.

**The decisive finding — most "bugs" are the code drifting from frozen product language.** The Foundation
already says **Result** (not Deliverable) and **Decisions** (not Approvals); the frozen Domain Model
already says **the framework is chosen at creation**. The implementation quietly drifted. So the fix is
**the code catching up to the Foundation — never editing the Foundation.** This is the Freeze rule doing
exactly its job (when code and a frozen doc disagree, the code is the bug).

**Trust item #9 (Dashboard 50% vs Result 0%) — reclassified from "Bug" to a C2 artifact, by evidence.**
The Dashboard Coverage snapshot is an **aggregate** across all completed Gap Assessments. On the running
seed, exactly one mission ("Technological controls (ISO 27001)") runs a real executor → coverage **1/2 =
50%**; every other gap mission runs the dev **Echo** executor → **0/0**. The Result screen I opened
happened to be an Echo mission (0/0). Opening the *real* mission's Result shows **50%**, matching the
Dashboard. **The two surfaces are consistent on the same mission; the apparent contradiction is the Echo
environment, not a broken trust signal. The coverage math is sound — no code change.**

**C2 boundary — three frictions share one root cause: the dev Echo executor.** #6 ("0 evidence"), #8
(empty Result body: `echo: …`), and #9 (above) all dissolve the moment a real executor replaces Echo.
**We do not build UX workarounds for Echo.** They are re-verified — not fixed — once real generation runs
(a wiring task, not a V1-Polish label task). The *one* durable piece hiding inside #6 is a genuine
**feedback** gap: even in production, a legitimately-zero-evidence result must say *why* (no matching
evidence) — that copy is in scope; the *frequency* of zero is C2 and is not.

---

## Foundation Reuse (speak the language, don't reinvent it)

- **Reused:** every screen, projection, query, command, endpoint, and Presenter — **unchanged**. This
  slice touches **labels, copy, one first-use overlay, and small feedback strings** — no new read model,
  no new command, no new endpoint, no new projection.
- **Frozen decisions the code must catch up to:** REST_API_CONTRACT / Wireframes (**Result**, not
  Deliverable; **Decisions**, not Approvals) · Conceptual Domain Model (**framework chosen at creation**).
- **Genuinely new here:** *nothing structural.* The only genuinely new UI surface is a **first-use
  overlay** on the Dashboard (shown at first entry only) — a narrative layer, not a screen.
- **Expected Foundation edits: none.** If a fix reveals a real contradiction with a frozen doc → stop,
  fix the doc with approval (Freeze rule) — but the investigation says every item is code-catches-up.

---

## Scope — the fresh-eyes frictions, by family (owner's Phase-2 classification)

### A — Product language *(the code drifted from a frozen word; fix code to match)*
- **#10 `Deliverable` → `Result`** — the Work Surface tab is "Deliverable"; the button inside it already
  says "Open Result". Rename the tab to **Result**. *(Bug — breaks Result≠Deliverable.)*
- **#11 `Approvals` → `Decisions`** — one concept wears five labels: Work Surface tab "Approvals", the
  Dashboard card subtitle "Approvals that need your decision", the Missions summary chip "Awaiting
  approval", and the status badge "Awaiting Approval". Unify to the **Decisions / waiting-for-decision**
  language the dedicated screen already uses. *(Bug — breaks Decisions≠Approvals.)*
- **#12 `Executing` → `Running`** — the Missions status filter says "Executing" while the Dashboard and
  the summary chip say "Running". Pick one user word (**Running**) for the same state. *(Bug — language.)*
- **#13 `Iso Controls` → `ISO Controls`** — the Missions type filter title-cases the internal id; the New
  Mission card is correct. Fix the casing (and any other auto-cased type label). *(Bug.)*
- **(#7-adjacent) `gap assessment:` casing** — the Result subtitle is lowercase vs "Gap Assessment"
  everywhere else. Same family; align. *(minor.)*

### B — Narrative *(a missing part of the story)*
- **#1 "Where do I begin?"** — a brand-new user lands in a data-filled Dashboard with no orientation.
  **Do not change the Dashboard.** Add a **first-use overlay** (first entry only) that answers "start
  here" (what Rasheed is, what a Mission is, upload evidence → start a mission). *(Flow — First-use.)*
- **#6 "Why 0 evidence?"** — when a result carries zero evidence, say *why* (no documents matched this
  scope; add evidence to improve) instead of a bare "0 evidence". *(Feedback — the durable half of C2.)*
- **#7 "What happened after I approved?"** — after Approve, the list updates but nothing says what became
  of the **mission** (resumed / completed). Add a one-line outcome. *(Flow — narrative continuity.)*

### C — Trust
- **#9 Dashboard 50% vs Result 0%** — **reclassified: not a bug (C2 artifact); no code change.** The
  coverage aggregate is correct; re-verify once a real executor runs. Kept here only to record the
  verdict so it is never re-litigated. *(No action beyond documentation.)*

### Flow — small UX *(not language, not narrative)*
- **#2 Upload is a thin header strip** — the primary Upload action is easy to miss; make it prominent (a
  clear panel/step), not an inline strip. *(Flow.)*
- **#5 `Create` disabled with no reason** — hint that **Scope** is required to enable Create. *(Flow.)*
- **#3 `Unclassified` selectable as an upload category** — the story says Unclassified is the **system's
  bin** for what it couldn't classify; it must **not** be an author's creation choice. Remove it from the
  upload-kind options (it remains a display bucket, shown last). *(Bug — contradicts the product story.)*
- **#4 Gap Assessment never says "against what"** — the point that made the reviewer stop. The real
  question is not *"Which framework?"* nor *"Default framework?"* but **"What will this mission assess
  against?"** So this is **not a small label** — it is **answering the user's question as part of the
  story.** **In scope:** on the creation screen, read it as narrative, e.g.
  > **Assessment framework** — ISO/IEC 27001:2022
  >
  > *This assessment will evaluate your evidence against ISO/IEC 27001:2022.*

  and **repeat the same language on the Mission Created review station**, so the user knows (a) *what it
  will be measured against* and (b) *why ISO appears later in the Result* — **without adding any choice.**
  **Show in V1, choose in V2.** **Out of scope (V2):** a framework *picker* — a new capability (more
  frameworks-as-data), not polish. *(This is the methodology's own proof: the Reality Gate forced the
  question "does the system even have more than one framework?" → No → so the fix is "show the existing
  truth," not "build a selector for a capability that doesn't exist." Product Polish, not Feature Creep.)*

### Not changing *(correct as-is)*
- **#14 "documents" inside an Evidence Collection** — a Collection *contains* Documents; the word is
  right. No change.
- **#8 empty Result body (`echo: …`)** — C2 (Echo executor). Deferred; re-verify with a real executor.

---

## Out of scope (explicit)
- No new capability, screen, endpoint, command, or projection. No V2.
- No UX built to compensate for the Echo executor (#8, and the *frequency* of #6/#9).
- No framework **picker** (V2). This slice only *shows* the default framework (#4).
- Wiring a real executor in dev is a separate task (it *un-blocks* re-verification of #6/#8/#9, but is
  not itself V1 Polish).

## Success Criteria (verification — the fresh-eyes test, re-run)
- Re-walk the eight scenarios and re-ask the **9th question** ("any technical term still visible?"):
  **Deliverable, Approvals/Awaiting Approval, Executing, Iso** no longer appear in the UI; the decided
  words (Result, Decisions, Running, ISO) do.
- A brand-new user sees a **"start here"** answer on first entry (#1).
- A zero-evidence result explains **why** (#6); after a decision, the user learns the **mission's**
  outcome (#7); Create tells the user **what unlocks it** (#5); Upload's primary action is **obvious**
  (#2); **Unclassified** is not offer­able at upload (#3); Gap Assessment **states its framework** (#4).
- #9 documented as a C2 artifact (no code change); coverage math re-confirmed on the real-executor
  mission = Dashboard.
- Quality gates green (pytest/ruff/mypy/tsc); **no Foundational Document edited.**

## Done Definition
- [ ] Every A and B item resolved; every Flow item resolved or consciously deferred with a reason.
- [ ] 9th-question re-scan clean; the eight scenarios re-walked with no new-user "stop" on a fixed item.
- [ ] Tenant-scoped, fail-closed preserved; tests green.
- [ ] **No Foundational Document edited** (code caught up to the Foundation).
- [ ] Design Review block + Slice Retrospective appended; decision = **Close Slice → V1 Finished**.

---

**Approval block** *(filled at verification)*

```
Items:     A(#10,#11,#12,#13) · B(#1,#6,#7) · Flow(#2,#3,#4,#5) · C(#9 doc-only) · Not-changing(#8,#14)
Findings:  0 🔴 · 0 🟠 · 3 🟡 · 0 🔵   (all wording; none blocking)
Status:    Design Review = Approved (owner) → 3 wording refinements applied & verified → CLOSED
Reviewer:  Owner (mam0022)
Date:      2026-07-23
```

**Design-Review refinements (owner, all applied & verified live — pure wording, no decision changed):**
- 🟡 **First-run ghost button** → "Explore on my own" replaced by **"Skip for now"** (a universal word;
  the user doesn't yet know what there is to explore).
- 🟡 **Zero-evidence copy** → less internal, two short lines: *"No relevant evidence was found for this
  mission yet."* / *"Add evidence to improve this result."* (dropped the internal word "matched").
- 🟡 **Decision outcome** → human effect, not status: *"Approved — <mission> **has resumed**."* (the user
  pressed Approve and waits to learn *what happened*, not *what the current status is*). Reject reads
  *"…was stopped."* The captured status field was removed as now-unused.

**Verified live (frontend-only; grc-api untouched):** first-run overlay · prominent labeled upload panel
(no "Unclassified" choice) · framework narrative on New Mission + Mission Created (hidden for non-
framework types) · "Enter a scope to continue" hint · Work Surface tabs **Decisions** / **Result** ·
zero-evidence note · decision outcome banner · Missions filters **Running** / **Awaiting decision** /
**ISO Controls** · Dashboard "Decisions waiting for you" · Result title cased "Gap Assessment: …".
9th-question re-scan clean (no Deliverable / Approvals / Executing / Iso in the UI). `tsc -b` + `vite
build` green; no console errors.

**Slice Retrospective** *(filled at close — a **polish** retro, not an architectural one)*

> By owner's ruling: **no Reuse Ratio, no New-Component Justification, no Reality Gate here.** This is not
> an architectural slice — it is a polish slice. The retro answers only three questions:

1. **What was confusing?** The product spoke in more than one voice. The **wrong words** — the machine's
   *Deliverable, Approvals, Executing, Iso* leaking where the user should read *Result, Decisions,
   Running, ISO*. The **missing story** — a new user landing with no "start here"; a result saying "0
   evidence" with no reason; a decision that succeeded but left the mission's fate unsaid. And the
   unanswered question at creation: *"what will this assess against?"*
2. **How did it become clearer?** One shared `labels.ts` made every surface speak the same word for the
   same thing. A first-use overlay answers "where do I begin?" without touching the Dashboard. Zero
   evidence now says why, plainly. A decision now reports its human effect ("the mission has resumed").
   And a Gap Assessment states its framework at creation — *showing* the one framework the system has,
   not building a picker for frameworks it doesn't.
3. **Did any screen's question change?** — **No.** Every screen still answers the exact same single
   product question it did at close of S7. V1 Polish changed only *language, story, and feedback* — it
   made S1–S7 read the way they were always meant to, and moved not one screen's question. *(And no
   Foundational Document was edited — the code caught up to the frozen words; #4 was even a frozen
   decision the code had quietly dropped; #6/#8/#9 proved to be one C2 root cause, not three UX bugs.)*
