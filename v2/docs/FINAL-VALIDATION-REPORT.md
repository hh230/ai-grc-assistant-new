# Final Validation Report

**Verdict: the project is ENGINEERED, not yet KNOWLEDGE-COMPLETE.**

Architecture, security, deployment readiness, reliability, testing and the decision engine's
mechanics are sound. The **knowledge base** is not. Those are different claims, and the difference
is the whole report.

> The next phase is not software engineering. It is **Governance Knowledge Engineering**.

Everything below was rebuilt from zero. No previous baseline was reused. Three of my own earlier
claims were **wrong and are corrected here**.

---

## 1. Executive Summary

**300,000 organizations**, stratified over every reachable combination of the rule-driving signals,
replayed and re-measured from scratch.

| question | answer |
|---|---|
| Does it crash, flake, or contradict itself mechanically? | **No.** 0 unstable replays, 0 explosions, 0 unreachable rules. |
| Is every recommendation traceable to an answer? | **Almost.** 1 of 10 task types has no evidence. |
| Would a senior GRC consultant call some output obviously wrong? | **Yes.** |

The engine is a **sound machine running an under-specified model**. Every defect found is in the
*knowledge*, not the *machinery*.

**The finding that subsumes most others: the 5-level maturity scale is, in decision terms, binary.**

---

## 2. Architecture Health — GOOD

| property | evidence |
|---|---|
| Determinism | 2,000 organizations × 5 replays → **0** divergences |
| Rule reachability | every seeded rule fires somewhere in 300,000 organizations |
| No shadowed rules | no pair of seeds co-fires 100% of the time |
| No dead rules | none |
| Layering | domain has no framework dependencies; `analyze()` is a pure function |
| Repo hygiene | **0** TODO/FIXME/HACK/XXX in `v2`, `devteam`, `apps/web` |
| Branches | only `main`; 14 feature branches merged and pruned |
| Working tree | clean; no stale artifacts tracked |

---

## 3. Decision Engine Health — SOUND MECHANICS

| check | result |
|---|---|
| Stability (Step 9) | **DETERMINISTIC** |
| Decision explosions (Step 4) | **0** of 12,000 single-signal probes exceed 50% churn |
| Impossible sequences | none |
| Dangling dependencies | none (1,500/1,500 clean) |
| Priority stability | every task carries one priority in all organizations |
| Duplicate advice | none |
| Capacity fit | no plan exceeds the organization's own budget |
| Plan size | 0–9 tasks; 513 distinct plans |

---

## 4. Semantic Findings

### S1 — The maturity ladder is effectively BINARY ⚠️ **P1, new, deepest**

For **every** state signal, five levels collapse to **two** outcomes:

| signal | equivalent values |
|---|---|
| `org_structure_state` | `verbal` = `documented_unapproved` = `approved` = `reviewed_periodically` |
| `risk_register_state` | same four are identical |
| `internal_audit_state` | same four are identical |
| `policy_state` | `{absent, verbal}` vs `{documented_unapproved, approved, reviewed_periodically}` |
| `tech_team_maturity` | `absent` vs the other four |

An organization whose risk register is **verbal** receives advice **identical** to one that
**reviews it periodically**. The product asks a five-point question, renders five stars, and acts
on a yes/no. This single fact explains the collisions (S2), the empty plans (S3), and most of the
"why didn't anything change?" behaviour.

### S2 — Decision collisions ⚠️ P1

**3,840 organizations** spanning a maturity spread of **11/16** receive byte-identical plans —
including two organizations both with government clients and personal data, one barely started and
one fully mature.

### S3 — Empty plans ⚠️ P1

**1,152 of 300,000 (0.38%)** receive no tasks at all. The fallback is guarded on
`confidence == "low"`, so it never fires for a confident-but-empty result. *(RFC-1 measured: → 0,
zero regression.)*

### S4 — An organization is penalised for improving ⚠️ P1

Approving your policies makes a 13th question become required; the unanswered question drops
coverage below 0.8; confidence flips low; the fallback fires. **You are told to consult an advisor
because you improved.**

### S5 — `has_gov_clients` never changes the plan ⚠️ P1

Verified three independent ways, now across 300,000 organizations. It flags a **critical** gap and
changes **nothing** in the plan, the priorities, or the schedule.

