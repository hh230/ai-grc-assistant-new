# ADR 0060: The Embedding boundary — one EmbeddingPort, many provider realizations

- Status: **Accepted** (2026-07-25; final refinements 2026-07-26) — ratified by the Product Owner with
  seven refinements folded in: (1) state-port split, (2) rich input, (3) format version, (4) Embedding ≠
  Egress, (5) **`embedding_profile` as the identity axis** (not `model`, not `content_hash`),
  (6) **`EmbeddingProfile` + registry** — the identity is a first-class, resolvable entity, not a bare
  string, and (7) **total Provider ⟂ Store separation** via an immutable `EmbeddingBatch` (the store
  never sees the provider; the provider never sees the store — as GraphProjector ⟂ ProjectionTarget).
  **With (6) and (7), the Product Owner declared the V3 architectural language complete — no further ADRs;
  the rest is Platform Engineering.** Boundary-first, like the Extraction Port (0056) and Graph Projection
  Port (0059). Proven by the `DeterministicEmbeddingProvider` + `MemoryEmbeddingStore` reference
  realizations before any real provider.
- Date: 2026-07-25
- Deciders: **Product Owner**, Architecture
- Related: ADR 0056 (one Port / many realizations) · ADR 0058 (Fail-Open · Incremental · Independent &
  Idempotent; System of Record = Append-only, Serving = Upsert) · ADR 0059 (Request → target-agnostic
  transform → immutable package → realization) · CANONICAL-MODEL §12 (embeddings for **entities**, not
  documents/chunks) · §10.6 & Storage ≠ Egress (extended here to **Embedding ≠ Egress**).

## Context

The Knowledge Graph (System of Record) holds 387 entities (live in Supabase). To enable AI / vector
search, each **entity** needs an embedding vector. V3's unit is the **Knowledge Entity — never a
document or a chunk**. Vectors come from an external **provider** (OpenAI, Gemini, Voyage, Jina, …), but
the system must never be coupled to one: swapping providers must be a *realization*, not an architecture
change. Per ADR 0058 the stage must be **Incremental** (embed only the delta), **Idempotent** (never
re-embed the same content), **Fail-Open** (a provider failure never halts the pipeline), **Independent**
(runs standalone), and must leave the **System of Record append-only** — embeddings are a *serving*
artifact. And embeddings are not one-representation-forever: search, classification, RAG, and re-ranking
each want a different text recipe — so the design must let multiple representations coexist.

## Decision

**One provider-agnostic `EmbeddingPort`; every provider is a Realization behind it. Around it, four small
single-responsibility collaborators — a Formatter (what text represents an entity), a Planner (which
entities still need embedding), a State Port (what is already embedded), and a Store (serving) — each
ignorant of the others' concerns. The identity of an embedding is its `embedding_profile`.** The unit is
always the **entity**.

### The pipeline (each arrow is a boundary)

```
EmbeddingProfileRegistry.resolve(profile_id)
        │  → EmbeddingProfile { profile_id · purpose · formatter · provider · model · dimensions · distance_metric }
        ▼
EmbeddingRequest + KnowledgeGraph
        │
        ▼
   profile.formatter        ← owns the text composition + embedding_format_version; stamps profile_id
        ▼                      (changing wording lives HERE, not in the Planner)
   EmbeddingInput[]          entity_id · … · text · text_hash · egress_restricted
        │                    · embedding_profile · embedding_format_version
        ▼
   EmbeddingPlanner  ──────▶ EmbeddingStatePort   (has_embedding / list_embeddings — the ONLY
        │                                           window into "what's already embedded")
        ▼
   EmbeddingWorkSet          the DELTA only — inputs where has_embedding(...) is False
        │
        ▼
   profile.provider.embed(workset) → EmbeddingVector[]     ← ONE operation; knows no STORE
        ├ DeterministicEmbeddingProvider  (Reference — in-memory, no provider/network/key)
        └ OpenAI / Gemini / Voyage / Jina  (later realizations)
        │
        ▼
   EmbeddingBatch           immutable hand-off: vectors + run identity   ← like ProjectionPackage (0059)
        │
        ▼
   EmbeddingStore.apply(batch) → EmbeddingResult          ← knows no PROVIDER; Upsert by
                              (entity_id, embedding_profile) + append-only run log
```

