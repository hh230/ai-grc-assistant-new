# Rasheed V2 — Decision Engine Architecture

- Status: **Implemented** — `v2/packages/decision-engine/`. The status line below dated
  2026-07-12 said "design document only, nothing here is implemented"; that was true when
  written and stale by Phase 12. Corrected 2026-07-16 (Phase 14.5) without touching the
  design content. One structural difference from this document: per-intent routing metadata
  (the workflow catalog) now lives in `pipeline_contracts.intent_registry`, the single source
  of truth every engine reads — the decision-engine keeps the *classification* rules
  (cue patterns) and reads its routing from the registry. See
  [platform-overview](platform-overview.md).
- Date: 2026-07-12 (design) · 2026-07-16 (status corrected)
- Companions: [Knowledge Library](knowledge-library.md), [Chunking Engine](chunking-engine.md),
  [Retrieval Engine](retrieval-engine.md), [ADR 0035](../../../docs/adr/0035-v2-knowledge-library.md);
  and the governing pillars in **CLAUDE.md §3, §7 (the AI Orchestrator), §8 (Missions),
  §9–10 (Tools), §11 (Agents), §16 (fail-safe), §19 (transparency).**
- Scope boundary: **v2/ only.** This designs the deliberation layer that decides *how* a
  request is handled **before** Retrieval runs. It does **not** implement anything, and it
  does **not** design generation/answering, the Retrieval internals ([retrieval-engine.md]
  owns those), or the Mission execution engine (it consumes the plan this produces).

---

## 0. What the Decision Engine is — and what it refuses to assume

Rasheed is a **GRC Intelligence Platform**, not a chatbot and not a generic RAG box. The
single most important consequence:

> **Not every request is a search request.** A generic RAG system embeds whatever the user
> typed and retrieves. That is wrong for a GRC platform, where a request might be a
> multi-step compliance review, a cross-framework mapping, an analysis of an *attached*
> document (no corpus search at all), a comparison that needs several retrieval passes, a
> destructive action that needs a human gate — or just a clarification.

The Decision Engine is the layer that **deliberates before acting**. It turns a raw request
into a governed, inspectable **DecisionPlan** — *what kind of request is this, which
workflow handles it, does it even need retrieval, how many passes, which tools, how much
context, does it need to be decomposed, is it confident enough to proceed or must it ask
first, what needs a human gate* — and only then hands that plan to an executor.

This is **CLAUDE.md §7 applied to the front of the brain**: the Decision Engine is the seat
of control; the LLM is a reasoning engine it *calls* (behind a port, with schema-validated
outputs) for classification and planning — never the thing that silently decides control
flow. The Decision Engine decides; it does not execute.

Two crisp boundaries to avoid confusion with the layer below it:

- **Decision Engine intent ≠ Retrieval intent.** The Decision Engine classifies the whole
  *request/task* ("this is a gap assessment"). The [Retrieval Engine](retrieval-engine.md)
  classifies a *search query* for retrieval strategy ("this query is a `lookup_clause`").
  One Decision may spawn *many* retrieval calls, each with its own retrieval intent.
- **Decision ≠ Execution.** The Decision Engine emits a plan; a Workflow/Mission executor
  runs it; Tools do the work; Retrieval is just one Tool the plan may call.

---

## 1. Position in the architecture

```
        ┌──────────────────────────────────────────────────────────────────────┐
        │  INTERFACES   Workspace UI · API · CLI · SDK · Scheduler · Events      │
        └───────────────────────────────┬──────────────────────────────────────┘
                                         │ request (+ conversation, scope, attachments)
                                         ▼
        ┌──────────────────────────────────────────────────────────────────────┐
        │                       ★ DECISION ENGINE ★  (this document)            │
        │   understand → classify → (confidence gate) → select workflow →       │
        │   plan/decompose → route & select tools → budget context → govern     │
        │                        emits ▼ DecisionPlan  (or Clarification)        │
        └───────────────────────────────┬──────────────────────────────────────┘
                                         │  a governed, inspectable plan
                                         ▼
        ┌──────────────────────────────────────────────────────────────────────┐
        │   WORKFLOW / MISSION EXECUTOR   (CLAUDE.md §8 — runs the plan, owns    │
        │   the lifecycle, human gates, retries, durable state)                  │
        └───────┬───────────────────────────────────────────────────┬──────────┘
                │ calls Tools per the plan                           │
                ▼                                                    ▼
        ┌───────────────────────┐                        ┌───────────────────────┐
        │      TOOL REGISTRY     │  knowledge_retrieval,  │   MULTI-AGENT LAYER    │
        │  (CLAUDE.md §9–10)     │  policy/risk/compliance│  Knowledge · Policy ·  │
        │                        │  intelligence, doc/reg │  Compliance · Risk ·   │
        │                        │  analysis, cross_map,  │  Report · Workflow     │
        │                        │  knowledge_graph, …    │  agents (CLAUDE.md §11)│
        └───────────┬───────────┘                        └───────────────────────┘
                    │ one of the tools:
                    ▼
        ┌───────────────────────────────────────────────────────────────────────┐
        │   RETRIEVAL ENGINE (Phase 6) → cited ContextBundle → generation (later) │
        └───────────────────────────────────────────────────────────────────────┘
```