### S6 — 45% of gaps cannot be traced to a task ⚠️ P2

No gap carries `source_signal_keys`. The advice is right; it cannot be *checked*.

### S7 — One recommendation has no evidence ⚠️ P2

`seed:confirm_basics_with_advisor` fires 2,304 times citing **no answer at all** — the only one of
ten task types that cannot be explained from the interview.

### S8 — Plan content ignores organization size ⚠️ P2

A 1-person firm and a 50,000-person firm receive identical task **sets**; only scheduling differs.

### S9 — Execution capacity is nearly inert ⚠️ P2 *(corrected — see §12)*

Five levels collapse to **two** tiers: `{none, ad_hoc}` → mid, `{allocated_time, dedicated_budget,
dedicated_team_and_budget}` → large. An organization with **no capacity at all** gets the same
schedule as one with ad-hoc capacity.

### S10 — Partial data residency = no data residency ⚠️ P2

With the cloud pack active, `no` and `partially` produce identical plans. Only `yes` removes the
task. A customer who has partially implemented controls is told nothing has changed.

### S11 — Dead answers ⚠️ P2

`held_licenses` (incl. **ISO certified**, **government licence**), `has_legal_team`, `has_it_team`
influence nothing. 8 of 13 industries are mutually identical.

---

## 5. Software Findings — NONE OUTSTANDING

No TODO/FIXME, no dead code found, no duplicate models, no stale branches, clean working tree.
Earlier software defects (dangling dependencies, outbox never drained, liveness-only health check,
no connection pool, unrotatable secret) are **fixed and merged**.

---

## 6. Performance

| operation | measured |
|---|---|
| `analyze()` | ~1 ms |
| 300,000-organization sweep | ~7 min single-threaded |
| Release gate (300 orgs, full team) | **9–14 s** in CI |
| Outbox drain | 38 events, single batch |

No performance risk in the decision path. **Untested:** behaviour under concurrent production load
(mission execution is inline — see §12 of the readiness matrix).

---

## 7. Security

| control | status |
|---|---|
| Anonymous exposure | **20/20** protected routes refuse anonymous callers |
| Identity leakage | anonymous-safe routes withhold identity |
| Hostile payloads | **8/8** rejected (200KB, SQLi, template injection, NUL, non-JSON) |
| Concurrency | 72 simultaneous requests, consistent, no 5xx |
| Secret rotation | zero-downtime, proven Node→Python, old key revoked |
| Secrets in logs | never; absence + remediation logged instead |
| Tenant isolation | enforced at every store call |

---

## 8. Testing

**56 of 57 packages pass.** `devteam-harness` 198, `grc-api` 122, `governance-discovery` 64.

**One environmental failure, not a code defect:** `retrieval-engine` — 28 pass, 6 need the
`pgvector` extension, which is not installed on this machine
(`vector.control: No such file or directory`). **I could not validate that package here**, and I am
recording it as a coverage gap in my own validation rather than a passing result.

---

## 9. Coverage

| dimension | covered |
|---|---|
| Rule-driving signal space | **exhaustive** (full cartesian product) |
| Capacity tiers | all 5 reached |
| Headcount | 1 → 50,000; no cliffs |
| Locales | en + ar |
| Viewports | desktop + mobile |
| Surfaces | in-process, HTTP, real browser |

**Not covered:** ownership, geography, outsourcing, critical-infrastructure status — **these
signals do not exist in the engine.**

---

## 10. Known Limitations

1. **Only 513 distinct plans** exist for 300,000 distinguishable organizations.
2. The engine cannot represent dimensions that drive NCA/SAMA/PDPL applicability.
3. Maturity is binary in effect while presented as five-point.
4. Mission execution is inline; no queue.
5. No migration ledger (ADR 0045; you approved adding one — not yet built).

---

## 11. Future Research

- A proportionality model: obligations that scale with size, sector and exposure.
- Gap→task linkage as a first-class relation.
- Whether a 5-level ladder should drive 5 distinct behaviours, or be honestly presented as 2.

---

## 12. AI Self-Criticism — three of my own claims were WRONG