### 1. `EmbeddingPort` — the provider boundary (one operation only)

```
class EmbeddingPort(ABC):
    model: str          # identity of THIS provider+model, e.g. "text-embedding-3-small"
    dimensions: int     # vector length this model emits
    def embed(self, inputs: Sequence[EmbeddingInput]) -> Sequence[EmbeddingVector]: ...
```

`texts → vectors`, nothing more. The Port knows **nothing** of OpenAI / Gemini / Voyage / Jina / HTTP /
keys — *how* a vector is produced is the Realization's private concern (as `fitz` lives in an extractor,
never in the Extraction Port). `model` + `dimensions` **travel with every vector** as attributes.
Because `EmbeddingInput` is **rich** (§3), a provider may pick a different prompt for a `Control` than
for a `Definition` — without breaking the contract later.

### 2. `EmbeddingFormatter` — a component, not the Planner (Owner refinement 2)

Turning an entity into embed-text is a **separate responsibility** from planning: *changing the wording
is not a change in planning.* The Formatter maps one entity → one `EmbeddingInput`, grounded in the
entity's **real** fields (`native_node_type`, `number`, `name`, `description`, `type`) — e.g.
`"Control A.5.7: Threat intelligence …"`. It **owns `embedding_format_version`** and stamps the run's
`embedding_profile` onto each input.

### 3. `EmbeddingInput` — rich, provider-friendly (Owner refinement 2)

`entity_id` · `entity_type` · `source` · `version` · `text` · `text_hash` · `egress_restricted` ·
`embedding_profile` · `embedding_format_version`. Enough for any provider to specialize its prompt, and
enough to key, audit, and egress-govern the result — without ever re-reading the graph.

### 4. `EmbeddingStatePort` — the Planner's only window (Owner refinement 1)

```
class EmbeddingStatePort(ABC):
    def has_embedding(self, entity_id: str, text_hash: str, embedding_profile: str) -> bool: ...
    def list_embeddings(self, *, source_id=None, embedding_profile=None) -> Sequence[EmbeddingKey]: ...
```

The **Planner never touches pgvector**. It asks the State Port. Swap pgvector → Pinecone / Qdrant /
Weaviate and **not one line of the Planner changes** — the new store simply realizes this port.

### 5. `EmbeddingPlanner` — pure delta (no store, no format)

`EmbeddingInput[] + EmbeddingStatePort → EmbeddingWorkSet`. The delta = inputs where
`has_embedding(entity_id, text_hash, embedding_profile)` is **False**. The identity travels IN each
input, so the Planner needs no extra parameter. That's all it does.

### 5b. Provider ⟂ Store — the immutable `EmbeddingBatch` (Owner refinement 7)

The **provider never sees the store, and the store never sees the provider** — the same total separation
as GraphProjector ⟂ ProjectionTarget (0059). The provider's output flows into an **immutable
`EmbeddingBatch`** (vectors + run identity: `embedding_profile`, `model`, `embedding_format_version`,
`request_label`, `skipped`, `failed`, `status`), and the store's single write op is
`apply(batch) → EmbeddingResult`:

```
class EmbeddingStore(EmbeddingStatePort, ABC):
    def apply(self, batch: EmbeddingBatch) -> EmbeddingResult: ...   # Upsert vectors + append run log
```

`apply` reads the batch, upserts its vectors by `(entity_id, embedding_profile)`, and appends one
append-only run row — knowing **nothing** of how the vectors were made. Swap pgvector → Pinecone /
Qdrant / Weaviate: only the `apply` realization changes. (The batch is the embedding stage's
`ProjectionPackage`.)

