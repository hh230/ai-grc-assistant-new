"""The Capability Selector: existence-only decision — known → it, unknown → fallback."""

from __future__ import annotations

import pytest
from assistant_runtime import (
    Capability,
    CapabilityCatalog,
    CapabilityIntent,
    CapabilitySelector,
    FallbackCapabilityMissing,
)


def test_known_candidate_is_selected(capability_catalog: CapabilityCatalog) -> None:
    selector = CapabilitySelector(capability_catalog)
    intent = CapabilityIntent(capability_id="vendor_risk_assessment", confidence=0.9)
    assert selector.select(intent).id == "vendor_risk_assessment"


def test_unknown_candidate_falls_back_to_simple_question(
    capability_catalog: CapabilityCatalog,
) -> None:
    selector = CapabilitySelector(capability_catalog)
    # empty candidate (recognizer had no idea) → the fallback
    assert selector.select(CapabilityIntent(capability_id="")).id == "simple_question"
    # a hallucinated/unregistered candidate → still the fallback (never returned as-is)
    hallucinated = CapabilityIntent(capability_id="make_me_a_sandwich")
    assert selector.select(hallucinated).id == "simple_question"


def test_confidence_is_ignored_in_slice_2(capability_catalog: CapabilityCatalog) -> None:
    """The selector's only question is existence (ADR 0046 §4): a registered candidate is selected
    regardless of confidence; no threshold logic in Slice 2."""
    selector = CapabilitySelector(capability_catalog)
    intent = CapabilityIntent(capability_id="vendor_risk_assessment", confidence=0.01)
    assert selector.select(intent).id == "vendor_risk_assessment"


def test_missing_fallback_fails_loud() -> None:
    catalog = CapabilityCatalog([Capability(id="only", resolver="mt")])  # no simple_question
    selector = CapabilitySelector(catalog)
    with pytest.raises(FallbackCapabilityMissing, match="simple_question"):
        selector.select(CapabilityIntent(capability_id="unknown"))
