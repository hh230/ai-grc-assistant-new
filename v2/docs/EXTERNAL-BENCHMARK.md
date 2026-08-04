# External Benchmark — is the engine consistent with outside professional opinion?

Every previous measurement asked *"is the engine consistent with itself?"*. This asks the harder
question: **is it consistent with expertise it did not author?**

It exists because the previous report scored "governance advice quality **4/10**" — a number that
was **not derivable** from internal analysis. That score is withdrawn. This is the reference that
was missing.

---

## Method, and its limits stated first

| | |
|---|---|
| Reviewer | GPT-4o, prompted as a Lead GRC Consultant (ISO 27001 LA, NCA ECC / SAMA CSF experience) |
| Organizations | 100 synthetic, stratified; **86 completed** (14 calls failed — see below) |
| Input to the reviewer | the organization's **answers only** |
| Task vocabulary | closed — the engine's own 10 seeds, plus an explicit "missing" escape |
| Temperature | 0 |

**What this is not:**

- **Not the three-way panel requested.** Only `OPENAI_API_KEY` is configured in this repository;
  there are no Anthropic or Gemini keys. This is **one** external reviewer.
- **Not ground truth.** An LLM is a proxy for professional opinion, not a certified consultant. It
  is *an independent reference*, which is the property that matters here — it did not author the
  rules it is judging.
- **Not complete.** 14 of 100 calls failed (concurrency/rate limiting). Reported, not hidden; the
  agreement figures are over the 86 that completed.

**Why the reviewer never sees the engine's plan:** showing it first would anchor it, and the result
would measure agreement-after-suggestion rather than independent judgement.

---

## Headline

| metric | value |
|---|---|
| Tasks both agreed on | 219 |
| Engine only | 42 |
| Expert only | 168 |
| **Jaccard agreement** | **51.0%** |
| **Under-advice ratio** | **4.0×** (expert-only ÷ engine-only) |

**The engine under-advises four times more often than it over-advises.** In a compliance product
that is the dangerous direction: a customer who is told to do too much wastes effort; a customer who
is told to do too little fails an audit believing they were ready.

---

## Where they diverge, and why

| task | both | engine only | expert only | reading |
|---|---|---|---|---|
| `formalize_org_structure` | 19 | 0 | **44** | engine fires only at `absent` — **S1** |
| `plan_internal_audit_cadence` | 17 | 0 | **33** | same |
| `confirm_basics_with_advisor` | 0 | 0 | **33** | expert recommends it deliberately; engine only as a fallback |
| `establish_risk_register` | 21 | 0 | **31** | same as S1 |
| `adopt_technical_security_baseline` | 5 | 5 | **23** | |
| `implement_data_residency_controls` | 1 | **19** | 0 | **engine OVER-advises** |
| `establish_governance_oversight_body` | 27 | **17** | 0 | **engine OVER-advises** — proportionality |
| `draft_foundational_policies` | 33 | 0 | 4 | close agreement |
| `review_personal_data_handling` | 48 | 1 | 0 | **near-perfect agreement** |
| `designate_compliance_owner` | 48 | 0 | 0 | **perfect agreement** |

Two distinct failure directions, now quantified:

**Under-advice (108 cases)** concentrated in exactly the three tasks gated by the binary ladder —
`formalize_org_structure`, `plan_internal_audit_cadence`, `establish_risk_register`. The engine
fires them only at `absent`; the expert recommends them at `verbal` and `documented_unapproved` too.
**This is S1's consequence, measured externally.**

**Over-advice (36 cases)** in `implement_data_residency_controls` and
`establish_governance_oversight_body` — the engine recommends a board and residency controls where
the expert judges them unwarranted.

**Perfect agreement** on `designate_compliance_owner` (48/48) and near-perfect on
`review_personal_data_handling` (48/49). Where the engine's rules are well-specified, it matches
professional opinion exactly. **The machinery is not the problem.**

---

## The four findings, independently confirmed

| finding | engine | external expert | verdict |
|---|---|---|---|
| **S1** — ladder is binary | 1 → 0 → 0 → 0 tasks across `verbal`→`reviewed_periodically` | **4 → 3 → 2 → 2** | **CONFIRMED** |
| **S3** — empty plans | **nothing** | 4 tasks | **CONFIRMED** |
| **S5** — `has_gov_clients` inert | identical | **adds** an oversight body | **CONFIRMED** |
| **S8** — size ignored | 6 tasks for a 1-person firm | **4** — drops the oversight body and audit cadence | **CONFIRMED** |

On S8 the expert dropped precisely the two tasks flagged as disproportionate for a sole trader,
independently.

---

## A negative result worth recording

The reviewer was given an explicit escape to name a task the vocabulary could not express. **It
never used it.** Across 86 organizations, the engine's ten-task vocabulary was judged sufficient.

**The concepts are not missing. The rules that reach them are.** That materially narrows the work:
this is a rule-coverage problem, not a taxonomy-design problem.

---

## What this does and does not license

**Supported by this evidence:**
- The engine agrees with an independent professional reference on **about half** its advice.
- Disagreement is **systematic, not random** — it concentrates in three ladder-gated tasks.
- The dominant error direction is **under-advice, 4:1**.
- S1, S3, S5 and S8 are confirmed by a reference that did not author the rules.

**Not supported:**
- Any claim that the engine is "4/10" or any other score. One LLM reviewer over 86 synthetic
  organizations does not establish professional quality. **That number remains withdrawn.**
- Any claim about real customers, real auditors, or real regulatory outcomes.

**What would establish it:** the same protocol against multiple providers, and against plans
produced by named human consultants for the same organizations. The harness now exists to run it
the moment those keys or those plans are available.

---

## Reproduce

```bash
cd v2/docs   # scripts live with the audit tooling
OPENAI_API_KEY=… python bench100.py
```

Deterministic on the engine side (temperature 0 on the reviewer side reduces, but does not
eliminate, variance — an LLM reviewer is not reproducible the way the engine is, which is precisely
why it advises and never gates).