| earlier claim | corrected finding |
|---|---|
| "`cloud_data_residency_controlled` is dead" | **Wrong** — it was probed with its pack inactive. It *does* act, but `no` ≡ `partially` (S10). |
| "`tech_team_maturity` is dead" | **Wrong** — same probe error. It acts when the technology pack is active; 4 of 5 levels are equivalent. |
| "`execution_capacity` is dead" | **Wrong** — it does not change plan *content*, but it does change tier and schedule (S9). |

Also withdrawn: a scripted label that read *"gaps that never fire"* while printing gaps that **do**
fire — a reporting bug in my own tooling, not a finding.

**Claims that survived scrutiny:** S1–S8, S11, and every "verified clean" result.

---

## 13. Production Readiness

| area | ready? |
|---|---|
| Software correctness | **Yes** |
| Security posture | **Yes** |
| Determinism / auditability of the mechanism | **Yes** |
| Infrastructure (B1–B4) | **Yes** — closed and merged |
| Deployment | **No** — `grc-api` is not deployed; hosting undecided |
| **Governance advice quality** | **No** — S1–S5 are P1 |

### Would it survive…

| | |
|---|---|
| a customer trusting it? | **Not yet** — a mature organization can be told the same as a beginner (S2). |
| a consultant defending it? | **Not for S1/S5** — "your five-point maturity answer didn't matter" is indefensible. |
| an external audit? | **Partially** — the mechanism is reproducible; 45% of gaps are untraceable (S6). |
| government procurement? | **No** — declaring government clients changes nothing (S5). |
| legal / compliance review? | **Risk** — advice that ignores stated regulatory exposure is hard to defend. |

---

## 14. Remaining Risks

| # | risk | severity |
|---|---|---|
| R1 | A mature customer receives beginner advice and loses trust permanently | **High** |
| R2 | A government-client organization is under-advised (S5) | **High** |
| R3 | 0.38% receive nothing at all (S3) | **High** |
| R4 | An auditor asks "which task closes this gap?" and there is no answer (S6) | Medium |
| R5 | `retrieval-engine` unvalidated in this environment | Medium |
| R6 | Inline mission execution under load | Medium |

---

## Confidence Score

| dimension | score | basis |
|---|---|---|
| **Software correctness** | **9.5 / 10** | 300k organizations, deterministic, 0 explosions, 56/57 suites |
| **Security** | **9 / 10** | every probe repelled; not yet exercised in production |
| **Mechanical auditability** | **8 / 10** | reproducible; gap traceability missing |
| **Governance advice quality** | **WITHDRAWN — not derivable** | see correction below |
| **Production readiness** | **5 / 10** | code ready; not deployed; advice quality blocks launch |
| **Overall trustworthiness** | **not scorable yet** | depends on the withdrawn dimension |

### Correction — the advice-quality score is withdrawn

The original report scored "governance advice quality **4/10**" and an overall **5.5/10**. **Both
are withdrawn.** They were not derivable from the evidence.

Everything measured here is the engine's consistency **with itself**: determinism, reachability,
collisions, monotonicity, traceability. None of that can produce a number for whether the advice is
*professionally good*. That requires an external reference — expert review, comparison against
consultant-produced plans, or a benchmark — and none was run.

What the internal analysis **does** support, without a score:
- specific, reproducible defects (S1–S11), each with population-scale evidence;
- the claim that those defects live in the knowledge model, not the machinery.

What it does **not** support:
- any numeric rating of advice quality;
- therefore any composite "trustworthiness" score built on it.

Stating an engineering opinion in the grammar of a measured result is exactly the failure this
harness exists to prevent, and I made it in my own report.

**An external reference has since been run** — see `EXTERNAL-BENCHMARK.md`. It measures **51%
agreement** with an independent professional reviewer and a **4:1 under-advice ratio**, and it
independently confirms S1, S3, S5 and S8. It still does not license a quality score: one LLM
reviewer over 86 synthetic organizations is evidence, not a rating.

---

## Stop Condition

I am stopping because I **cannot find another meaningful defect in the mechanism** — not because I
am tired and not because CI is green.

**The repository is NOT ready**, and the proof is S1: a five-point maturity scale that drives a
two-valued decision. Until the knowledge model can distinguish the organizations the product claims
to distinguish, no amount of engineering quality makes the advice trustworthy.

**The machine is ready. The model is not.**