The Decision Engine is the **planning/routing front** of the AI Orchestrator (CLAUDE.md §7).
Where CLAUDE.md says "the Orchestrator plans, routes, and enforces policy," this document is
the detailed design of *plan and route*; the executor and the human-gate machinery are the
Mission engine's concern.

---

## 2. The internal stages of the Decision Engine

```
 request ─▶ 1 INTAKE ─▶ 2 UNDERSTAND ─▶ 3 CLASSIFY ─▶ 4 CONFIDENCE GATE
                                                          │
                          ┌───────────────────────────────┤
                          │ confident + complete           │ ambiguous / missing params
                          ▼                                 ▼
              5 WORKFLOW SELECTION                  emit CLARIFICATION plan ──▶ (return to user)
                          │
                          ▼
              6 PLANNING / DECOMPOSITION  (single step or a plan DAG)
                          │
                          ▼
              7 ROUTING & TOOL SELECTION  (per step: retrieval? how many passes? which tools?)
                          │
                          ▼
              8 CONTEXT BUDGET PLANNING   (per step: breadth/depth/token budget)
                          │
                          ▼
              9 GOVERNANCE ANNOTATION     (scope, guardrails, human gates, consequential flags)
                          │
                          ▼
             10 EMIT DecisionPlan ───────▶ Workflow/Mission Executor
```

Every stage writes to a **decision trace** (§17). The engine is otherwise stateless per
call; durable state (conversation memory, mission state) lives outside it.

---

## 3. Request Classification *(objective 1)*

### 3.1 The request taxonomy

A **closed** taxonomy of request *classes* — the task the user wants done, not the search
strategy. Distinct from anything in the Retrieval Engine.

