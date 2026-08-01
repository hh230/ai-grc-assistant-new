-- V3 Serving-Layer schema — migration 0001. Implements SCHEMA-SPEC.md Rev 2.1 (the design).
-- ADR 0058: a SERVING layer (Upsert), NOT the System of Record (that is the append-only
--   Artifact archive + Knowledge Graph). Rows are written only by SupabaseProjection (ADR 0059),
--   applying an immutable ProjectionPackage in ONE transaction (upsert nodes -> upsert edges).
-- Constraint policy (Rev 2.1): NO domain-enumeration CHECKs (which values are valid is contract
--   logic, validated upstream by the Port — a new `type` must never need a migration); KEEP
--   structural-integrity CHECKs (non-empty ids, non-negative counts).
-- Scope: V3 knowledge is GLOBAL, not tenant-scoped -> no tenant_id.

-- ── knowledge_nodes (entities; serving view) ─────────────────────────────────────────
create table if not exists knowledge_nodes (
    entity_id          text primary key,                 -- §2.2 version-pinned id
    source_id          text        not null,
    version            text        not null,
    type               text        not null,             -- canonical §3.5 — no domain CHECK
    native_node_type   text        not null,             -- retained native label (guarantee 7)
    name               text        not null,
    number             text,
    parent             text,                             -- denormalized; hierarchy is in edges
    authority          text        not null,             -- §3.1 — no domain CHECK
    license            text        not null,             -- §3.2 — no domain CHECK
    stability          text        not null,             -- §3.9 — no domain CHECK
    confidence         text        not null,             -- §3.7 — no domain CHECK
    description        text        not null,             -- full text even for Licensed (Storage != Egress)
    from_content_hash  text        not null,             -- provenance
    egress_restricted  boolean     generated always as (license <> 'Public-Domain') stored,
    projection_state   text        not null default 'ACTIVE',  -- ACTIVE | SUPERSEDED | DEPRECATED
    updated_at         timestamptz not null default now(),
    -- structural integrity (data, not domain):
    constraint knowledge_nodes_entity_id_not_empty        check (entity_id <> ''),
    constraint knowledge_nodes_source_id_not_empty        check (source_id <> ''),
    constraint knowledge_nodes_version_not_empty          check (version <> ''),
    constraint knowledge_nodes_type_not_empty             check (type <> ''),
    constraint knowledge_nodes_content_hash_not_empty     check (from_content_hash <> ''),
    constraint knowledge_nodes_projection_state_not_empty check (projection_state <> '')
);
create index if not exists knowledge_nodes_source_idx on knowledge_nodes (source_id, version);
create index if not exists knowledge_nodes_type_idx   on knowledge_nodes (type);
create index if not exists knowledge_nodes_parent_idx on knowledge_nodes (parent);
create index if not exists knowledge_nodes_state_idx  on knowledge_nodes (projection_state);

-- ── knowledge_edges (relationships; serving view) ────────────────────────────────────
create table if not exists knowledge_edges (
    type               text        not null,             -- 'contains' now; Tier-2 semantic later
    source_entity_id   text        not null,
    target_entity_id   text        not null,
    from_content_hash  text        not null,
    updated_at         timestamptz not null default now(),
    primary key (type, source_entity_id, target_entity_id),
    constraint knowledge_edges_type_not_empty   check (type <> ''),
    constraint knowledge_edges_source_not_empty check (source_entity_id <> ''),
    constraint knowledge_edges_target_not_empty check (target_entity_id <> ''),
    -- FK + one-transaction projection ⇒ no dangling edges. DEFERRABLE so node/edge order
    -- inside the txn is flexible; integrity is checked at commit.
    constraint knowledge_edges_source_fk foreign key (source_entity_id)
        references knowledge_nodes (entity_id) deferrable initially deferred,
    constraint knowledge_edges_target_fk foreign key (target_entity_id)
        references knowledge_nodes (entity_id) deferrable initially deferred
);
create index if not exists knowledge_edges_source_idx on knowledge_edges (source_entity_id);
create index if not exists knowledge_edges_target_idx on knowledge_edges (target_entity_id);

-- ── knowledge_projection_log (append-only audit) ─────────────────────────────────────
create table if not exists knowledge_projection_log (
    projection_id      uuid        primary key default gen_random_uuid(),
    status             text        not null,             -- SUCCESS | FAILED | PARTIAL — no domain CHECK
    request_label      text        not null,             -- e.g. ProjectSource(ISO-27001@2022)
    projector_version  text        not null,             -- which GraphProjector projected this (traceable)
    source_id          text,
    version            text,
    content_hash       text,                             -- the artifact projected (source/delta)
    upserted_nodes     int         not null default 0,
    upserted_edges     int         not null default 0,
    deactivated_nodes  int         not null default 0,
    deleted_edges      int         not null default 0,
    error              text,                             -- failure detail when status <> 'SUCCESS'
    projected_at       timestamptz not null default now(),
    constraint knowledge_projection_log_status_not_empty  check (status <> ''),
    constraint knowledge_projection_log_request_not_empty check (request_label <> ''),
    constraint knowledge_projection_log_counts_nonneg check (
        upserted_nodes >= 0 and upserted_edges >= 0
        and deactivated_nodes >= 0 and deleted_edges >= 0
    )
);
create index if not exists knowledge_projection_log_source_idx on knowledge_projection_log (source_id, version);
create index if not exists knowledge_projection_log_time_idx   on knowledge_projection_log (projected_at);
create index if not exists knowledge_projection_log_status_idx on knowledge_projection_log (status);

-- Later, separate migrations (deliberately NOT here):
--   • Embeddings (Stage 7): knowledge_embeddings (entity_id, embedding vector(N)) + pgvector.
--   • RLS: knowledge is global/read-mostly; writes are service-role only. Read policy TBD with owner.
