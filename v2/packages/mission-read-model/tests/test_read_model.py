"""S1 acceptance for the Mission read model, verified on the in-memory adapter (no Postgres).

These map to the Execution Contract's Given/When/Then: a Practitioner sees their tenant's missions
newest-first; can filter by status and type; can search by title; and NEVER sees another tenant's
missions (fail-closed). Ordering, paging, and upsert idempotency are pinned so the Postgres adapter
has an exact spec to match.
"""

from __future__ import annotations

from mission_read_model import InMemoryMissionListReadModel, MissionListItem
from pipeline_contracts import TenantContext


def tenant(tenant_id: str) -> TenantContext:
    return TenantContext(
        tenant_id=tenant_id, principal_id="user-1", roles=("practitioner",), region="ksa"
    )


def item(
    mission_id: str,
    tenant_id: str,
    *,
    mission_type: str = "gap_assessment",
    title: str = "Technological controls",
    status: str = "executing",
    created_at: float = 100.0,
    updated_at: float = 100.0,
) -> MissionListItem:
    return MissionListItem(
        mission_id=mission_id,
        tenant_id=tenant_id,
        mission_type=mission_type,
        title=title,
        status=status,
        created_at=created_at,
        updated_at=updated_at,
    )


def seed_two_tenants() -> InMemoryMissionListReadModel:
    rm = InMemoryMissionListReadModel()
    # tenant T: 3 missions, distinct updated_at so ordering is unambiguous
    rm.record(item("m1", "T", status="executing", updated_at=300.0))
    rm.record(item("m2", "T", status="completed", updated_at=200.0, mission_type="risk_assessment"))
    rm.record(item("m3", "T", status="awaiting_approval", updated_at=100.0, title="Vendor Acme"))
    # tenant T2: 2 missions the caller from T must never see
    rm.record(item("x1", "T2"))
    rm.record(item("x2", "T2"))
    return rm


# --- fail-closed tenant isolation -------------------------------------------------------


def test_lists_only_the_callers_tenant() -> None:
    rm = seed_two_tenants()
    page = rm.list_missions(tenant("T"))
    assert page.total == 3
    assert {i.mission_id for i in page.items} == {"m1", "m2", "m3"}


def test_never_returns_another_tenants_missions() -> None:
    rm = seed_two_tenants()
    for i in rm.list_missions(tenant("T")).items:
        assert i.tenant_id == "T"
    # and the reverse direction: T2 sees only its own, never T's
    ids_t2 = {i.mission_id for i in rm.list_missions(tenant("T2")).items}
    assert ids_t2 == {"x1", "x2"}


def test_unknown_tenant_sees_empty_page() -> None:
    rm = seed_two_tenants()
    page = rm.list_missions(tenant("does-not-exist"))
    assert page.items == ()
    assert page.total == 0


# --- ordering ---------------------------------------------------------------------------


def test_orders_newest_updated_first() -> None:
    rm = seed_two_tenants()
    order = [i.mission_id for i in rm.list_missions(tenant("T")).items]
    assert order == ["m1", "m2", "m3"]


# --- filters & search -------------------------------------------------------------------


def test_filter_by_status() -> None:
    rm = seed_two_tenants()
    page = rm.list_missions(tenant("T"), status="completed")
    assert [i.mission_id for i in page.items] == ["m2"]
    assert page.total == 1


def test_filter_by_type() -> None:
    rm = seed_two_tenants()
    page = rm.list_missions(tenant("T"), mission_type="risk_assessment")
    assert [i.mission_id for i in page.items] == ["m2"]


def test_text_search_is_case_insensitive_on_title() -> None:
    rm = seed_two_tenants()
    page = rm.list_missions(tenant("T"), query="acme")
    assert [i.mission_id for i in page.items] == ["m3"]


def test_filters_combine() -> None:
    rm = seed_two_tenants()
    # status that no gap_assessment row has → empty, even though the type matches
    page = rm.list_missions(tenant("T"), mission_type="gap_assessment", status="completed")
    assert page.total == 0


# --- pagination -------------------------------------------------------------------------


def test_pagination_windows_and_reports_total() -> None:
    rm = seed_two_tenants()
    p1 = rm.list_missions(tenant("T"), page=1, page_size=2)
    assert [i.mission_id for i in p1.items] == ["m1", "m2"]
    assert p1.total == 3 and p1.has_next is True

    p2 = rm.list_missions(tenant("T"), page=2, page_size=2)
    assert [i.mission_id for i in p2.items] == ["m3"]
    assert p2.has_next is False


def test_page_size_is_bounded() -> None:
    rm = seed_two_tenants()
    page = rm.list_missions(tenant("T"), page_size=10_000)
    assert page.page_size <= 200


# --- projection semantics ---------------------------------------------------------------


def test_record_is_idempotent_upsert_by_mission_id() -> None:
    rm = InMemoryMissionListReadModel()
    rm.record(item("m1", "T", status="executing", updated_at=100.0))
    rm.record(item("m1", "T", status="completed", updated_at=150.0))  # same id → status advances
    page = rm.list_missions(tenant("T"))
    assert page.total == 1
    assert page.items[0].status == "completed"


# --- get-by-id (S2: type/scope for the detail view) -------------------------------------


def test_get_returns_the_projection_for_the_tenant() -> None:
    rm = seed_two_tenants()
    got = rm.get("m2", tenant("T"))
    assert got is not None
    assert got.mission_id == "m2" and got.mission_type == "risk_assessment"


def test_get_is_fail_closed_across_tenants() -> None:
    rm = seed_two_tenants()
    assert rm.get("m1", tenant("T2")) is None  # m1 belongs to T
    assert rm.get("x1", tenant("T")) is None  # x1 belongs to T2
    assert rm.get("nope", tenant("T")) is None
