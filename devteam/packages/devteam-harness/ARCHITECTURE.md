# Architecture — one responsibility each

```
organizations → answers → runner → store        build an organization, interview it
                            ↓
                        campaign ──→ invariants  is the plan STRUCTURALLY sound?
                            │    └─→ decisions   is the plan sound ADVICE?
                            ↓
  explorer · breaker · saboteur · verifier · regression · sentry · pilot
                            ↓
                    reporter → dashboard → baseline   classify · render · gate
```

**The gate** — every module below runs on every PR.

| | one responsibility |
|---|---|
| `organizations` | Turn a seed into one synthetic organization. |
| `answers` | Decide how it answers any question it is asked. |
| `runner` | Conduct the interview, return the transcript. |
| `store` | Hold a session in memory so the real service runs without a database. |
| `campaign` | Run N organizations, collect everything wrong with each. |
| `invariants` | Say whether a plan is structurally sound. |
| `decisions` | Say whether a plan is sound advice. |
| `results` | Persist every scenario so a failure replays by seed. |
| `reporter` | Group findings into classes, each with one runnable reproduction. |
| `dashboard` | Render a report as a page that outlives the run. |
| `baseline` | Decide whether this run is *worse* than the last accepted one. |
| `__main__` | Be the one command a human or CI runs. |

**The agents** — each asks one question nothing else asks.

| | one question |
|---|---|
| `explorer` | Are we still reaching organizations we have never seen? |
| `breaker` | Does the engine survive hostile input? |
| `saboteur` | Does the running app survive concurrency, double submits, hostile payloads? |
| `verifier` | Across a *range* of seeds, what is wrong? |
| `regression` | Do the seeds that failed *before* still fail? |
| `sentry` | Does the app refuse an unauthenticated caller? |
| `pilot` | Do pages actually **render**, in both locales and both viewports? |

**Surfaces** — how a question reaches the system: in-process · `http` · `browser`, over the
inventory in `routes`.

**Instruments** (`investigation/`) — run by hand, never by the gate: `counterfactual` (if one answer
changed, should the plan have?) · `minimal_fix` (smallest edit that fixes it) · `intent` (does that
edit still MEAN what the rule meant?) · `synthesis` (if no edit works, what rule is missing?) ·
`diff` (what changed, in one line).

---

**Proof of no overlap.** `tests/test_architecture.py` runs the gate in a clean subprocess and
asserts every gate module is loaded on every run, and no instrument ever is. Three overlaps were
found and removed, not explained away:

| overlap | evidence | resolution |
|---|---|---|
| `judge` | nothing imported it; the benchmark I ran used a separate script | **deleted**, 261 lines |
| `verifier` / `regression` | both converted `check_scenario` → findings, differing only in which seeds | merged into `base.findings_for_seed`; Regression keeps only its before/after comparison |
| `sentry` page sweep | measured: anonymous pages return **307**, routes **401** — it re-measured the route sweep, 24 requests at a time | **deleted**; rendering is Pilot's question, asked authenticated |

**Two pairs look like overlap and are not.** `breaker`/`saboteur`: the same idea against different
physics — only a live server, session and browser produce **races**; neither finds the other's bugs.
`invariants`/`decisions`: same mechanism, different question — *"is this data coherent?"* versus
*"is this good advice?"*, kept apart so a release can tell **"the system is broken"** from **"the
system works and its advice is wrong."**
