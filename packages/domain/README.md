# grc-domain

The **pure Domain Layer** (DDD bounded contexts) of the AI GRC Assistant.

This package contains business rules only — entities, value objects, aggregates, domain
events, domain services, repository *interfaces*, domain exceptions, and enums. It has
**zero** dependency on FastAPI, SQLAlchemy, LLM SDKs, databases, or any framework
(standard library only). See [`CLAUDE.md` §15](../../CLAUDE.md) and
[`docs/adr/0011-ddd-boundaries.md`](../../docs/adr/0011-ddd-boundaries.md).

## Contexts

`tenancy` · `workspace` · `frameworks` · `controls` · `policies` · `risks` ·
`assessments` · `evidence` · `knowledge` · `reporting` · `platform` (Tool/Agent/Plugin) ·
`missions` · `audit`, over a `shared` kernel.

## What is intentionally NOT here

No persistence, no ORM, no API, no AI/LLM calls, no database. Those layers depend inward on
this one. Repository classes here are abstract interfaces only; implementations live in the
infrastructure layer.
