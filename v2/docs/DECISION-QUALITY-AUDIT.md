# Decision Quality Audit — can we trust every recommendation?

**Status: findings and RFCs. Nothing changed. Every governance rule remains the owner's decision.**

The question this answers is not "do the tests pass". It is:

> Can the AI produce a governance recommendation a senior GRC consultant would call obviously wrong?

**Yes. Six ways.** All are reproducible, all have evidence, and two have clean, measured fixes.

---

## Method

Not random sampling. The engine references **13 signals**; the ones that drive plan seeds are
enumerable, so this walks their **full cartesian product**. Complete coverage of what the engine can
distinguish beats a large random sample of what it cannot.

| sweep | organizations | varied |
|---|---|---|
| Semantic discovery | 30,000 | 4 maturity ladders × 4 booleans × 3 capacities (exhaustive) |
| Failure classes | 10,000 | ladders × booleans (exhaustive) |
| Size / capacity / product | 118,750 | 19 headcounts × 5 capacities × SaaS × tech × cloud |
| Counterfactual | 32,000 probes | every single-signal improvement |
| **Total** | **~190,000** | |

---

## Finding 1 — the safety net is attached to the wrong condition ⚠️ P1

**128 of 10,000 organizations (1.3%) receive a completely empty plan.**

The engine has a fallback for uncertainty:

```python
if confidence == "low" and not plan_seeds:
    plan_seeds = [_LOW_CONFIDENCE_SEED]      # "confirm basics with an advisor"
```

It fires when *"we might be wrong because we did not ask enough"*. It does **not** fire when
*"we asked enough, we are confident, and we produced nothing"* — which is the far more dangerous
state, because the organization reads silence as reassurance.

**Evidence** — an organization scoring 0/5 in governance, risk and cyber:

```
org_structure_state  : verbal
policy_state         : documented_unapproved
risk_register_state  : verbal
internal_audit_state : verbal
→ plan       : []            (nothing at all)
→ confidence : normal (0.833)
```

**Cause:** wrong guard condition, plus a missing concept (below).

---

## Finding 2 — an organization is penalised for improving ⚠️ P1

**320 monotonicity violations.** Improving one axis, changing nothing else, *adds* work.

```
policy_state: documented_unapproved → approved
  before : plan []               confidence normal (0.833)   required coverage 10/12
  after  : plan [confirm_basics_with_advisor]
           confidence LOW (0.769)                            required coverage 10/13
```

**Mechanism, verified:** approving your policies makes a **13th question become required** (when
the policy was last reviewed — only meaningful once one is approved). The unanswered new question
drops coverage below 0.8, confidence flips to low, and the low-confidence fallback fires.

**The organization is told to go consult an advisor because it improved.** No consultant would
defend that, and no test that inspects one plan at a time can see it.

---

## Finding 3 — `has_gov_clients` never changes the plan ⚠️ P1

Confirmed across the whole population: **the plan is byte-identical for every value of
`has_gov_clients`, in 100% of organizations.**

A government-client organization with no compliance officer **is** flagged
`gap:gov_client_without_compliance_officer`, severity **critical** — and receives advice
indistinguishable from a company with no government clients.

**The gap reaches the report. It never reaches the work.** In a KSA context (NCA ECC applicability
is driven precisely by this kind of exposure) that is the single most consequential inert signal.

---

## Finding 4 — 45% of gaps cannot be traced to any task ⚠️ P2

No gap carries `source_signal_keys`, so **nothing — not this harness, not the UI, not an auditor —
can mechanically answer "which task closes this gap?"**.

The answer may exist in someone's head. It does not exist in the data. For a product whose value is
auditability (CLAUDE.md §19), that is a structural defect, not a cosmetic one.

Note this is deliberately *not* claimed as "the gap is unaddressed" — an earlier version of the
check made that claim and was disproved by seed 7, where `designate_compliance_owner` addresses the
gap perfectly. **The advice is right; it just cannot be checked.**

---

## Finding 5 — plan content is completely independent of size ⚠️ P2

A **1-employee** company and a **50,000-employee** company receive the **identical set of tasks**.
Only the schedule differs.

