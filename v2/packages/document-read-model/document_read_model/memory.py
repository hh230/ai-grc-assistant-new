"""`InMemoryDocumentReadModel` — the driver-free adapter (V1 Execution Slice S4).

It backs unit tests and local runs with no database, and defines the read model's semantics the
Postgres adapter must match: tenant-scoped fail-closed reads, newest-first ordering, an optional
exact filter by `evidence_kind`, collection grouping in the product's display order, and idempotent
upsert by `document_id`. It is a projection: `record` upserts (a re-record — e.g. `ingesting →
ready` — replaces the row rather than adding one).
"""

from __future__ import annotations

from pipeline_contracts import TenantContext

from document_read_model.kinds import kind_sort_key
from document_read_model.models import DocumentItem, EvidenceCollection


class InMemoryDocumentReadModel:
    """A dict-backed projection keyed by `document_id`. Reads filter strictly by the caller's
    tenant, so cross-tenant leakage is impossible regardless of what was recorded."""

    def __init__(self) -> None:
        self._by_id: dict[str, DocumentItem] = {}

    def record(self, item: DocumentItem) -> None:
        """Upsert by `document_id`. Idempotent: recording the same id again overwrites the previous
        projection (the document's latest snapshot — e.g. its new status — wins)."""
        self._by_id[item.document_id] = item

    def get(self, document_id: str, tenant: TenantContext) -> DocumentItem | None:
        item = self._by_id.get(document_id)
        # Fail-closed: a row owned by another tenant is not found.
        if item is None or item.tenant_id != tenant.tenant_id:
            return None
        return item

    def _tenant_rows(self, tenant: TenantContext) -> list[DocumentItem]:
        # Fail-closed: start from *this tenant's* rows only. No later step can widen the scope.
        return [item for item in self._by_id.values() if item.tenant_id == tenant.tenant_id]

    def list_documents(
        self,
        tenant: TenantContext,
        *,
        evidence_kind: str | None = None,
    ) -> tuple[DocumentItem, ...]:
        rows = self._tenant_rows(tenant)
        if evidence_kind:
            rows = [item for item in rows if item.evidence_kind == evidence_kind]
        # Newest first; ties broken deterministically so ordering is stable across calls.
        rows.sort(key=lambda item: (item.uploaded_at, item.document_id), reverse=True)
        return tuple(rows)

    def list_collections(self, tenant: TenantContext) -> tuple[EvidenceCollection, ...]:
        counts: dict[str, int] = {}
        for item in self._tenant_rows(tenant):
            counts[item.evidence_kind] = counts.get(item.evidence_kind, 0) + 1
        # Product display order: known kinds first (KIND_ORDER), unknown kinds after.
        kinds = sorted(counts, key=kind_sort_key)
        return tuple(EvidenceCollection(evidence_kind=kind, count=counts[kind]) for kind in kinds)
