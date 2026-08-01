# V3 Serving-Layer — Schema Specification (Rev 2.1 — owner-approved, official reference)

> The **design** — the SQL migration, `SupabaseProjection`, and integration tests are generated **from
> this**, never the reverse. ADR 0058: a **Serving layer (Upsert)**, not the System of Record.
> ADR 0059: rows are written only by `SupabaseProjection` applying an immutable `ProjectionPackage`.
>
> **Changes (owner, 2026-07-25):** (1) `active` bool → **`projection_state` enum**; (2) **remove
> domain-enumeration CHECKs (business rules); keep structural-integrity CHECKs (data integrity)** — the
> DB carries no *contract* logic (a new `type` needs no migration) but still guards non-empty ids and
> non-negative counts; (3) **FK on edges + apply in one transaction** (no dangling edges); (4) added
> **`status` + `error`** to the projection log (Fail-Open visibility); (5) added **`projector_version`**
> to the log — the Projection layer is traceable too, alongside source/protocol/contract/extractor
> versions. Approved as-is: SoR≠Serving · derived `egress_restricted` · append-only log · Upsert
> serving · no `tenant_id` · `content_hash`.

## Summary

| Table | Purpose | Primary Key | Write policy |
|---|---|---|---|
| `knowledge_nodes` | serving view of entities | `entity_id` | **Upsert**; withdrawal = state change |
| `knowledge_edges` | serving view of relationships | `(type, source_entity_id, target_entity_id)` | **Upsert** / hard `delete` |
| `knowledge_projection_log` | audit of projection events | `projection_id` (uuid) | **Append-only** |

**Cross-cutting:** knowledge is **GLOBAL, not tenant-scoped** (no `tenant_id`). Idempotency via upsert on
the PKs. **Constraint policy:** **no domain-enumeration CHECKs** — *which values are valid* is contract
logic, validated upstream by the Port (a new `type` must never require a migration); but **keep
structural-integrity CHECKs** — non-empty identity columns, non-negative counts — that is data integrity,
not domain logic. Later, separate migrations: pgvector `knowledge_embeddings` (Stage 7) and RLS.

---

## 1. `knowledge_nodes` — entities (serving view)

| Column | Type | Null | Notes |
|---|---|---|---|
| `entity_id` | text | PK | version-pinned identity (§2.2) |
| `source_id` | text | not null | |
| `version` | text | not null | |
| `type` | text | not null | canonical §3.5 — **no CHECK** (a new type must not need a migration) |
| `native_node_type` | text | not null | retained native label (guarantee 7) |
| `name` | text | not null | |
| `number` | text | null | |
| `parent` | text | null | denormalized; hierarchy is authoritative in `knowledge_edges` |
| `authority` | text | not null | §3.1 — no CHECK |
| `license` | text | not null | §3.2 — no CHECK |
| `stability` | text | not null | §3.9 — no CHECK |
| `confidence` | text | not null | §3.7 — no CHECK |
| `description` | text | not null | full text stored even for Licensed (Storage≠Egress) |
| `from_content_hash` | text | not null | provenance: the artifact that produced this row |
| `egress_restricted` | boolean | generated | `GENERATED ALWAYS AS (license <> 'Public-Domain') STORED` |
| `projection_state` | text | not null, default `'ACTIVE'` | `ACTIVE` \| `SUPERSEDED` \| `DEPRECATED` — serving filters `= 'ACTIVE'` (values owned by the projection code, no DB CHECK) |
| `updated_at` | timestamptz | not null, default now() | |

- **Indexes:** PK(`entity_id`) · (`source_id`,`version`) · (`type`) · (`parent`) · (`projection_state`).
- **Constraints:** NOT NULLs; **structural CHECKs** (`entity_id`, `source_id`, `version`, `type`,
  `from_content_hash` non-empty; `projection_state <> ''`); **no domain-enumeration CHECKs**. No FK on
  `parent` (denormalized).
