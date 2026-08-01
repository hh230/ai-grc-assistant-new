# ADR 0053: Read Models & Application-layer Projection (the V2 CQRS read side)

- Status: **Accepted** (2026-07-22)
- Date: 2026-07-22
- Deciders: Product Owner (this coupling decision reserved to the owner), Architecture
- Related: `CONCEPTUAL_DOMAIN_MODEL_V1.md` §3 (the read-model gaps this generalises), ADR 0046
  (the product Application layer that owns projection), ADR 0042/0043 (the frozen Core — Mission
  aggregate, Mission Store, the Transactional Outbox this makes event-driven-ready), ADR 0052
  (`v2/apps/grc-api` reads the read models), `mission-read-model` + `mission-projection` (the first
  instance), `V1_EXECUTION_PLAN.md` (S1).

---

## Context

Slice S1 (Mission List) needed a *list a tenant's missions* read, which the frozen Core does not
offer, and it needed two fields the Core does not persist — the product **Mission Type** and the
**scope** (the aggregate stores a free-text `goal`). S1 answered both with a **read model**
(`mission-read-model`) fed by a small **projector** (`mission-projection`).

The owner flagged the real question before this becomes an undocumented habit: **is projection a
one-off adapter, or a V2 architecture pattern?** It is a pattern: `CONCEPTUAL_DOMAIN_MODEL_V1.md` §3
already names three more read models to come — **Approvals Queue**, **Deliverables Index**, and the
**Dashboard**. A mechanism reused across four views is architecture, not a slice detail — so it is
decided here, once.

A hard constraint shapes the decision: **Core domain events carry `id`/`tenant`/`status`, not
`type`/`scope`.** Only the product Application layer knows those two, and only at creation. So a
pure event subscriber cannot build a row on its own — the product must stamp type/scope regardless.

## Decision

**Read models are the CQRS read side; projection into them is an Application-layer, synchronous
concern in V1.**

1. **Read models** are tenant-scoped, fail-closed projections that answer list/query views. They are
   the read side only — they never write the domain. (`MissionListReadModel` is the first; Approvals,
   Deliverables, Dashboard follow the same port shape.)
2. **The projector is an Application-layer adapter**, not Core and not infrastructure. The product
   **Application Service** that owns the mission's create/drive transaction (the ADR 0046 product
   layer — e.g. `AssistantRuntime` / the integration composition root) calls
   `projector.project(mission, type, scope)` **after persisting** the mission. The coupling is
   explicit and points outward from the Application layer to a read-model *port*.
3. **Synchronous in V1**, matching the owner-locked "V1 is synchronous; no async infra before need."
4. **Event-driven-ready, not event-driven yet.** The Core's Transactional Outbox + Event Bus already
   exist. Moving *status* updates to an event subscriber later is possible **without changing the
   caller** — but the create-time stamping of type/scope stays an Application-layer act either way.

**Rejected:** a *Repository Decorator* on the store (hidden coupling; the store layer does not know
type/scope) and a *pure domain-event subscriber now* (cannot supply type/scope; pulls async forward
against the synchronous-V1 decision).

## Consequences

- **Positive.** One documented pattern for all four V1 read models; explicit, testable coupling in
  the Application layer; the frozen Core is untouched (it neither knows nor calls the read model);
  the outbox keeps the async evolution open at zero caller cost.
- **Follow-ups.** Wiring the projector into the product Application Service lands with the **create**
  flow (Slice S7, New Mission) — S1 is the read side, so it is exercised by seeding until then.
  Each new read model (Approvals, Deliverables, Dashboard) is an instance of this ADR, not a new
  decision.
- **Freeze.** No Foundational Document is contradicted — this formalises the §3 read-model gap and
  names the mechanism. It is an additive ADR (like 0052), not a Core change.
