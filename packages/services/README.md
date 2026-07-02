# grc-services

The **Application Layer** (Clean Architecture) of the AI GRC Assistant.

Orchestrates use cases over the pure Domain Layer (`grc-domain`). Depends **only** on the
domain — no FastAPI, SQLAlchemy, database, AI/LLM, or other infrastructure. See
[`CLAUDE.md` §14](../../CLAUDE.md) and the ADRs.

## Contents

- **Commands / Queries** (CQRS messages) and their **Handlers** (use cases).
- **DTOs** — plain, boundary-friendly read models.
- **Application Services** — one facade per capability.
- **Ports & abstractions** (`shared/`): `UnitOfWork` (transaction boundary),
  `AuthorizationService`, `EventDispatcher`, `Validator`, `Clock`/`IdGenerator`,
  `CommandBus`/`QueryBus`, `Result` types, application exceptions, and the
  `TransactionalCommandHandler` pattern (transaction + event dispatch).

## Capabilities

`missions` · `workspaces` · `policies` · `risks` · `assessments` · `evidence` ·
`frameworks` · `knowledge` · `controls` · `reporting` · `tools` · `agents` · `plugins` ·
`audit`.

> Repository, UoW, authorization, and event-dispatch *implementations* live in the
> infrastructure layer and are injected into the application services at the composition
> root.
