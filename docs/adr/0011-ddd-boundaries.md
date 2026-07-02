# ADR 0011: Domain-Driven Design boundaries

- Status: Accepted
- Date: 2026-06-26
- Deciders: Architecture team
- Related: CLAUDE.md §14, §15; ADR 0006

## Context

GRC has rich, long-lived business rules that must survive a decade of framework churn,
model swaps, and infrastructure changes. If business rules leak into FastAPI handlers,
SQLAlchemy models, or prompts, they become untestable, duplicated, and coupled to
replaceable technology.

## Decision

We model the system with **Domain-Driven Design**. The domain is split into **bounded
contexts** — Controls, Policies, Risks, Evidence, Frameworks, Missions, Tenancy/Identity,
Reporting — each with its own model and ubiquitous language (the Glossary is the shared
dictionary). Each context defines **aggregates** that enforce their own invariants via the
aggregate root. The **Domain layer is pure**: no dependency on FastAPI, SQLAlchemy, LLM
SDKs, or any framework, and is independently testable.

A **Services Layer** sits between Tools and the Domain, coordinating domain objects,
transactions, and infrastructure; data access uses the **repository pattern** (no ORM
queries leak into Tools, handlers, or domain logic). External inputs (LLM output, connector
data, framework imports) cross **anti-corruption layers** that translate them into clean
domain models. Relationships between contexts are explicit, via Services and events.

## Consequences

**Positive**
- Business rules are centralized, testable, and insulated from technology churn.
- Clear ownership and language per context; safer evolution over 10+ years.

**Negative / costs**
- More layers and mapping (DTO ↔ domain) than a CRUD-on-ORM approach.
- Requires team discipline to keep the domain pure.

## Alternatives considered

- **Anemic models / logic in services and handlers.** Rejected: rules scatter, invariants
  erode, testing suffers.
- **ORM entities as the domain model.** Rejected: couples business rules to persistence and
  framework.