- **Unique:** `entity_id`.
- **Upsert:** `INSERT … ON CONFLICT (entity_id) DO UPDATE SET <mutable cols>, updated_at = now()`.
- **Withdrawal (no hard delete):** a node's row is **never deleted**; a `deactivate` operation sets
  `projection_state` to `SUPERSEDED` (a newer version replaced it) or `DEPRECATED` (withdrawn) — the *why*
  is preserved, and the row still joins to the projection log + `content_hash`. The SoR retains all
  history regardless.

## 2. `knowledge_edges` — relationships (serving view)

| Column | Type | Null | Notes |
|---|---|---|---|
| `type` | text | not null | `contains` now; Tier-2 semantic later |
| `source_entity_id` | text | not null | **FK → `knowledge_nodes(entity_id)`** |
| `target_entity_id` | text | not null | **FK → `knowledge_nodes(entity_id)`** |
| `from_content_hash` | text | not null | provenance |
| `updated_at` | timestamptz | not null, default now() | |

- **Indexes:** PK(`type`,`source_entity_id`,`target_entity_id`) · (`source_entity_id`) · (`target_entity_id`).
- **Constraints:** NOT NULLs; **structural CHECKs** (`type`, `source_entity_id`, `target_entity_id`
  non-empty). **FK** on both endpoints → `knowledge_nodes(entity_id)` (no cascade — nodes are never
  hard-deleted, so the FK never dangles). **`SupabaseProjection` applies a package in ONE transaction:
  upsert nodes → upsert edges**, so the FK is always satisfiable and **no dangling edge is possible**. *(Future cross-source Tier-2 edges reference a node from another projection; that node must
  already be present — handled when Tier-2 ships, e.g. project the referenced source first.)*
- **Unique:** the composite PK.
- **Upsert:** `INSERT … ON CONFLICT (type, source_entity_id, target_entity_id) DO UPDATE SET
  from_content_hash = excluded.from_content_hash, updated_at = now()`.
- **Removal:** hard `DELETE` via `delete_edge` (edges are structural, cheap, re-derivable).

*(Note: the FK + transaction is the `SupabaseProjection` realization's mechanism; the abstract
`ProjectionPackage` and `MemoryProjectionTarget` remain store-agnostic.)*

## 3. `knowledge_projection_log` — projection audit (append-only)

| Column | Type | Null | Notes |
|---|---|---|---|
| `projection_id` | uuid | PK, default gen_random_uuid() | one row per projection event |
| `status` | text | not null | **`SUCCESS` \| `FAILED` \| `PARTIAL`** — Fail-Open is part of the system; state it, don't infer it |
| `request_label` | text | not null | e.g. `ProjectSource(ISO-27001@2022)` |
| `projector_version` | text | not null | which `GraphProjector` version projected this — traceability, like source/protocol/contract/extractor versions |
| `source_id` | text | null | null for a snapshot |
| `version` | text | null | |
| `content_hash` | text | null | the artifact projected (for source/delta) |
| `upserted_nodes` | int | not null, default 0 | |
| `upserted_edges` | int | not null, default 0 | |
| `deactivated_nodes` | int | not null, default 0 | |
| `deleted_edges` | int | not null, default 0 | |
| `error` | text | null | failure detail when `status <> 'SUCCESS'` |
| `projected_at` | timestamptz | not null, default now() | |

- **Indexes:** PK(`projection_id`) · (`source_id`,`version`) · (`projected_at`) · (`status`).
- **Constraints:** NOT NULLs on `status`/`projector_version`/counts; **structural CHECKs** (counts
  `>= 0`; `status`, `request_label` non-empty). No domain-enumeration CHECK on `status`.
- **Unique:** none beyond the PK — every projection event appends a row.
- **Write policy:** **Append-only** (INSERT per event; never UPDATE/DELETE). Source of the last
  successfully-projected `content_hash` per source (drives `ProjectDelta`, filtering `status='SUCCESS'`).
- **Removal:** never — the audit trail is retained.
