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
