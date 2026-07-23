"""S4 acceptance for the Document read model, verified on the in-memory adapter (no Postgres).

These map to the Execution Contract's Given/When/Then: a Practitioner sees their tenant's evidence
grouped into **Evidence Collections** (by `evidence_kind`) with counts, in the product's display
order; can open a collection to see the documents inside it, newest-first; sees ingestion status;
and NEVER sees another tenant's documents or collections (fail-closed). Ordering, collection
grouping, and upsert idempotency are pinned so the Postgres adapter has an exact spec to match.
"""

from __future__ import annotations

from document_read_model import (
    DocumentItem,
    DocumentStatus,
    EvidenceKind,
    InMemoryDocumentReadModel,
)
from pipeline_contracts import TenantContext


def tenant(tenant_id: str) -> TenantContext:
    return TenantContext(
        tenant_id=tenant_id, principal_id="user-1", roles=("practitioner",), region="ksa"
    )


def doc(
    document_id: str,
    tenant_id: str,
    *,
    filename: str = "policy.pdf",
    evidence_kind: str = EvidenceKind.POLICY.value,
    status: str = DocumentStatus.READY.value,
    uploaded_at: float = 100.0,
    size: int = 2048,
) -> DocumentItem:
    return DocumentItem(
        document_id=document_id,
        tenant_id=tenant_id,
        filename=filename,
        evidence_kind=evidence_kind,
        status=status,
        uploaded_at=uploaded_at,
        size=size,
    )


def seed_two_tenants() -> InMemoryDocumentReadModel:
    rm = InMemoryDocumentReadModel()
    # tenant T: 5 documents across three kinds, distinct uploaded_at so ordering is unambiguous
    rm.record(doc("d1", "T", evidence_kind="policy", uploaded_at=500.0, filename="aup.pdf"))
    rm.record(doc("d2", "T", evidence_kind="policy", uploaded_at=400.0, filename="access.pdf"))
    rm.record(doc("d3", "T", evidence_kind="procedure", uploaded_at=300.0))
    rm.record(doc("d4", "T", evidence_kind="soc_report", uploaded_at=200.0))
    rm.record(doc("d5", "T", evidence_kind="procedure", uploaded_at=100.0))
    # tenant T2: 2 documents the caller from T must never see or count
    rm.record(doc("x1", "T2", evidence_kind="policy"))
    rm.record(doc("x2", "T2", evidence_kind="standard"))
    return rm


# --- fail-closed tenant isolation -------------------------------------------------------


def test_lists_only_the_callers_tenant() -> None:
    rm = seed_two_tenants()
    ids = {d.document_id for d in rm.list_documents(tenant("T"))}
    assert ids == {"d1", "d2", "d3", "d4", "d5"}


def test_never_returns_another_tenants_documents() -> None:
    rm = seed_two_tenants()
    for d in rm.list_documents(tenant("T")):
        assert d.tenant_id == "T"
    ids_t2 = {d.document_id for d in rm.list_documents(tenant("T2"))}
    assert ids_t2 == {"x1", "x2"}


def test_unknown_tenant_sees_empty() -> None:
    rm = seed_two_tenants()
    assert rm.list_documents(tenant("nope")) == ()
    assert rm.list_collections(tenant("nope")) == ()


def test_collections_never_count_another_tenant() -> None:
    rm = seed_two_tenants()
    # T2 has one policy + one standard; T's policy count (2) must not bleed in.
    collections = {c.evidence_kind: c.count for c in rm.list_collections(tenant("T2"))}
    assert collections == {"policy": 1, "standard": 1}


# --- ordering ---------------------------------------------------------------------------


def test_orders_newest_uploaded_first() -> None:
    rm = seed_two_tenants()
    order = [d.document_id for d in rm.list_documents(tenant("T"))]
    assert order == ["d1", "d2", "d3", "d4", "d5"]


# --- Evidence Collections (the unit) ----------------------------------------------------


def test_collections_group_by_kind_with_counts() -> None:
    rm = seed_two_tenants()
    collections = {c.evidence_kind: c.count for c in rm.list_collections(tenant("T"))}
    assert collections == {"policy": 2, "procedure": 2, "soc_report": 1}


def test_collections_are_in_product_display_order() -> None:
    rm = seed_two_tenants()
    # KIND_ORDER: policy, procedure, standard, soc_report, risk_register, other.
    # T has policy, procedure, soc_report → they must appear in exactly that order.
    order = [c.evidence_kind for c in rm.list_collections(tenant("T"))]
    assert order == ["policy", "procedure", "soc_report"]


def test_unknown_kind_is_kept_and_sorts_last() -> None:
    rm = InMemoryDocumentReadModel()
    rm.record(doc("d1", "T", evidence_kind="policy"))
    rm.record(doc("d2", "T", evidence_kind="mystery"))  # not one of the six — kept, sorts last
    order = [c.evidence_kind for c in rm.list_collections(tenant("T"))]
    assert order == ["policy", "mystery"]


# --- opening a collection (filter by kind) ----------------------------------------------


def test_open_a_collection_filters_to_its_kind_newest_first() -> None:
    rm = seed_two_tenants()
    policies = rm.list_documents(tenant("T"), evidence_kind="policy")
    assert [d.document_id for d in policies] == ["d1", "d2"]
    assert all(d.evidence_kind == "policy" for d in policies)


def test_open_a_collection_is_tenant_scoped() -> None:
    rm = seed_two_tenants()
    # T2's only policy is x1; T opening "policy" must never surface it.
    ids = {d.document_id for d in rm.list_documents(tenant("T"), evidence_kind="policy")}
    assert "x1" not in ids


# --- projection semantics ---------------------------------------------------------------


def test_record_is_idempotent_upsert_and_status_advances() -> None:
    rm = InMemoryDocumentReadModel()
    rm.record(doc("d1", "T", status=DocumentStatus.INGESTING.value, uploaded_at=100.0))
    rm.record(doc("d1", "T", status=DocumentStatus.READY.value, uploaded_at=100.0))  # same id
    docs = rm.list_documents(tenant("T"))
    assert len(docs) == 1
    assert docs[0].status == "ready"


def test_fields_are_preserved_including_size() -> None:
    rm = InMemoryDocumentReadModel()
    rm.record(doc("d1", "T", filename="soc2.pdf", evidence_kind="soc_report", size=9001))
    got = rm.get("d1", tenant("T"))
    assert got is not None
    assert got.filename == "soc2.pdf" and got.evidence_kind == "soc_report" and got.size == 9001


# --- get-by-id (fail-closed) ------------------------------------------------------------


def test_get_returns_the_projection_for_the_tenant() -> None:
    rm = seed_two_tenants()
    got = rm.get("d3", tenant("T"))
    assert got is not None
    assert got.document_id == "d3" and got.evidence_kind == "procedure"


def test_get_is_fail_closed_across_tenants() -> None:
    rm = seed_two_tenants()
    assert rm.get("d1", tenant("T2")) is None  # d1 belongs to T
    assert rm.get("x1", tenant("T")) is None  # x1 belongs to T2
    assert rm.get("nope", tenant("T")) is None
