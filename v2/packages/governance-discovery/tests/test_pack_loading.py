from governance_discovery.pack import CORE_PACK_ID, load_bundled_packs


def test_bundled_packs_load_and_include_core() -> None:
    packs = load_bundled_packs()
    assert CORE_PACK_ID in packs
    assert packs[CORE_PACK_ID].is_always_active


def test_core_pack_has_no_activation_predicate() -> None:
    packs = load_bundled_packs()
    assert packs[CORE_PACK_ID].activation_predicate is None


def test_technology_and_cloud_provider_packs_have_activation_predicates() -> None:
    packs = load_bundled_packs()
    assert not packs["pack:technology"].is_always_active
    assert not packs["pack:cloud_provider"].is_always_active
    assert packs["pack:technology"].activation_predicate is not None


def test_every_question_has_a_valid_typed_value_type() -> None:
    from governance_discovery.signal import ValueType

    packs = load_bundled_packs()
    for pack in packs.values():
        for question in pack.questions:
            assert isinstance(question.value_type, ValueType)
            assert question.writes_signal
            assert question.priority > 0


def test_every_rule_predicate_is_evaluable_data() -> None:
    packs = load_bundled_packs()
    for pack in packs.values():
        for rule in pack.rules:
            assert isinstance(rule.predicate, dict)


def test_pack_ids_are_namespaced() -> None:
    packs = load_bundled_packs()
    assert all(pack_id.startswith("pack:") for pack_id in packs)


def test_every_plan_seed_names_a_pillar_the_UI_can_LABEL():
    """A stray `"cyber"` where every other rule said `"cyber_security"` reached a real customer's
    plan and rendered as a missing-translation error. One pillar, one name — the same class of bug
    as two names for one question type, and the same fix.

    The list is duplicated here on purpose: this test's job is to fail when the packs and the
    interface drift apart, which it cannot do if it reads the same source they do.
    """
    labelled = {
        "organization", "risk", "compliance", "policies", "governance", "legal", "cyber_security",
    }
    used = {
        rule.effect.plan_seed.pillar
        for pack in load_bundled_packs().values()
        for rule in pack.rules
        if rule.effect.plan_seed is not None
    }
    assert used <= labelled, f"plan seeds name pillars the interface cannot label: {used - labelled}"
