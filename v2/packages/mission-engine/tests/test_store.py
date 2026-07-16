"""The reference store (ADR 0040 §5): reads are tenant-scoped by construction — a mission is
never visible to a foreign tenant, and idempotency keys never collide across tenants."""

from mission_engine import InMemoryMissionStore, Mission


def test_save_and_get_within_the_owning_tenant(tenant):
    store = InMemoryMissionStore()
    mission = Mission.create(goal="g", tenant=tenant)
    store.save(mission)
    assert store.get(mission.id, tenant) is mission


def test_a_foreign_tenant_cannot_read_the_mission(tenant, other_tenant):
    store = InMemoryMissionStore()
    mission = Mission.create(goal="g", tenant=tenant)
    store.save(mission)
    assert store.get(mission.id, other_tenant) is None  # not found, never returned


def test_idempotency_lookup_is_tenant_scoped(tenant, other_tenant):
    store = InMemoryMissionStore()
    mission = Mission.create(goal="g", tenant=tenant, idempotency_key="k1")
    store.save(mission)
    assert store.find_by_idempotency_key(tenant, "k1") is mission
    assert store.find_by_idempotency_key(other_tenant, "k1") is None
    assert store.find_by_idempotency_key(tenant, "") is None  # empty key never matches
