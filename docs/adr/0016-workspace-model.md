# ADR 0016: Workspace model (Workspace-first UX)

- Status: Accepted
- Date: 2026-06-26
- Deciders: Architecture team, Product
- Related: CLAUDE.md §18; ADR 0003, 0013, 0015

## Context

A chat window is a poor home for durable, auditable GRC work: objects scroll away, plans
and approvals are invisible, and provenance is hard to surface. Users (compliance officers,
risk managers, auditors) need to browse, filter, and act on controls, risks, policies,
evidence, reports, and missions as first-class objects — and to steer long-running work.

## Decision

The product is **Workspace-first, not chat-first.** Users live in a structured
**workspace** where missions, controls, policies, risks, evidence, and reports are durable,
navigable, linkable objects. Conversation is one tool inside the workspace, not the whole
product. Missions are visible and steerable (goal, plan, progress, approval gates,
citations, outputs, with intervention at any step); human gates are ergonomic, in-context
interactions surfaced with their evidence; long missions stream progress; and every AI
output shows its sources, confidence, and decision trail directly where it is reviewed
(per ADR 0015). New workspaces are added as frontend feature modules that are **views onto
existing Tools/Missions**, not new business logic.

## Consequences

**Positive**
- Durable, auditable, object-centric UX fit for regulated GRC work.
- Human gates and explainability are part of the everyday interaction surface.
- New workspaces compose existing Tools/Missions without new backend logic.

**Negative / costs**
- More UX surface to design and maintain than a single chat view.
- Requires consistent object models and contracts across many workspace areas.

## Alternatives considered

- **Chat-first assistant.** Rejected: ephemeral, weak provenance, unsafe for consequential
  actions (see ADR 0003).
- **Static dashboards only.** Rejected: not steerable; cannot drive governed missions or
  approvals.
