# assistant-runtime

Rasheed V2 **AI GRC Assistant** — the product-layer runtime ([ADR 0046](../../../docs/adr/0046-v2-ai-grc-assistant.md)).
The Assistant is the gateway that turns a user's request into the **right Mission** and drives it
through the **frozen** Core (`MissionRuntime`). This package is the runtime **mechanism** — it adds no
capability to the Core and changes nothing in it.

> **Slice 2 — Capability & Mission Catalog.** The two registries and the two-layer selection, wired
> to `MissionRuntime`. **Mechanism only** — demo capabilities live in tests.
>
> **Slice 3 — First Capability (Simple Question).** The first real built-in capability
> (`assistant_runtime/builtin/`): the **AI GRC Assistant** capability (`ask`) → a **Simple Question**
> Mission (single read-only step), plus `build_assistant()` — a one-call assembler. Proves the whole
> loop end to end on the real `MissionRuntime`.
>
> **Risk Assessment (MVP, ADR 0047).** The first **composite** capability: `risk_assessment` → a
> multi-step Mission with **domain** step names `collect_context → assess_risk → generate_report` (no
> gate/tools/integrations/scoring). Two rulings baked in: **domain** (not implementation) step names,
> and the **Capability is detection-agnostic** — the `risk` keyword lives in the recognizer config,
> never on the Capability, so an LLM/semantic recognizer swaps in without touching capabilities.
>
> Still out of scope: sessions/conversations (Slice 4), Response Layer (5), Integrations/real
> executor & tools (6), real LLM, streaming, API/UI.

```python
from assistant_runtime import build_assistant

assistant = build_assistant(mission_runtime)          # the frozen MissionRuntime, injected
response = assistant.handle("what does NCA ECC say about MFA?", tenant)
#   response.capability_id == "ask"   (AI GRC Assistant)  →  a Simple Question Mission, COMPLETED
```

## The path a request takes

```
User request
   ↓  Intent Understanding (LLM — suggests, never decides)      [reference: KeywordIntentRecognizer, no LLM]
Capability (+ confidence + inputs)
   ↓  Capability Selector (deterministic — exists? yes/no)
Capability Catalog  ──resolves to──▶  Mission type
   ↓  Mission Catalog (plan factory: (inputs, tenant) → (goal, Plan))
Plan
   ↓  MissionDriver.run_transition   (the one seam into the frozen Core)
MissionRuntime → MissionEngine → … → a durable, audited Mission
```

```python
from assistant_runtime import AssistantRuntime, CapabilityCatalog, MissionCatalog, KeywordIntentRecognizer

assistant = AssistantRuntime(
    missions=mission_runtime,          # the frozen MissionRuntime (injected behind MissionDriver)
    capabilities=capability_catalog,   # product-facing: what the Assistant can do
    mission_catalog=mission_catalog,   # execution: how each Mission type is built
    intent=KeywordIntentRecognizer({"vendor": "vendor_risk_assessment"}),
)
response = assistant.handle("please assess this vendor", tenant)
#   response.capability_id == "vendor_risk_assessment"
#   response.mission        is a real Mission, driven through the Core in ONE run_transition
```

## The layers (each a thin, logic-light piece)

| Piece | Role |
|---|---|
| `Capability` + `CapabilityCatalog` | The **product-facing** registry — *what* the Assistant can do (id, name, description, input schema, resolver). Pure records, **no logic**. |
| `MissionType` + `MissionCatalog` | The **execution** registry — a Mission type is exactly a **plan factory** `(inputs, tenant) → (goal, Plan)` (ADR 0042 §11). |
| `IntentRecognizer` (port) + `KeywordIntentRecognizer` | **Layer 1 of selection** — the LLM *suggests* a `CapabilityIntent` (candidate + confidence + inputs). The reference impl uses keywords, **no LLM**; a real recognizer drops in behind the same port. |
| `CapabilitySelector` | **Layer 2 of selection** — deterministic: does the candidate exist? **yes → it, no → the `simple_question` fallback**. No confidence/validation logic (Slice 2). The anti-hallucination boundary. |
| `MissionDriver` (port) | The **one** seam into the Core — exactly `run_transition`. `MissionRuntime` satisfies it structurally, so the Assistant depends only on `mission-engine` + `pipeline-contracts` and carries **no reverse dependency** into the Core. |
| `AssistantRuntime` | The **thin** composition root: `handle(request, tenant)` = intent → capability → plan → one `run_transition`. |

## Dependencies

```
assistant-runtime ─→ mission-engine       (Plan/PlanStep/Mission/MissionEngine/…)
                  └─→ pipeline-contracts   (TenantContext)
   (dev/test only) ─→ mission-integration + mission-store + psycopg   (real MissionRuntime for the E2E)
```

The **runtime** never imports `mission-store`, `mission-integration`, `event-bus`, or `psycopg` — the
`MissionRuntime` is injected. Enforced by `tests/test_architecture.py` (AST-parsed imports).

## Tests

```
uv run pytest
```

The six Slice-2 proofs: (1) a recognized request → one Mission; (2) an unrecognized request →
`simple_question`; (3) the Mission Catalog builds a drivable `Plan`; (4) `handle` calls the Core
**exactly once**; (5) **no reverse dependency** on the Core (and the runtime depends only on
`mission-engine` + `pipeline-contracts`); (6) **end-to-end against the real `MissionRuntime`** on real
PostgreSQL (DB-gated, auto-skips without a database). Unit tests inject a spy `MissionDriver` and need
no database. `ruff` + `mypy --strict` clean on all source.