### 6. Identity axis = `embedding_profile`; dedup key = `(entity_id, text_hash, embedding_profile)` (Owner ratified)

`content_hash` identifies a whole **Artifact** (all 156 PDPL entities share one) — it cannot key a single
entity. And `model` alone is too weak an identity: search, classification, and RAG can share a model yet
need different vectors. The ratified identity axis is **`embedding_profile`** — a **named, versioned
recipe** that bundles {purpose · text composition · model · params}, e.g. `semantic-v1`, `rag-v1`,
`classification-v1`, `search-v2`. `model` and `embedding_format_version` are **recorded attributes** under
the profile, not identity.

- **Dedup key = `(entity_id, text_hash, embedding_profile)`.** Same entity + same text + same profile ⇒
  already present ⇒ **skipped**. A changed text (new `text_hash`) or a different profile ⇒ a genuine delta.
- **Serving store upsert key = `(entity_id, embedding_profile)`** — one *current* vector per entity per
  profile; `has_embedding` returns True only when the stored row's `text_hash` still matches, so a wording
  change overwrites within the profile and a re-run is a no-op.

**Coexistence ≠ append-only history (the key clarification).** Distinct profiles **coexist** for the same
entity (`semantic-v1` *and* `rag-v1` both present) — this is *serving multiplicity* (comparison, rollback,
multi-purpose), **not** kept history: within a profile it is still **Upsert** (Serving = Upsert, ADR 0058),
one current vector. When a profile is fully retired it is deleted (a serving decision). The append-only
*history of embedding events* lives in the run log, never in the vector table — so we honour ADR 0058
(no per-vector append bloat) while making the recipe part of identity. Bumping a recipe = a **new profile
version** (`semantic-v1 → semantic-v2`), which coexists with the old until migration completes.

### 6b. `EmbeddingProfile` + registry — identity as a first-class entity (Owner refinement 6)

`embedding_profile` is **not a bare string** scattered through the system. It is a resolvable entity, like
the Extractor/Tool registries:

```
@dataclass(frozen=True)
class EmbeddingProfile:
    profile_id · purpose · formatter · provider · model · dimensions · distance_metric

class EmbeddingProfileRegistry:      # profile_id -> EmbeddingProfile
    register(profile)  # validates model/dimensions against the provider — fail loud, not silent
    resolve(profile_id) -> EmbeddingProfile
    ids() -> frozenset[str]
```

A profile bundles the text recipe (`formatter`) with the vector producer (`provider`) and the metadata a
serving store needs (`model`, `dimensions`, `distance_metric` — the last for the ANN index, deferred).
The orchestration is handed a **resolved `EmbeddingProfile`**, not a string — so `semantic-v1`,
`semantic-v2`, `semantic-ar`, `semantic-multilingual`, `rag-v1`, `rerank-v1` are managed in one place, and
adding one is a registration, never a scattered literal. Registration **validates** the profile against
its provider (declared `model`/`dimensions` must match), so a mis-wired profile fails loud.

### 7. `embedding_format_version` — provenance, like `projector_version` (Owner refinement 3)

Owned by the Formatter; carried on every `EmbeddingInput`, `EmbeddingVector`, and run-log row as an
**attribute** under the profile. It tells us **which text format** built a vector without reverse-
engineering from `text_hash`. (It is *not* the identity — the profile is — but it is recorded for audit
and for a deliberate "re-embed" migration.)

### 8. **Embedding ≠ Egress** — a named architectural rule (Owner refinement 4)

Extends *Storage ≠ Egress*:
- Any content **may be embedded and stored** — including Licensed (ISO) content.
- The serving vector store **persists no raw text** — only the vector + keys + `egress_restricted`.
- **Vector search returns entities only** (`entity_id` + score), never text.
- Retrieving the text goes through `knowledge_nodes`, governed by the Egress Policy; **the AI layer
  decides whether an `egress_restricted=true` text may be shown.**

