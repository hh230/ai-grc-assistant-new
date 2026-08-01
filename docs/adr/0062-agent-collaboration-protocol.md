# ADR 0062: The Agent Collaboration Protocol — the boundary is the messages; agents are realizations

- Status: **Accepted** (2026-07-26) — owner-approved after reviewing the protocol, before any agent was
  built. **Rule 6 (role→agent resolution) is amended by ADR 0063**: routing is by capability via a
  separate `CapabilityResolver`, and `AgentRole` is demoted to agent identity. Governs every dev-team
  agent (Foreman, QA, Monitor, Security, Developer, Reviewer): each is a *realization* of this
  protocol, never a bespoke class the rest of the system depends on.
- Date: 2026-07-26
- Deciders: **Product Owner**, Architecture
- Related: [docs/devteam/DESIGN.md](../devteam/DESIGN.md) · ADR 0061 (the dev team) · 0005 (multi-agent
  roster) · 0042 (Mission Engine; §12.2 events are summaries; §12.3 the `ExecutionPort` seam) · 0044
  (Human Approval) · 0048 (per-step tool selection, `PlanStep.tool`) · 0051 (inter-step context,
  `StepRequest.prior_results`) · 0056 / 0059 (the boundary-first "one Port, many realizations" pattern
  this mirrors) · 0040 (tenancy) · CLAUDE.md §9 (Tool contract; agents never self-authorize), §11
  (agent roster), §17 (extend at the edges).

## Context

The dev team (ADR 0061) needs agents, but CLAUDE.md §11's roster is unimplemented and **no Agent Runtime
exists**. The owner's ruling was explicit: **do not start from agent classes — start from the messages
the agents exchange**, design them as a boundary exactly as the Extraction Port (0056) and Projection
Port (0059) were designed, reuse the existing Mission contracts wherever possible, duplicate nothing in
the Core, and review the protocol before any agent is implemented.

The risk being avoided: a monolithic agent framework, or six ad-hoc agent classes wired to each other,
that duplicates the lifecycle / events / audit / gating the frozen Core already provides.

## Decision

**The collaboration protocol is the boundary; agents are realizations of it. It reuses the frozen Core
and duplicates nothing.**

1. **One seam.** Every agent realizes a single-method Protocol (like `ExtractionPort`/`ProjectionPort`):

   ```python
   class Agent(Protocol):
       @property
       def role(self) -> AgentRole: ...
       def handle(self, request: AgentRequest) -> AgentResult: ...
   ```

   The system depends on this protocol, never on a concrete agent. New agents are added at the edge
   (§17) without touching the Core.

2. **Six messages, each mapped onto the Core — no duplication** (package `devteam-protocol`):
   - `AgentRequest` — built from a mission-engine **`StepRequest`** via `agent_request_from_step`,
     reusing `TenantContext`, `mission_id`, `step_id`, `instruction`, and the consequential flag.
   - `AgentResult` — **folds down to a `StepResult`** via `agent_result_to_step`
     (`ok`/`output`/`source_ids`/`confidence`/`warnings`).
   - `AgentFinding` — the **one** finding concept (renamed from the Phase-0 `DevFinding`), living in
     `devteam-contracts`, re-exported by the protocol.
   - `AgentDecision` — a **machine verdict** (`AgentVerdict`: proceed/approve/request_changes/block/
     escalate/abstain), deliberately **distinct** from the Core's `ApprovalDecision` (a human's gate
     resolution, 0044) and `DecisionPlan` (the pipeline's request classification).
   - `AgentArtifact` — an agent's work-product (diff, report, test log, scan); the upstream form the v2
     `deliverables` package later turns into a deliverable.
   - `AgentHandoff` — the **typed form of `StepRequest.prior_results`** (0051); the Foreman composes
     handoffs into an ordered `Plan`.

3. **Agents plug into the engine through the EXISTING `ExecutionPort`.** A dispatched `StepRequest`
   becomes an `AgentRequest`; the `AgentResult` folds back into a `StepResult`. No new engine, lifecycle,
   event bus, or registry. Role routing reuses **`PlanStep.tool`** (0048): the step names the role.

4. **The engine seam carries a summary; the rich layer is lossy at the seam by design.** `AgentResult`'s
   `artifacts`/`findings`/`decision`/`handoff` are **not** forced into `StepResult` (which keeps events
   and records summaries, 0042 §12.2). That collaboration layer flows agent-to-agent under the Foreman
   and into the audit trail.

5. **Consequence, not authority.** An agent never self-authorizes (CLAUDE.md §9). A `BLOCK`/`ESCALATE`
   or any consequential recommendation makes a `PlanStep` **consequential**, which the Mission Engine
   routes to the **human** `ApprovalRequest` gate (0044). The machine verdict proposes; the human gate
   disposes.

6. **Role → agent resolution is a plain map, not a new port.** Resolution is a plain map (`role → Agent`
   here; `capability → Agent` per 0063) invoked by the agent's Tool adapter on the Core's one
   tool-execution path — not a new port. Per the Port-Worthiness rule, no `AgentRegistry` port is
   introduced unless a second independent realization actually appears.

## Consequences

**Positive**
- The architecture is the protocol, not the classes: agents are swappable, independently testable
  realizations; the six messages are the stable contract.
- Everything reuses the frozen Core — lifecycle, gating, resume, events, audit, tenancy come for free;
  the Core is unchanged.
- The finding concept is single-sourced; machine verdicts and the human gate stay cleanly separated.

**Negative / costs**
- The rich collaboration layer is not persisted through the engine seam; preserving artifacts/findings
  across a process boundary (durable agent memory / an artifact store) is a **future concern**, tracked.
- `AgentRequest`/`AgentResult` overlap `StepRequest`/`StepResult` in spirit; the mapping functions are
  the single place that relationship lives, and must stay thin.

## Alternatives considered

- **Agents as plain Tools (only `ToolStepResult`).** Rejected — too thin for collaboration (no findings,
  artifacts, decisions, or handoffs); agents need a richer vocabulary than a leaf tool.
- **A new agent lifecycle / event bus / registry.** Rejected — duplicates the frozen Core and forks the
  audit story; violates ADR 0061 rule 1 and CLAUDE.md §17.
- **Forcing the rich layer through `StepResult`.** Rejected — bloats the engine seam and breaks 0042
  §12.2 (events/records are summaries).
- **Starting from agent classes.** Rejected by the owner — the boundary (messages) is the architecture;
  classes are realizations.
