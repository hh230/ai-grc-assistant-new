# Product Backlog — every open finding, ordered by impact

**Nothing here is being worked on.** Ordered by measured impact; the owner picks.

Every item was re-verified against the **current** engine on 2026-08-05, after the recent fixes —
nothing is carried forward on the strength of an older run.

Impact = how many organizations are affected × how wrong the consequence is. "Cases" are from the
100-organization external-reviewer comparison; "population" from deterministic sweeps.

---

## P1 — the product gives measurably wrong or missing advice

### 1. Industry does not change the advice — 8 of 9 industries are identical
`primary_activity` distinguishes **only** `technology`, and only when the organization has no IT
team. Healthcare, financial services, government, retail, education, manufacturing and
construction all receive **identical** plans.

> A customer picks their industry from 13 options and it changes nothing. In GRC, sector *is*
> applicability: healthcare and financial services carry obligations construction does not.

**Verified:** 8 values → 1 identical plan. **Effort:** rules per sector. **Risk if ignored:** the
most visible "this tool doesn't know my business" failure.

### 2. Certifications are ignored — `held_licenses` is dead
`iso_certified`, `government_license`, `industry_specific_license`, `none` → **identical plan**.

> An ISO-certified organization is told to draft foundational policies. A government-licensed one
> gets no additional obligation. Both are wrong in opposite directions.

**Verified:** 4 values → 1 plan. **Effort:** small (a handful of rules). **Highest value-per-effort
item in this list.**

### 3. Technical maturity is binary — 4 of 5 rungs identical
`tech_team_maturity`: only `absent` differs; `verbal` = `documented_unapproved` = `approved` =
`reviewed_periodically`.

> Exactly the S1 defect that was fixed for the four core signals, still present in the technology
> pack. The fix pattern is known and proven.

**Verified.** **Effort:** small — mirror the approve/review rules already written for S1.

### 4. When should a technical security baseline be recommended?
The reviewer wanted `adopt_technical_security_baseline` for **49** organizations; the engine offers
it only at `tech_team_maturity == absent`. Largely the same root as #3, but the scope question is
genuinely open: is a baseline warranted for an organization whose technical practice is *documented
but unapproved*?

**Cases:** 49. **Needs a GRC judgement, not a search.**

### 5. Partial data-residency control counts as none
`no` ≡ `partially`. An organization that has partially implemented residency controls is told
exactly what one with nothing is told.

**Verified:** 2 of 3 values identical. **Effort:** one rule. **Note:** in a PDPL context this is the
signal most likely to be partially true in reality.

### 6. A fully mature organization receives only "confirm the basics with an advisor"
Every ladder at `reviewed_periodically`, board, compliance officer, residency controlled →
**one task**, and it is the low-confidence fallback, which cites **no supporting answer**.

> The best customer gets the weakest, least explainable output in the product.

**Verified.** **Effort:** medium — needs a "what does good look like next?" concept
(surveillance, continual improvement, ISO 27001 §10).

---

## P2 — the product asks for information it cannot use

### 7. `has_legal_team` is dead
Asked of everyone, influences nothing. **Either make it matter or stop asking.**

### 8. `last_policy_review_date` is dead as a rule input
It is *required* once policies are approved — and no rule ever reads it. It affects the plan only
indirectly, by lowering confidence when unanswered (the mechanism behind the old S4 defect).

> The most misleading kind of dead question: it has a real effect, but not the one the customer
> would assume.

### 9. Execution capacity is nearly inert
Five levels collapse to **two** scheduling tiers, and change plan **content** not at all. An
organization with **no capacity** receives the same plan and nearly the same schedule as one with a
dedicated budget.

**Verified:** `{none, ad_hoc, allocated_time, dedicated_budget}` → one tier.

---

## P3 — known divergence from professional opinion, judgement required

### 10. Review-cadence recommendations (~61 cases)
The engine recommends putting approved-but-unreviewed controls on a cycle; the external reviewer
often does not. **ISO 27001 §5.2/§9.3 support the engine.** Recorded as a legitimate professional
difference — deliberately **not** chased, because over-fitting to one model's opinion is the wrong
move.

### 11. The reviewer recommends an external advisor far more readily (42 cases)
The engine emits `confirm_basics_with_advisor` only as a floor. Whether "get help" is a legitimate
first-class recommendation is a product-positioning question.

---

## P4 — the model cannot represent these at all

### 12. Missing signals: ownership · geography · outsourcing · critical-infrastructure status
These are not gaps in the rules; the engine has **no signal for them**. Each materially drives
applicability under NCA / SAMA / PDPL.

> This is a ceiling on how correct any recommendation can be, independent of rule quality.

**Effort:** large — new questions, new rules, longer interview.

### 13. Interview length is unmeasured
Organizations with an IT team now answer two more questions. We have **no data** on abandonment,
and no principle for how long the interview may become as coverage grows.

---

## P5 — operational, blocks production but not correctness

| # | item | note |
|---|---|---|
| 14 | **`grc-api` is not deployed** | B1–B4 closed. Remaining: Dockerfile, migrate command, read-only→503, staging, harness sweep. **Blocked on the hosting decision.** |
| 15 | Migration ledger | Owner approved; amends ADR 0045; not built. |
| 16 | Metrics · alerting · DR runbook · rehearsed restore | From the readiness matrix; all still ❌. |
| 17 | Mission execution is inline | Declared, not a blocker at current scale; trigger is mission-duration metrics (#16). |
| 18 | `retrieval-engine` unvalidated locally | Needs the `pgvector` extension; 6 tests cannot run on this machine. |

---

## Recommended first pick

**#2 (certifications) and #3 (technical maturity ladder)** — together the highest impact for the
least work: both are small rule additions, #3 reuses a fix pattern already proven on the four core
signals, and both remove a "you asked me and ignored the answer" defect.

**#1 (industry)** is the highest impact overall and the largest piece of genuine GRC knowledge
work — it is the one that most needs your domain judgement rather than my search.