So a vector search can never leak Licensed text by construction — the vectors are numeric, textless, and
carry the egress marker for downstream filtering.

### 9. Fail-Open (ADR 0058)

A provider error on a batch marks those entities **FAILED** (recorded in the run log) and the pipeline
**continues**; failed entities are never written to the store, so they reappear in the next run's delta
(self-healing). No single provider hiccup halts embedding.

### 10. Multi-provider without the system knowing any provider

A profile pins a provider; selecting one = resolving an `EmbeddingProfile` from the registry (§6b) —
selection is *data* (§17). The core passes `EmbeddingInput`s and receives `EmbeddingVector`s; `model` +
`dimensions` ride along so models coexist. Nothing in the core imports a provider SDK. The registry (§6b)
is the home for the `profile_id → {formatter, provider, model, dimensions, distance_metric}` wiring.

## Consequences

**Positive**
- Providers **and** stores are swappable: a new provider = a new `EmbeddingPort`; a new vector DB = a new
  `EmbeddingStatePort`/store. The Planner and Formatter never change.
- Incremental + idempotent fall out of `(entity_id, text_hash, embedding_profile)`; a re-run is a no-op.
- **Multiple representations coexist** (search / RAG / classification) as distinct profiles — added later
  with **zero PK migration** on millions of vectors, because the identity is already `embedding_profile`.
- Entity-level embeddings with full provenance (`source`, `version`, `entity_type`, `model`,
  `embedding_format_version`) — not opaque chunks.
- **Embedding ≠ Egress** makes Licensed-text leakage impossible by construction.
- Fail-Open + self-healing delta: a provider outage costs only a retry next run.

**Negative / costs**
- Several small collaborators instead of one blob — but each is tiny and single-purpose (the 0058/0059
  shape), and the registry + immutable batch make the seams explicit rather than implicit.
- The Formatter's composition must be **stable** within a profile; a new recipe is a new profile version.
- A profile bundles a formatter + provider + declared model/dimensions; the registry **validates** that
  binding at registration (fail loud), so the composition root cannot wire an inconsistent profile.

## Alternatives considered

- **Dedup / PK on `model` alone.** Rejected (Owner ratified) — too weak; search vs RAG share a model but
  need different vectors, and bumping the format silently overwrites the only copy.
- **Dedup on `content_hash`.** Rejected — that's per-Artifact, not per-entity.
- **Surrogate `embedding_id`, full per-vector append.** Rejected — contradicts ADR 0058 (Serving = Upsert)
  and bloats to millions of stale vectors; serving still needs a latest-per-(entity, profile) index, so
  the identity question is deferred, not removed. The append-only *event* history is the run log's job.
- **Planner reads the vector store directly / `EmbeddingInput` text-only / formatting inside the Planner /
  embed documents-or-chunks / couple to one provider / re-embed everything each run.** All rejected — see
  §1–§5.

## Reference Realization (proves the Port before any real provider)

- `DeterministicEmbeddingProvider` (`EmbeddingPort`): `vector = normalize(seeded_prng(text_hash))` at a
  fixed `dimensions`, `model = "deterministic-v1"`.
- `MemoryEmbeddingStore` (`EmbeddingStatePort` + store): an in-memory dict keyed
  `(entity_id, embedding_profile)` + an in-memory append-only run log — the `MemoryProjectionTarget` analog.

Together, driven through the `EmbeddingProfileRegistry` and the `EmbeddingBatch → store.apply` hand-off,
they prove — with **no provider, no network, no key** — the Port contract, the registry (resolve +
validate), the Formatter → Planner → Provider → Batch → Store chain with **Provider ⟂ Store** separation,
the `(entity_id, text_hash, embedding_profile)` delta/dedup, distinct profiles coexisting for one entity,
idempotent re-runs, Fail-Open, `embedding_format_version` provenance, and Embedding ≠ Egress (textless
vectors). Only then do we build the first real provider realization + the pgvector store.
