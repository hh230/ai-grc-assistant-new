# DevTeam Ops Dashboard — Architecture & Principles

> Status: **stable / read-only product surface** over a frozen runtime.
> Scope: the `devteam-dashboard` package — the Mission, Agent, and Executive Experiences.
> This document records the architectural principles the dashboard was built under so the
> boundaries that were deliberately frozen are not reopened by future work.

---

## 1. The one-way read model

Every product view is a projection over a single read model. Data flows **one way**:

```
        RuntimeStateView            (frozen — devteam-observability)
                │   (the ONLY read seam: devteam_view_from_journal)
                ▼
    ┌───────────────────────┐
    │  Mission View          │  pipeline_view.py   → /api/pipeline, /api/pipeline/{id}[/stream]
    │  Agent View            │  agents_view.py     → /api/agents, /api/agents/{key}
    └───────────┬───────────┘
                │   (compose the views' own outputs)
                ▼
        Executive View              executive_view.py → /api/executive  (overview + organization)
                │
                ▼
        Executive Insights          (composed inside the same payload: attention / capacity / summary)
```

It is **never** the other way around:

```
        Executive  ──►  new Runtime calculations        ✗  (forbidden)
```

## 2. The governing principle

> **Executive never owns facts. Executive owns composition.**

The Executive layer does not compute any new fact about the runtime. It **composes** facts that
the Mission and Agent layers already produce:

- Per-agent operational metrics come from **`agents_view.agent_metrics(dto, sessions)`** — the same
  function the Agent Inspector renders. The Executive view sums its *additive* fields
  (`session_count`, `active_ms`, `idle_ms`, `decision_distribution`, `missions_*`) across the roster.
- Per-mission tallies come from **`pipeline_view.session_summary(sessions)`** — the same function the
  Mission cards and timeline use.
- The **Insights** layer (Increment 3) computes nothing new at all: it re-arranges the lists and
  counts already assembled for the overview and organization sections into an actionable digest.

Consequence: a fact is defined in exactly one place and counted the same way everywhere. Adding a
fleet-level number never means writing new runtime math — it means summing an existing additive
field. The metrics were **designed additive** for precisely this (per-agent `avg`/`median` are
display-only and never summed; fleet averages recompute from the raw totals).

## 3. Frozen boundaries (do not reopen)

- **Runtime + Observability are in Feature Freeze.** No product increment changed
  `devteam-runtime` or `devteam-observability`. Their test counts were unchanged across every
  increment (observability 56, runtime 45). New product capability lives entirely in
  `devteam-dashboard`.
- **`RuntimeStateView` is the single read source.** The Mission/Agent/Executive views import only
  `devteam_view_from_journal` from `devteam-observability`. They never open or parse the journal
  file, and never import runtime internals. (The journal's mtime is used by the live SSE stream as a
  cheap *change-trigger* only — never read for data.)
- **The Dashboard is presentation-only.** The sole runtime *write* path is the pre-existing
  approve/reject `runtime_gateway` (the Open Missions feature), which drives the existing
  `ApprovalGateway`. It is a separate, intentional seam and is unrelated to the read model above.

## 4. Public API surface (read model)

| Route | Returns | Built from |
|---|---|---|
| `GET /api/pipeline` | observed mission cards | `RuntimeStateView.missions` + `session_summary` |
| `GET /api/pipeline/{id}` | one mission's timeline | `mission_flow` + `mission_sessions` |
| `GET /api/pipeline/{id}/stream` | SSE live timeline | re-reads the above; emits on payload change |
| `GET /api/agents` | live roster | `RuntimeStateView.agents` + `recent_sessions` |
| `GET /api/agents/{key}` | agent inspector (state + timeline + metrics) | `agent_sessions` + `agent_metrics` |
| `GET /api/executive` | command center (overview + organization + insights) | composition of all the above |

Payloads are additive-only DTOs (`dict[str, object]`). New keys may be added; existing keys and
their meaning are the stable contract the SPA renders.

## 5. Navigation hierarchy (drill-down)

The whole product is one connected graph — every aggregate links down to the concrete object:

```
Executive ─► Organization ─► Mission ─► Session ─► Agent
     ▲                                                │
     └────────────────────  Agent ─► Mission  ◄───────┘
```

- Executive / Organization active-mission & insight items → `#pipeline/{id}` (Mission Timeline).
- Mission Timeline session details → `#agents/{key}` (Session → Agent).
- Agent Inspector rows & agent-performance table → `#pipeline/{id}` (Agent → Mission).

## 6. "Never infer missing information"

Where a figure cannot be measured from the data it is returned as `null` and the UI shows
**"insufficient data"** — it is never estimated, predicted, or padded. Examples:

- Median session duration: only with ≥ 3 timed sessions.
- Active/idle window ratio: only with a measurable session span.
- Average completion time: only from **completed** missions' session spans.
- The Operational Summary states observed counts only — no recommendations, no predictions.

*This document is descriptive of what was built and frozen. Changing a boundary here (the read
seam, the composition principle, or Feature Freeze) is an architecturally significant decision and
should be raised explicitly, not drifted into.*
