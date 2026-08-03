from governance_discovery.signal import Signal, SignalSet, ValueType


def test_signal_set_get_and_has() -> None:
    s = SignalSet().with_signal(Signal(key="employee_count", value_type=ValueType.NUMERIC, value=15))
    assert s.has("employee_count")
    assert s.value("employee_count") == 15
    assert s.get("missing") is None
    assert s.value("missing", default="fallback") == "fallback"


def test_with_signal_is_immutable_and_latest_wins() -> None:
    s1 = SignalSet().with_signal(Signal(key="k", value_type=ValueType.BOOLEAN, value=True))
    s2 = s1.with_signal(Signal(key="k", value_type=ValueType.BOOLEAN, value=False))
    assert s1.value("k") is True  # s1 unchanged
    assert s2.value("k") is False  # s2 has the latest value
    assert len(s1) == 1 and len(s2) == 1


def test_as_dict_and_keys() -> None:
    s = SignalSet().with_signal(
        Signal(key="a", value_type=ValueType.NUMERIC, value=1)
    ).with_signal(Signal(key="b", value_type=ValueType.BOOLEAN, value=True))
    assert s.as_dict() == {"a": 1, "b": True}
    assert s.keys() == frozenset({"a", "b"})
