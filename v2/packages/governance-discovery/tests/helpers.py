"""Test-only convenience for building a SignalSet without hand-writing every Signal's value_type."""

from __future__ import annotations

from governance_discovery.signal import Signal, SignalSet, ValueType

_ENUM_KEYS = {
    "primary_activity",
    "org_structure_state",
    "policy_state",
    "risk_register_state",
    "internal_audit_state",
    "execution_capacity",
    "tech_team_maturity",
    "cloud_data_residency_controlled",  # tri-state: no | partially | yes
    "held_licenses",
}
_BOOLEAN_KEYS = {
    "provides_saas",
    "has_compliance_officer",
    "has_legal_team",
    "has_it_team",
    "handles_personal_data",
    "has_gov_clients",
}
_DATE_KEYS = {"last_policy_review_date"}
_TEXT_KEYS = {"additional_context_note"}


def make_signals(**kwargs: object) -> SignalSet:
    signals: dict[str, Signal] = {}
    for key, value in kwargs.items():
        if key in _ENUM_KEYS:
            value_type = ValueType.ENUM
        elif key in _BOOLEAN_KEYS or isinstance(value, bool):
            value_type = ValueType.BOOLEAN
        elif key in _DATE_KEYS:
            value_type = ValueType.DATE
        elif key in _TEXT_KEYS:
            value_type = ValueType.TEXT
        elif isinstance(value, (int, float)):
            value_type = ValueType.NUMERIC
        else:
            value_type = ValueType.ENUM
        signals[key] = Signal(key=key, value_type=value_type, value=value)
    return SignalSet(signals)
