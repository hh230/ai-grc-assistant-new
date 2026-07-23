"""The Capability Catalog is a plain registry — register, look up, reject duplicates. No logic."""

from __future__ import annotations

import pytest
from assistant_runtime import Capability, CapabilityCatalog


def test_register_and_get() -> None:
    catalog = CapabilityCatalog([Capability(id="a", resolver="mt_a")])
    assert catalog.get("a") == Capability(id="a", resolver="mt_a")
    assert "a" in catalog
    assert catalog.ids() == ("a",)


def test_unknown_id_is_none() -> None:
    catalog = CapabilityCatalog([Capability(id="a", resolver="mt_a")])
    assert catalog.get("nope") is None
    assert "nope" not in catalog


def test_duplicate_id_is_rejected_loudly() -> None:
    catalog = CapabilityCatalog([Capability(id="a", resolver="mt_a")])
    with pytest.raises(ValueError, match="already registered"):
        catalog.register(Capability(id="a", resolver="mt_other"))