```
1 employee → establish_governance_oversight_body, plan_internal_audit_cadence,
             formalize_org_structure, draft_foundational_policies, …  (7 tasks)
```

Telling a sole trader to establish a governance oversight body is the kind of recommendation that
makes a customer stop trusting the whole plan. Capacity tiers change *when* work is scheduled; they
never change *whether* it is appropriate.

---

## Finding 6 — five questions can never affect anything ⚠️ P2

Of 19 questions asked, these influence no rule and no pack activation:

| question | note |
|---|---|
| `held_licenses` | ISO certified / government licence — highly consequential in GRC, ignored |
| `has_legal_team` | |
| `has_it_team` | |
| `last_policy_review_date` | required in some states (see Finding 2) but never read by a rule |
| `additional_context_note` | free text, unused |

And `primary_activity` (13 industries) only ever activates the technology pack on the single value
`technology` — **the other 12 industries are identical to the engine.**

Asking a question that cannot change the answer costs the customer time and buys trust the system
has not earned.

---

## Verified clean — stated because a negative result is also a result

| property | result |
|---|---|
| Priority stability | every task carries one stable priority in all 10,000 organizations |
| Duplicate advice | no plan contains two tasks resolving the same signal to the same state |
| Dangling dependencies | 0 (fixed earlier; 1500/1500 clean) |
| Plan fits capacity | 0 violations |
| `employee_count` cliffs | none — no ±1 headcount change restructures a plan |
| Impossible sequences | none — no task precedes a prerequisite it declares |

---

# RFCs

## RFC-1 — fire the fallback whenever the plan is empty

**Problem** Findings 1 and 2.
**Change** One line in `governance_discovery/analysis.py`:

```python
- if confidence == "low" and not plan_seeds:
+ if not plan_seeds:
```

**Evidence, 10,000 organizations**

| | baseline | with RFC-1 |
|---|---|---|
| empty plans | 128 | **0** |
| `an_immature_organization_gets_a_plan` | 128 | **0** |
| `gaps_are_traceable_to_tasks` | 4,500 | 4,500 (unchanged) |
| **regression** | — | **none** |

**Blast radius** 128 plans — only those that were previously empty.
**Intent** preserved: the fallback keeps its meaning, it just stops being conditional on a
confidence signal that has nothing to do with whether the plan is empty.

**AI Critic (attacking this proposal, not defending it):**
- *"Would an NCA assessor accept it?"* — Not as a plan. "Confirm basics with an advisor" for a firm
  with government clients and no risk register is **weak advice**.
- *"Does it hide the real problem?"* — Yes. It is a **safety net, not a fix**. It guarantees the
  product never says "nothing to do"; it does not make the advice good.
- *"Traceability?"* — This task carries **no source signals** (256 occurrences), so the user cannot
  see why they were told this. That is Finding 4 again, in the fallback itself.

**Recommendation** Adopt — as a **floor**, explicitly labelled as such, and not as a substitute for
RFC-2. **Confidence: high** (one line, zero regression, exhaustively measured).

---

## RFC-2 — add rules for the states nobody covers

**Problem** Every rule fires on `absent`. Nothing covers organizations that have *started* —
documented but unapproved, or verbal.

**Change** Seven rules, data only, in the pack's existing shape:

| rule | when | emits |
|---|---|---|
| `r:policy_documented_unapproved_seeds_approve` | `policy_state == documented_unapproved` | `approve_policy` |
| `r:org_structure_verbal_seeds_formalize` | `org_structure_state == verbal` | `formalize_org_structure` |
| `r:org_structure_documented_unapproved_seeds_approve` | … | `approve_org_structure` |
| `r:risk_register_verbal_seeds_formalize` | … | `formalize_risk_register` |
| `r:risk_register_documented_unapproved_seeds_approve` | … | `approve_risk_register` |
| `r:internal_audit_verbal_seeds_formalize` | … | `formalize_internal_audit` |
| `r:internal_audit_documented_unapproved_seeds_approve` | … | `approve_internal_audit` |

**Evidence, 10,000 organizations**

| | baseline | with RFC-2 |
|---|---|---|
| empty plans | 128 | **0** |
| **regression** | — | **none** |
| fire rates | — | 20–40% (they discriminate; no rule fires for everyone) |