| Class | The user wants… | Typically needs |
|---|---|---|
| `lookup` | a specific clause/definition/value | 1 retrieval pass, exact-biased |
| `explanation` | a concept explained, grounded | 1 retrieval pass, synthesis |
| `comparison` | two+ things compared | N passes (one per subject) |
| `compliance_review` | "are we compliant with X" | obligation pass + coverage pass + gate |
| `gap_assessment` | what's missing vs a standard | obligations vs controls/policies, diff |
| `risk_analysis` | risks / scoring / mitigation | risk + control retrieval, analysis |
| `policy_review` | review/critique a policy | policy retrieval (org-scoped) + standards |
| `obligation_extraction` | the obligations in a regulation | law/regulation retrieval, extraction |
| `control_mapping` | controls ↔ requirements/evidence | mapping, graph |
| `cross_framework_mapping` | framework ↔ framework | knowledge graph, dual retrieval |
| `summarization` | summarize something | often the *provided* doc, not the corpus |
| `document_analysis` | analyze an attached/uploaded doc | the attachment; corpus optional |
| `conversation` | meta / greeting / follow-up / off-topic | often **no retrieval** |
| `ambiguous` | (engine can't tell) | → clarification |
| `out_of_scope` | non-GRC / disallowed | safe refusal, no retrieval |

`ambiguous` and `out_of_scope` are first-class outcomes, not error states — a GRC platform
must know when *not* to answer.

### 3.2 How a request is classified

A **hybrid classifier**, deterministic-first, LLM-assisted only when needed — same
"try cheap/precise first, escalate on uncertainty" shape as the Chunking recognizer cascade
and the Retrieval intent classifier.

Signals (cheap, deterministic, computed first):
- **Verb / act cues** ("compare", "assess", "review", "map", "summarize", "extract",
  "what is", "where does it say", Arabic equivalents "قارن", "قيّم", "راجع", "لخّص").
- **Entities** from understanding (§ below): framework names, clause codes, "our policy",
  "gap", "risk", "obligation".
- **Attachments / references**: an uploaded document strongly implies `document_analysis`
  or `summarization` of *that doc*, not corpus search.
- **Conversation context**: a follow-up to a prior mission may inherit or refine its class.
- **Scope hints**: "our" / "my organization" → org-scoped classes (`policy_review`).

The deterministic layer proposes a class + confidence. If confidence is high and unambiguous
→ accept. If ambiguous (two classes close, or a cue conflict) → escalate to the
**LLM-assisted classifier** behind `RequestClassifierPort`, which returns a
**schema-validated** `{class, confidence, rationale, extracted_parameters}` — validated
against the closed taxonomy, never trusted as free text (CLAUDE.md §8 "determinism at the
edges"). Persistent ambiguity → `ambiguous` → clarification (§8), never a guess.

### 3.3 Request Understanding (feeds classification)

Before classification, an understanding pass (reusing much of Retrieval's query
understanding, §2 there): normalize (incl. Arabic §13 of retrieval doc), detect language,
extract entities (frameworks, clause codes, doc-type words, org references, dates),
resolve **anaphora against conversation memory** ("compare *it* with ECC" → *it* = the ISO
27001 from the prior turn), and register **attachments** as first-class inputs. Output:
`UnderstoodRequest { normalized, language, entities, references, attachments, conversation_refs }`.

---

## 4. Workflow Selection *(objective 2)*

### 4.1 Workflows are templates, selected by class + parameters

A **Workflow** is a reusable template describing an ordered/graph of steps, each binding
tools + retrieval passes + context budget + optional human gate. Workflows are **data /
registered templates** (a `WorkflowRegistry`), not hardcoded branches — "workflows as data,"
the same extensibility discipline as the Framework Engine and Document Profile catalog.

| Class | Default workflow | Shape |
|---|---|---|
| `lookup` | **LookupWorkflow** | 1 step: retrieve → cite |
| `explanation` | **ExplanationWorkflow** | retrieve → synthesize (cited) |
| `comparison` | **ComparisonWorkflow** | retrieve×N (per subject) → align → compare |
| `compliance_review` | **ComplianceWorkflow** | extract obligations → find coverage → assess → **gate** |
| `gap_assessment` | **GapAssessmentWorkflow** | obligations ∥ controls/policies → diff → **gate** |
| `risk_analysis` | **RiskWorkflow** | retrieve risks+controls → score → recommend → **gate** |
| `policy_review` | **PolicyWorkflow** | retrieve policy (org) + standards → critique |
| `obligation_extraction` | **ObligationWorkflow** | retrieve regulation → extract obligations |
| `control_mapping` / `cross_framework_mapping` | **MappingWorkflow** | dual retrieve → graph map |
| `summarization` | **SummarizationWorkflow** | (provided doc or scoped retrieval) → summarize |
| `document_analysis` | **DocumentAnalysisWorkflow** | analyze attachment (+ optional corpus) |
| `conversation` | **ConversationWorkflow** | direct / clarify — **no retrieval** |

Selection = `class → default workflow`, then **parameter-driven refinement**: a `comparison`
of *three* frameworks widens the fan-out; a `compliance_review` naming an *attached* policy
swaps the coverage source from the corpus to the attachment. Complex or long-running
workflows are promoted to **Missions** (CLAUDE.md §8) with a full lifecycle; simple ones run
inline.

### 4.2 Workflow diagrams (representative)

```
LookupWorkflow                         ComparisonWorkflow
  [retrieve(exact-biased)]               [retrieve subj A] [retrieve subj B] ... (parallel)
        │                                        └────────────┬───────────┘
        ▼                                                     ▼
  [validate citation] ──▶ result                         [align by structure/code]
                                                              ▼
                                                        [structured compare] ──▶ result

GapAssessmentWorkflow                                  ComplianceWorkflow
  [retrieve obligations (law/reg)]                       [extract obligations]
            │                                                     │
            │        [retrieve controls/policies (org)]           ▼
            └───────────────┬───────────────────────       [retrieve coverage evidence]
                            ▼                                     ▼
                    [map obligation→control]                [assess per obligation]
                            ▼                                     ▼
                    [diff: uncovered obligations]           [compliance verdict + confidence]
                            ▼                                     ▼
                    [★ human review gate]                   [★ human review gate]
                            ▼                                     ▼
                    [assemble gap report + citations]       [assemble review + citations]
```

Every consequential/assertive workflow ends behind a **human gate** (★) — no compliance
verdict or gap finding is presented as fact without the option of human sign-off
(CLAUDE.md §1, §9).

---

## 5. Routing — when Retrieval runs *(objective 3)*

The Decision Engine, **not** the Retrieval Engine, decides *whether and how often* retrieval
happens. Retrieval is a tool the plan schedules; it is never assumed.

### 5.1 When Retrieval is **called**
Any step that must make a grounded GRC claim: lookups, explanations, obligation extraction,
comparisons, coverage checks, mappings, risk/policy work. If the step's output will be cited,
it retrieves.

### 5.2 When Retrieval runs **multiple passes**
- **Comparison / cross-mapping:** one pass per subject/framework, so each side is retrieved
  cleanly before alignment (mixing them in one query is the generic-RAG mistake).
- **Compliance / gap:** an *obligation* pass (law/regulation) **and** a *coverage* pass
  (controls/policies, often org-scoped) — two-sided by nature.
- **Decomposed multi-step (§7):** at least one pass per sub-question.
- **Iterative refinement:** if a pass returns low retrieval confidence / thin evidence, the
  plan may schedule a **re-pass** with widened profiles or relaxed filters (bounded by a
  max-passes budget) before concluding "insufficient evidence."

### 5.3 When Retrieval is **skipped entirely**
- `conversation` (greeting, meta, "what can you do", a pure clarification turn).
- `summarization` / `document_analysis` of an **attached** document — the source is the
  attachment; corpus retrieval is optional/off unless the user asks to compare against the
  library.
- A request **fully answerable from conversation memory** (the answer was just produced).
- `out_of_scope` (safe refusal).
- The **clarification** branch (§8) — you don't retrieve to ask a question.

Routing is expressed per step as `retrieval: { enabled, passes: [PassSpec…], max_passes }`,
where each `PassSpec` is the filter/profile/intent the Retrieval Engine will run.

---

## 6. Tool Selection *(objective 4)*

### 6.1 Capability-based selection over the Tool Registry
The Decision Engine never hardcodes tool names into control flow. It reads the **Tool
Registry** (CLAUDE.md §10), where every tool declares `{capabilities, input/output schema,
side_effect_profile (read-only|consequential), required_permissions, cost/latency hints,
scope}`. The planner matches each step's *required capability* to a tool's *declared
capability* — so a new tool appears by registering, not by editing the engine (CLAUDE.md
§17 plugin architecture).

| Step needs… | Tool capability selected |
|---|---|
| grounded knowledge + citations | `knowledge_retrieval` (the Retrieval Engine, as a Tool) |
| policy critique / coverage | `policy_intelligence` |
| risk scoring / mitigation | `risk_intelligence` |
| control/obligation coverage & verdict | `compliance_intelligence` |
| analyze an attached document | `document_analysis` |
| parse/interpret a regulation | `regulation_analysis` |
| framework ↔ framework / control ↔ evidence | `cross_mapping` + `knowledge_graph` |
| relationship traversal | `knowledge_graph` |
| (future) autonomous sub-task | a registered **AI Agent** (CLAUDE.md §11) |

### 6.2 Selection rules
- **Capability match first**, then filter by **scope** (tenant/org) and **permissions**
  (RBAC/ABAC — CLAUDE.md §20).
- **Read-only vs consequential:** consequential tools (writes, external calls, sign-offs)
  are flagged and get a **human gate** in the plan; they never auto-run on low confidence.
- **Budget-aware:** the planner respects cost/latency hints against the request's budget;
  it prefers the cheapest tool that satisfies the capability.
- **Version-pinned:** the plan pins tool versions (`map_frameworks.v2`) for reproducibility
  (CLAUDE.md §10).

---

## 7. Context Planning *(objective 5)*

Each workflow/step carries a **context budget policy** that the Decision Engine sets and the
Retrieval Engine's Context Assembler ([retrieval §10]) honours. Budgets differ by intent —
depth for precision, breadth for coverage — and are **bounded** (a cost/latency guardrail).

| Workflow | Budget shape | Why |
|---|---|---|
| Lookup | **tight** — few, precise chunks, shallow parent expansion | one right answer; more context = noise |
| Explanation | moderate, single-subject, deeper parent context | needs surrounding meaning |
| Comparison | wide but **partitioned per subject**, equal budget each | fairness across sides |
| Compliance / Gap | **large + structured**, two-sided (obligations ∥ coverage) | the analysis needs both sets whole |
| Policy review | policy doc (fuller) + targeted standards | critique needs the policy in depth |
| Summarization / Doc analysis | the **provided document**, not the corpus | source is the attachment |
| Conversation | ~none | no grounding needed |

A budget is `{token_budget, max_chunks, parent_expansion_depth, per_subject_partition,
breadth_vs_depth}`. Budgets **scale with complexity** but are capped; a multi-step mission
allocates a per-step sub-budget from a total, so a runaway plan can't exhaust cost.

---

## 8. Multi-step Planning *(objective 6)*

### 8.1 Decomposition into a plan DAG
When a request needs more than one workflow, the Decision Engine decomposes it into a
**directed acyclic graph of steps** (a Mission plan): each node is a workflow/tool
invocation with its routing, tools, budget, and gates; edges are data dependencies. The
planner (LLM-assisted behind `PlannerPort`, output schema-validated) proposes the DAG; the
engine validates it is acyclic, every step's inputs are satisfiable, and consequential steps
carry gates — an invalid plan is rejected and re-planned or clarified, never executed.

### 8.2 The worked example

> *"Compare ISO 27001 with ECC and tell me which controls our policy does not cover."*

Classification → a **composite**: `cross_framework_mapping` **+** `gap_assessment`,
org-scoped. Decomposition:

```
        ┌─ S1 retrieve ISO 27001 controls ──┐
        │  (control_mapping, global)         │
 start ─┤                                     ├─▶ S3 cross-map ISO↔ECC ─┐
        │  ┌─ S2 retrieve NCA ECC controls ─┘   (cross_mapping +        │
        │  │  (control_mapping, global)          knowledge_graph)        │
        │  │                                                              ▼
        └─ S4 retrieve our policies ─────────────────────────────▶ S5 coverage/gap analysis
           (policy_intelligence, ORG-scoped)                        (compliance_intelligence:
                                                                     which mapped controls have
                                                                     no covering policy clause)
                                                                             │
                                                                             ▼
                                                                    ★ S6 human review gate
                                                                             │
                                                                             ▼
                                                                    S7 assemble gap report
                                                                       (report agent, cited)
```

- **Dependencies:** S1 ∥ S2 → S3; S4 ∥ (S1,S2); S3 + S4 → S5 → S6 → S7. S1, S2, S4 run in
  parallel (independent retrieval passes) — the Decision Engine marks parallelism the
  executor can exploit.
- **Routing:** four retrieval passes (S1, S2, S4, and any re-pass), plus a graph traversal
  (S3) that is *not* a retrieval call. S6/S7 do no retrieval.
- **Governance:** S5 produces an assertive compliance finding → S6 human gate before it's
  presented as fact.
- **Scope:** S1/S2/S3 global; S4/S5 organization-scoped — the plan carries scope per step.

This is exactly why the engine must never assume "one query → one search": the correct
handling is a *seven-step governed mission*, and the Decision Engine's whole job is to see
that before anything runs.

---

## 9. Confidence & Clarification *(objective 7)*

Confidence is evaluated at two gates, and clarification is a **first-class plan outcome**,
not a failure.

**Ask a follow-up when:**
- **Classification is ambiguous** — two classes near-tied, or conflicting cues.
- **A required parameter is missing** — which framework? which policy/document? which org
  scope? comparison subjects under-specified ("compare our policy" — with *what*?).
- **A consequential action** is implied — confirm intent before anything with side effects
  (CLAUDE.md §9 human-in-the-loop; also the platform-safety rule that consequential/outbound
  actions are confirmed first).
- **Evidence is insufficient after retrieval passes** — the plan can loop back to ask, or
  return an explicit "insufficient evidence," rather than fabricate (CLAUDE.md §12.3, §16).

**Continue automatically when:** classification confidence is high, all required parameters
are present, the step is read-only, and it's within budget.

**Bounded asking.** Clarification is rationed — the engine asks the *fewest* questions that
unblock a valid plan (batch multiple missing params into one prompt), and prefers a
**safe default with disclosure** over a question when a reasonable default exists and the
action is read-only (e.g. "assuming the current ISO 27001:2022 edition"). It never
ping-pongs. A `Clarification` outcome carries the specific missing slots so the UI can ask
precisely.

---

## 10. The full Decision Tree *(objective 8)*

```
                                   ┌───────────────────────────┐
                                   │  INTAKE + UNDERSTAND       │
                                   │  (normalize, entities,     │
                                   │   attachments, conv. refs) │
                                   └─────────────┬─────────────┘
                                                 ▼
                              ┌────────────────────────────────────┐
                              │ out_of_scope / disallowed?          │──yes──▶ SAFE REFUSAL (no retrieval)
                              └───────────────┬────────────────────┘
                                              │ no
                                              ▼
                              ┌────────────────────────────────────┐
                              │ CLASSIFY request (deterministic →   │
                              │ LLM-assist if ambiguous)            │
                              └───────────────┬────────────────────┘
                                              ▼
                       ┌──────────── classification confident & unambiguous? ───────────┐
                       │ no                                                              │ yes
                       ▼                                                                 ▼
             ┌──────────────────┐                                        ┌────────────────────────────┐
             │ required params  │                              ┌─────────│  is class = conversation ? │
             │ present?         │                              │ yes     └─────────────┬──────────────┘
             └───────┬──────────┘                              ▼                        │ no
              no │        │ yes                       CONVERSATION workflow              ▼
                 ▼        ▼                             (no retrieval)         ┌──────────────────────────┐
          ┌───────────────────────┐                                          │ attachment provided &     │
          │ emit CLARIFICATION     │                                          │ class ∈ {summ, doc_anal}? │
          │ (batched missing slots)│                                          └───────────┬──────────────┘
          └───────────────────────┘                                            yes │        │ no
                                                                                    ▼        ▼
                                                                    DOC/SUMMARY workflow   ┌───────────────────────┐
                                                                    (analyze attachment;   │ single class or        │
                                                                     retrieval OFF unless   │ composite / multi-step?│
                                                                     "vs library")          └──────────┬────────────┘
                                                                                          single │        │ composite
                                                                                                 ▼        ▼
                                                                                  select 1 WORKFLOW    DECOMPOSE → plan DAG
                                                                                                 │        │
                                                                                                 └────┬───┘
                                                                                                      ▼
                                                                              ┌──────────────────────────────────────┐
                                                                              │ per step: ROUTE (retrieval? #passes?) │
                                                                              │ SELECT TOOLS (capability match)       │
                                                                              │ BUDGET context · ANNOTATE gates/scope │
                                                                              └───────────────────┬──────────────────┘
                                                                                                  ▼
                                                                              ┌──────────────────────────────────────┐
                                                                              │ any consequential step? → attach ★    │
                                                                              │ human gate                            │
                                                                              └───────────────────┬──────────────────┘
                                                                                                  ▼
                                                                                       VALIDATE plan (acyclic,
                                                                                       inputs satisfiable, budget ok)
                                                                                                  │
                                                                          invalid │               │ valid
                                                                                  ▼               ▼
                                                                        re-plan / clarify   EMIT DecisionPlan ─▶ executor
```

---

## 11. Sequence diagrams *(deliverable)*

**(a) Simple lookup — one pass, no gate**
```
User → DecisionEngine: decide("what does ISO 27001 A.5.15 say?")
DecisionEngine → DecisionEngine: understand + classify → lookup (0.96)
DecisionEngine → User: DecisionPlan{ workflow: Lookup, retrieval: 1 pass (exact-biased), no gate }
Executor → RetrievalTool: retrieve(pass)
RetrievalTool → Executor: cited ContextBundle
Executor → (generation, later phase) → answer + citation
```

**(b) Ambiguous → clarification loop**
```
User → DecisionEngine: decide("review our policy")
DecisionEngine: classify → policy_review, but param 'which policy?' missing
DecisionEngine → User: Clarification{ ask: "which policy — infosec, privacy, or travel?" }
User → DecisionEngine: decide("the infosec one", conversation=prev)
DecisionEngine: resolve via conversation memory → complete → DecisionPlan{ PolicyWorkflow, org-scoped }
```

**(c) Multi-step mission with human gate (the worked example)**
```
User → DecisionEngine: decide("compare ISO 27001 with ECC and which controls our policy misses")
DecisionEngine: classify → composite (cross_map + gap) → DECOMPOSE → 7-step DAG
DecisionEngine → Executor(Mission): DecisionPlan{ steps S1..S7, S6=human_gate }
Executor: S1∥S2∥S4 (retrieval passes) → S3 (knowledge_graph) → S5 (compliance analysis)
Executor → Human: S6 gate — "review 12 uncovered controls before finalizing"
Human → Executor: approve
Executor: S7 assemble gap report (cited) → Mission complete (audited)
```

---

## 12. Data flow *(deliverable)*

```
 request + conversation + scope + attachments
        │
        ▼
 [Intake] ──▶ [Understand] ──▶ UnderstoodRequest
        │                          │  (reads: ConversationMemory, Attachment store)
        ▼                          ▼
 [Classify] ──(reads: taxonomy, LLMReasoner port)──▶ Classification{class, confidence, params}
        │
        ▼
 [Confidence gate] ──(low)──▶ Clarification  ─────────────────────────────▶ return
        │ (ok)
        ▼
 [Workflow select] ──(reads: WorkflowRegistry)──▶ Workflow template
        │
        ▼
 [Plan / decompose] ──(reads: PlannerPort, validates)──▶ Plan DAG
        │
        ▼
 [Route + tool select] ──(reads: ToolRegistry, permissions, scope)──▶ per-step tools + passes
        │
        ▼
 [Budget + govern] ──▶ DecisionPlan { class, workflow, steps[DAG], routing, tools,
        │                              budgets, gates, scope, confidence, trace }
        ▼
   Workflow/Mission Executor        (Decision Engine reads only metadata/registries/memory;
                                     it never reads PDFs, chunks, or embeddings directly —
                                     retrieval is a tool the *executor* calls.)
```

---

## 13. Ports & adapters *(deliverable)*

Hexagonal, consistent with `packages/extraction`, Retrieval (Phase 6), and Embedding
(Phase 4). The orchestrator core knows only the ports.

| Port | Responsibility | Example adapters |
|---|---|---|
| `RequestUnderstandingPort` | normalize, entities, references, attachments | rule-based (default) |
| `RequestClassifierPort` | request class + confidence + params | rules (default) · LLM-assisted |
| `PlannerPort` | decompose complex requests into a validated DAG | template-based · LLM-assisted (validated) |
| `WorkflowRegistryPort` | list/resolve workflow templates | file/DB-backed registry |
| `ToolRegistryPort` | discover tools + capabilities + side-effects | the Tool Registry (CLAUDE.md §10) |
| `ConversationMemoryPort` | short-/long-term, tenant-scoped memory | store-backed |
| `PolicyGuardrailPort` | scope, RBAC/ABAC, budget, safety guardrails | policy engine |
| `LLMReasonerPort` | the LLM as a *called* reasoning engine, structured output | provider-agnostic (reuses Phase-4-style provider abstraction) |
| `ClarificationPort` | render precise follow-up prompts | UI/API |
| `DecisionTracePort` | emit the decision trace to the audit trail | observability sink |

**Hard rule (CLAUDE.md §7):** the LLM is behind `LLMReasonerPort`; its outputs are always
schema-validated structured objects (class, plan) — **never** raw text used as control flow.
The Decision Engine is the seat of control; the model advises, the engine decides.

---

## 14. APIs *(objective 9)*

Deliberation is a **planning call**, cleanly separated from execution — you can inspect a
plan before running it. Also exposed as a Tool (`decide.v1`, six callers, CLAUDE.md §9).

```
POST /api/v1/decide
  request  {
    request_text, language?, scope { tenant_id, organization_id, user_id },
    conversation_id?, attachments?[], hints? { class_override?, budget?, dry_run? }
  }
  response (one of):
    DecisionPlan {
      decision_id, request_class, confidence,
      workflow, is_mission,
      steps: [ { step_id, workflow/tool, capability, retrieval { enabled, passes[], max_passes },
                 context_budget, scope, consequential, human_gate, depends_on[] } ],
      routing_summary { total_retrieval_passes, retrieval_skipped },
      governance { scope, gates[], guardrails_applied[] },
      trace, timings, estimated_cost
    }
  | Clarification { decision_id, missing_slots[], question, options?[] }
  | Refusal       { decision_id, reason }        # out_of_scope / disallowed

POST /api/v1/decide/explain      # full stage-by-stage trace (for the Knowledge Center / audit)
POST /api/v1/plans/{id}/submit   # hand an approved DecisionPlan to the Mission executor
GET  /api/v1/decide/health       # registries loaded, model/prompt versions, guardrail status
```

`dry_run` returns the plan without submitting — the basis for a future "preview what Rasheed
will do" UX and for eval harnesses. Every response carries the **decision trace** (CLAUDE.md
§19) — the plan is reproducible and auditable.

---

## 15. Caching strategy *(deliverable)*

All keys **tenant-scoped**; caches are optimizations, never correctness dependencies.

| Layer | Key | TTL / invalidation | Why |
|---|---|---|---|
| Understanding cache | `hash(normalized_request)` | medium | deterministic per request text |
| Classification cache | `hash(request, conv_context_fingerprint)` | medium | avoid re-running classifier on repeats |
| Plan cache | `hash(request, class, params, scope, registry_versions)` | **short** | plans are context-sensitive; bust on registry change |
| Workflow-template cache | template id + version | static; bust on registry publish | templates change rarely |
| Tool-capability snapshot | registry version | bust on tool (de)registration | selection reads a consistent catalog |
| Guardrail/permission cache | `(user, tenant)` | short; bust on RBAC change | avoid re-evaluating policy each call |

Conversation memory is **state, not cache** (durable, tenant-scoped, retention-governed).
Plan cache keys include **registry versions**, so registering a new tool/workflow cleanly
invalidates stale plans.

---

## 16. Failure handling *(deliverable)*

Fail-safe, always — on uncertainty in a compliance-relevant path, **stop and ask a human**
rather than proceed (CLAUDE.md §16).

| Failure | Behaviour |
|---|---|
| Classifier low-confidence / disagreement | degrade to `ambiguous` → **clarify**, never guess |
| LLM planner timeout / invalid plan | fall back to the class's **deterministic default workflow**, or clarify; never execute an unvalidated plan |
| Required tool unavailable | re-plan with an alternative capability; if none, **degrade with disclosure** ("policy intelligence is unavailable") — never silently drop a step |
| Retrieval returns insufficient evidence (after max passes) | return explicit **"insufficient evidence"** / clarify — never fabricate (CLAUDE.md §12.3) |
| Budget/cost ceiling hit | truncate the plan to the highest-value steps **and disclose**, or ask to proceed |
| Guardrail / scope / permission trip | **block or escalate**; a consequential step never auto-runs |
| Conversation memory unavailable | proceed statelessly + note reduced context |
| Any consequential step + low confidence | **hard stop → human gate** |

Two invariants: (1) a failure never yields an ungrounded or uncited GRC answer; (2) a
consequential action never executes without an explicit gate. Every failure path is
explicit, logged with context, and reflected in the decision trace.

---

## 17. Observability *(deliverable)*

Every Decision is a **reproducible, audited artifact** — CLAUDE.md §19 applied to the
deliberation layer, and the front half of the Mission audit trail (§8).

The **decision trace** records: the request (or a hash for sensitive text), understood
entities, classification + confidence + which layer decided (deterministic vs LLM) + model/
prompt versions, the workflow chosen and why, the full plan DAG with per-step tools/routing/
budgets/gates/scope, every clarification asked, guardrails applied, estimated vs actual cost,
and per-stage timings. Traces stream into the tenant-scoped, append-only audit log and are
surfaceable in the Knowledge Center (a natural "why did Rasheed do that" view).

Metrics (per tenant, per class): classification distribution & confidence, clarification
rate, retrieval-pass counts, workflow distribution, plan validity rate, human-gate hit rate,
decision latency (p50/p95), cost per decision, and safety counters (consequential-without-
gate attempts blocked = must be 0).

---

## 18. Evaluation strategy *(deliverable)*

The Decision Engine is regression-tested as rigorously as Retrieval — and separately, because
it's a different job (routing/planning, not ranking).

- **Golden decision set:** a bilingual, curated set of requests (single-shot and multi-turn,
  with/without attachments) labelled with the **expected** `{class, workflow, routing
  (retrieval passes / skipped), tools, clarify-or-not, gates}`. Includes adversarial cases:
  requests that *look* like search but aren't (summarize this attachment), consequential
  requests (must gate), ambiguous requests (must clarify, not guess), and the composite
  multi-step example.
- **Metrics:**
  - **Classification accuracy** & confusion matrix over the taxonomy.
  - **Workflow-selection accuracy.**
  - **Routing correctness** — did it skip retrieval when it should have, and multi-pass when
    it should have? (the "not every request is a search" property, measured).
  - **Clarification precision/recall** — asked when needed, didn't over-ask.
  - **Plan validity** — emitted DAGs are acyclic, satisfiable, budget-bounded.
  - **Safety** — consequential actions *always* gated; out-of-scope refused (target: 100%).
  - **Decomposition quality** — human-graded rubric on complex multi-step requests.
  - **Latency & cost** per decision.
- **Harness:** offline, reproducible, CI regression gate; planner/classifier changes ship
  behind flags and are A/B'd; `dry_run` plans feed the harness with no side effects.

---

## 19. Extensibility *(objective 10)* & non-goals

**Every future AI capability plugs into this layer without changing its core:**
- **AI Agents (CLAUDE.md §11):** a plan step can be delegated to a registered agent
  (Knowledge/Policy/Compliance/Risk/Report/Workflow) — the agent is selected by capability
  exactly like a tool; the Decision Engine composes agents into missions.
- **Missions (CLAUDE.md §8):** any multi-step DecisionPlan *is* a Mission plan — it carries
  steps, gates, scope, and dependencies the Mission engine executes with a full lifecycle,
  durable state, and replay.
- **Workflows:** new workflow = a registered template (data), picked up by selection; no
  core change.
- **Knowledge Graph:** `cross_mapping`/`control_mapping` route to the `knowledge_graph` tool
  (Knowledge Library §7); as the graph grows (multi-hop), the routing point is already here.
- **Human approval:** gates are first-class plan annotations today — the machinery to pause/
  resume lives in the Mission engine, but the *decision to gate* is made here.
- **Regulatory monitoring:** a decision need not come from a user. A "regulation changed"
  **event** or a **schedule** can invoke `/decide` with a synthetic request ("re-assess
  tenant X against the updated PDPL") — the same planning path, triggered by the event bus
  or scheduler (CLAUDE.md §16 EDA, §9 six callers). The Decision Engine is the common brain
  for user-initiated *and* autonomous work.

**Explicit non-goals for this phase (named, not overlooked):**
- **No code.** Architecture only.
- **No execution engine.** The Decision Engine emits a plan; the Mission/Workflow executor
  (its lifecycle, gate pause/resume, retries, durable state) is a separate design.
- **No generation / answering.** Producing the final grounded answer from a retrieved
  ContextBundle is a later phase.
- **No Retrieval internals** — owned by [retrieval-engine.md]; this document only *routes* to
  it.
- **No new tools built** — this designs how tools are *selected*, per the registry contract;
  each tool is its own implementation phase.

---

*Living design document — the architectural foundation for every future AI capability in
Rasheed. Nothing here is implemented. Proceed to implementation only on explicit approval,
one stage at a time, exactly as the Knowledge Pipeline was built.*
