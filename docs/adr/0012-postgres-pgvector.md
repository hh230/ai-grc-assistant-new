# ADR 0012: PostgreSQL + pgvector as the primary data store

- Status: Accepted — **access-mechanism clause amended in scope for V2 by [ADR 0045](./0045-v2-persistence-mechanism.md)**
- Date: 2026-06-26
- Deciders: Architecture team
- Related: CLAUDE.md §4, §12, §20; ADR 0008; **ADR 0045 (V2 persistence mechanism — reconciliation)**

> **Scope note (added 2026-07-17):** the store choice below (PostgreSQL + pgvector) stands unchanged.
> The **access-mechanism** sentence in *Decision* (async SQLAlchemy + Alembic + "no raw SQL") is
> **V1-scoped**; **V2** uses synchronous psycopg3 + raw *parameterized* SQL behind Ports & Adapters
> with ordered `.sql` migrations — see [ADR 0045](./0045-v2-persistence-mechanism.md). This ADR's
> Decision text is left immutable, per the ADR process; ADR 0045 carries the V2 reconciliation.

## Context

We need a single, reliable source of truth for relational GRC data (controls, policies,
risks, evidence, missions, tenancy) with strong consistency, transactions, and migrations,
plus vector similarity search for RAG. Operating two separate systems (an RDBMS and a
standalone vector DB) adds operational burden and makes it harder to keep retrieval
tenant-isolated and consistent with relational metadata.

## Decision

We use **PostgreSQL** as the primary relational database and **pgvector** for embeddings,
co-located in the same database. This enables **hybrid retrieval** (vector + keyword +
metadata filters) with `tenant_id` filtering enforced alongside relational constraints.
Access is via **SQLAlchemy (async)** with **Alembic** migrations (mandatory, reviewed,
reversible where possible); no raw SQL string interpolation; repositories isolate data
access. The embedding/vector-store layer remains behind an interface, so a managed vector
DB can be adopted later without touching business code (per ADR 0008).

## Consequences

**Positive**
- One system to operate, back up, and secure; transactions span relational + vector data.
- Tenant isolation and metadata filtering live next to the vectors, simplifying RAG.
- Mature ecosystem, strong consistency, and migration tooling.

**Negative / costs**
- pgvector at very large scale may need tuning (indexes, partitioning) or eventual move to
  a dedicated vector store — mitigated by the interface boundary.
- Mixed OLTP + vector workloads require capacity planning.

## Alternatives considered

- **Separate dedicated vector DB from day one.** Rejected initially: extra ops surface and
  cross-store consistency cost; kept as a future option behind the interface.
- **NoSQL primary store.** Rejected: GRC needs strong relational consistency, constraints,
  and transactions.
