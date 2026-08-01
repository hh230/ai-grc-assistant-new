# Execution Contracts

> **The bridge from design to code.** The Foundation (`../`) says *what the product is*. An **Execution
> Contract** says, for one slice, **what the user will count as success** — written *before* any code, and
> verified *after*. This inverts the build order: `Execution Contract → Backend → API → Frontend →
> Acceptance Verification`, never starting from the technical layer.
>
> Governed by [../PRODUCT_DEVELOPMENT_PROCESS.md](../PRODUCT_DEVELOPMENT_PROCESS.md) and sequenced by
> [../V1_EXECUTION_PLAN.md](../V1_EXECUTION_PLAN.md).

## Rules

- **One page per slice**, `S<n>_<NAME>.md`.
- **Open with the Reality Gate** (before the first commit): first name the **Source of Truth** for the
  slice (the component that owns the state it reads/writes), then investigate what the system *actually*
  provides — Core, builders, storage, whatever it depends on — and build the contract on reality, not
  assumption. ("What is the Source of Truth?" → "What can the system do / store today?" — never "what do
  we want to show?")
- **Then the Foundation Reuse block** (S5 onward): name the existing Read Model / Query / Presenter this
  slice reuses, and the one genuinely new thing. Mostly reuse ⇒ the Foundation works; mostly invention ⇒
  the slice is re-inventing — stop and ask why. Record a Foundation Reuse Ratio in the Retrospective,
  plus a one-line justification for each new component (a new *concept* is welcome; a *duplicate* is
  flagged — "every new component is justified", never "new is bad").
- **Authored just-in-time** — write a slice's contract immediately before building that slice, not in bulk.
  Its acceptance is informed by what earlier slices taught us.
- **Acceptance appears twice** — as *definition* here, and as *verification* in the slice's Done check.
- **This is not a Foundational Document** — it derives design into code; it does not add product decisions.
  If writing one reveals a Foundation doc is wrong, stop and fix the doc (the Freeze rule).

## Template

```
# Slice S<n> — <Name>

**Reality Gate**
- Source of Truth: <the component that owns this slice's state>
- Exists today: <what the system actually provides / stores>
- Composable from existing projections? <Yes → no new projection · No → justify under guard 7>
- To build: <the §3 gap this slice fills>

**Foundation Reuse** (S5 onward — speak the language, don't reinvent it)
- Read Model reused: <existing *-read-model, or "new: …">
- Query reused: <existing Application query, or "new: …">
- Presenter / registry reused: <Trust Bar / a Registry / Collections, or "new: …">
- Genuinely new here: <the one thing this slice actually adds>

**Goal.** <one sentence: the user outcome this slice delivers>

**Given / When / Then**
Given  <the user's starting context>
When   <the action they take>
Then   <observable, verifiable outcomes — including tenant isolation>

**UX Metrics** (targets — a "No" is a finding)
- Clicks to reach: <n>
- Time to first paint: < <t>
- <other measurable success signals>

**APIs used** (from the REST API Contract — no invented endpoints)
- <METHOD /v1/…>

**Referenced Design Checklist**
- View: <name> · Gates 0–7 must pass · notable gates: <…>

**Done Definition**
- [ ] Given/When/Then all hold; UX metrics met
- [ ] Design Review Checklist → Approved (block recorded)
- [ ] Tenant-scoped, fail-closed; tests green (pytest/ruff/mypy)
- [ ] No Foundational Document edited (unless contradicted → stop/fix/resume)
- [ ] Slice Retrospective appended; decision = Close Slice

**Slice Retrospective** (appended at close — the Learning Unit)
1. Did we edit any Foundational Document? Yes/No — if yes, which & why?
2. What did we learn that wasn't visible before implementation? (1–2 notes)
3. Does this affect the next slice? Yes/No.
4. Decision: Close Slice | Rework.
5. (S5+) Foundation Reuse Ratio: New: <n> · Reused: <n> · Ratio: <n>%
6. (S5+) New Component Justification — one line per NEW component:
   <Component>  ✓ <why it's a new concept, not a duplicate>
   <Component>  ⚠ duplicates <existing> — refactor candidate for S<n>
   (rule: every new component is justified — not "new is bad"; flag duplicates honestly)
```

## Contracts

| Slice | Contract | Status |
|---|---|---|
| S1 | [S1_MISSION_LIST.md](./S1_MISSION_LIST.md) | ✅ **Closed** (owner sign-off 2026-07-22) |
| S2 | [S2_MISSION_DETAIL.md](./S2_MISSION_DETAIL.md) | ✅ **Closed** (owner sign-off 2026-07-22) |
| S3 | [S3_DELIVERABLE.md](./S3_DELIVERABLE.md) | ✅ **Closed** (owner sign-off 2026-07-22) |
| S4 | [S4_KNOWLEDGE.md](./S4_KNOWLEDGE.md) | ✅ **Closed** (owner sign-off 2026-07-22) |
| S5 | [S5_DASHBOARD.md](./S5_DASHBOARD.md) | ✅ **Closed** (owner sign-off 2026-07-23) — first Product-Expansion slice |
| S6 | [S6_APPROVALS.md](./S6_APPROVALS.md) | ✅ **Closed** (owner sign-off 2026-07-23) — no contract change |
| S7 | [S7_NEW_MISSION.md](./S7_NEW_MISSION.md) | ✅ **Closed** (owner sign-off 2026-07-23) — first *behavior* slice; **V1 surface complete** |
| — | [V1_POLISH.md](./V1_POLISH.md) | ✅ **Closed** (owner Design Review = Approved, 2026-07-23) — the final slice (language·narrative·feedback); closed the fresh-eyes frictions → **V1 Finished**. Not a feature, not S8. |

**All seven slices are Closed, and the V1 Polish slice with them — V1 is Finished.** Foundation (S1–S4)
built the language; Product Expansion (S5–S7) used it — two new reads (Dashboard, Decisions) and the one
new behavior (New Mission: create + start). The **Zero-Assumption Product Review**
([../V1_ONE_QUESTION_REVIEW.md](../V1_ONE_QUESTION_REVIEW.md)) walked it as a new user; every friction it
found was language/narrative/feedback — none architectural — and **V1 Polish** closed them. The project
has moved from *forming the system* to *polishing the product*; next is V2, on a stable base.