**Counterexample that shaped it** The first attempt added a `policy_state == verbal` rule too and
introduced **2,000 duplicate-task findings** — `policy_state` already fires at `lte verbal`, so the
new rule double-fired. Only genuinely uncovered states are proposed.

**Why not a threshold change instead** Exhaustively searched: **33 threshold edits, all
semantically destructive, zero clean.** Widening any existing rule enough to catch these states
makes it fire for ~100% of organizations. `SearchExhausted` — **no valid fix exists in that space.**

**AI Critic:**
- *"Would a senior ISO consultant disagree?"* — "Approve the policy" is required by ISO 27001 §5.2
  and NCA ECC 1-1; "formalize roles" by §5.3. Defensible.
- *"Duplicated governance activity?"* — `formalize_internal_audit` may overlap conceptually with the
  existing `plan_internal_audit_cadence`. **Flagged, needs your judgement.**
- *"Unnecessary work?"* — plan sizes shift up (max stays 7). Capacity checks still pass.
- *"Proportionality?"* — inherits Finding 5: a 5-person firm now also gets "approve the internal
  audit charter". Correct in principle, questionable in practice.

**Recommendation** Adopt **six**; hold `formalize_internal_audit` pending your ruling on overlap.
**Confidence: medium-high** — mechanically clean; the GRC judgement is yours.

---

## RFC-3 — make `has_gov_clients` change the plan

**Problem** Finding 3. **No mechanical fix is proposed**, deliberately: what a government-client
organization should additionally *do* is a GRC judgement, not a search result. The tool can prove
the signal is inert; it cannot decide the remedy.

**Options for you:** (a) seed a task, (b) raise priority of existing tasks, (c) accept that it only
affects the gap list, and say so in the UI.

---

## RFC-4 — give gaps `source_signal_keys`

**Problem** Finding 4. **Change** data-model only: gaps carry the signals that triggered them, as
plan seeds already do. Unblocks mechanical gap→task traceability for the UI, auditors and this
harness. **Confidence: high** — additive, no behaviour change.

---

# Backlog

**P1 — critical semantic bugs**
1. Empty plans (RFC-1) — 128/10,000, an organization is told to do nothing.
2. Improvement penalised (RFC-1) — 320 cases; approving policies triggers "consult an advisor".
3. `has_gov_clients` inert (RFC-3) — critical gap never reaches the plan.

**P2 — missing governance concepts**
4. No concept of "started but not finished" (RFC-2) — 7 rules.
5. Gap→task traceability (RFC-4).
6. Plan content ignores organization size (Finding 5) — needs a proportionality model.
7. Five dead questions + 12 equivalent industries (Finding 6).

**P3 — candidate rules** RFC-2's seven, measured and clean.

**P4 — weak heuristics**
- The low-confidence fallback carries no evidence.
- Required-question coverage is state-dependent, which makes confidence unstable under improvement.
- Capacity tier changes at 7 and 80 employees are unexplained by any documented rationale.

**P5 — future research**
- The engine cannot represent **ownership, geography, outsourcing, or critical-infrastructure
  status** — dimensions that materially change obligations under NCA/SAMA/PDPL. This bounds how
  correct any recommendation can be, independent of rule quality.
- Only 129 distinct plans exist for 30,000 distinguishable organizations.

---

# Stopping condition — honest status

| # | condition | met? |
|---|---|---|
| 1 | No new semantic failures after large-scale exploration | **No** — 6 found; the decision-relevant space is now exhausted, but the space itself is small |
| 2 | No clean candidate rule exists | **No** — RFC-1 and RFC-2 are both clean |
| 3 | Every discovered issue has an RFC | **Yes** |
| 4 | Every RFC has evidence | **Yes** — population-scale, reproducible |
| 5 | Every recommendation can be explained | **No** — Finding 4 (45% of gaps) and the evidence-free fallback |
| 6 | Engine behaves consistently across the population | **No** — Finding 2 (monotonicity) |

**I am not declaring the audit closed.** Conditions 1, 2, 5 and 6 are open, and each is open for a
reason that is now documented and measured rather than unknown.
