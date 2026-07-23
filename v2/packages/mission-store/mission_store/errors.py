"""Errors raised by the Mission Store adapter — a small, purpose-built taxonomy so failures are
specific, not generic (CLAUDE.md §22; ADR 0043 §11). The tree:

    MissionStoreError                       — base: a store operation could not complete safely
     ├── SerializationError                 — a payload could not be (de)serialized
     │      └── UnsupportedPayloadSchemaVersion
     └── IdempotencyConflict                — a write collided on (tenant_id, idempotency_key)

`SerializationError` is its own branch because a payload problem is neither a storage/DB failure
nor a domain-rule violation — it is a (de)serialization failure. Future payload errors (e.g.
`CorruptPayload`, `MissingField`, `InvalidPayload`) slot under it. `IdempotencyConflict` is a
direct child of the base: it is a storage-level collision, not a serialization problem.

These are *store* errors, not Mission *domain* errors: payload versions, rows, and unique
constraints are persistence concerns and must not leak into the pure Mission Engine domain, which
keeps its own errors in `mission_engine.errors`.
"""

from __future__ import annotations


class MissionStoreError(RuntimeError):
    """A durable-store operation could not be completed safely. The canonical case is a refused
    cross-tenant overwrite (ADR 0040 §5): a `save` that would move an existing mission to a
    different tenant is rejected, never applied."""


class SerializationError(MissionStoreError):
    """A stored payload could not be turned back into (or serialized out of) a `Mission`
    aggregate. Base for the store's (de)serialization failures — distinct from storage/DB errors
    and from domain errors. Fails loud rather than returning a half-built aggregate."""


class UnsupportedPayloadSchemaVersion(SerializationError):
    """A stored row carries a `payload_schema_version` this build cannot read. Raised on the read
    path only (`codec.mission_from_row`, reached via `get` / `find_by_idempotency_key`), before
    any aggregate is constructed — never on write, which always stamps the current version."""

    def __init__(self, *, mission_id: str, found: int, supported: int) -> None:
        self.mission_id = mission_id
        self.found = found
        self.supported = supported
        super().__init__(
            f"mission {mission_id!r} has payload_schema_version {found}; "
            f"this build reads version {supported} only"
        )


class IdempotencyConflict(MissionStoreError):
    """A `save` collided with an existing mission on `(tenant_id, idempotency_key)`: a *different*
    mission id already holds this tenant's key, blocked by the partial unique index (schema.py).
    The store wraps the raw driver uniqueness violation into this typed error so callers never see
    a database exception for an idempotency collision (ADR 0043 §9, §11). The originating driver
    error is preserved as the exception's `__cause__`."""

    def __init__(self, *, tenant_id: str, idempotency_key: str, mission_id: str) -> None:
        self.tenant_id = tenant_id
        self.idempotency_key = idempotency_key
        self.mission_id = mission_id
        super().__init__(
            f"idempotency key {idempotency_key!r} already exists for tenant {tenant_id!r} "
            f"(attempted by mission {mission_id!r})"
        )
