from __future__ import annotations

from devteam_chain import AttemptStore, ChainAlert, ChainAttempt


def test_chain_attempt_carries_its_number_and_mission_id() -> None:
    first = ChainAttempt("issue-1", mission_id="m-100")
    assert first.attempt_number == 1 and first.is_first
    assert first.label == "attempt 1"
    assert first.mission_id == "m-100"  # the record the store re-reads the mission's status from
    second = ChainAttempt("issue-1", 2, mission_id="m-200")
    assert second.attempt_number == 2 and not second.is_first


def test_attempt_store_keeps_the_full_chain_history_per_ref() -> None:
    store = AttemptStore()
    assert store.count("r") == 0 and store.latest("r") is None
    assert store.history("r") == ()
    first, second = ChainAttempt("r", 1), ChainAttempt("r", 2)
    store.record(first)
    store.record(second)
    assert store.history("r") == (first, second)  # the whole chain, in order — not just the last
    assert store.latest("r") == second
    assert store.count("r") == 2


def test_attempt_store_isolates_refs() -> None:
    store = AttemptStore()
    store.record(ChainAttempt("r", 1))
    store.record(ChainAttempt("r", 2))
    store.record(ChainAttempt("other", 1))
    assert store.count("r") == 2 and store.history("other") == (ChainAttempt("other", 1),)
    assert store.count("other") == 1
    assert store.count("unknown") == 0 and store.history("unknown") == ()


def test_forget_drops_a_chains_history_so_a_recurrence_starts_fresh() -> None:
    store = AttemptStore()
    store.record(ChainAttempt("r", 1))
    store.record(ChainAttempt("r", 2))
    store.forget("r")
    assert store.count("r") == 0 and store.latest("r") is None
    store.forget("r")  # idempotent — forgetting an unknown ref is a no-op
    store.record(ChainAttempt("r", 1))  # a recurrence starts a fresh lineage
    assert store.count("r") == 1


def test_chain_alert_carries_ref_count_and_reason() -> None:
    alert = ChainAlert(correlation_ref="r", attempts=3, reason="max attempts exceeded")
    assert alert.correlation_ref == "r"
    assert alert.attempts == 3
    assert "max attempts" in alert.reason
