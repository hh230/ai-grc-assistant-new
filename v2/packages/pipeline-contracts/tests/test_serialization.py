"""The shared serialization helpers — the to_dict conventions every contract model relies on.

Every contract crosses a boundary as JSON at some point (an audit record, an API response,
a stored artifact), and they all get there through these two functions.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum

from pipeline_contracts import dataclass_dict, to_plain


class Colour(str, Enum):
    RED = "red"


@dataclass
class Nested:
    label: str

    def to_dict(self) -> dict[str, object]:
        return {"label": self.label, "nested": True}


@dataclass
class Sample:
    name: str
    colour: Colour
    tags: tuple[str, ...]
    nested: Nested
    scores: dict[str, float] = field(default_factory=dict)
    secret: str = "hidden"


def make_sample() -> Sample:
    return Sample(name="n", colour=Colour.RED, tags=("a", "b"), nested=Nested("x"),
                  scores={"vector": 0.5})


# ── to_plain ──────────────────────────────────────────────────────────────────
def test_to_plain_passes_scalars_through_untouched():
    for value in ("s", 1, 1.5, True, None):
        assert to_plain(value) == value


def test_to_plain_unwraps_enums_to_their_value():
    assert to_plain(Colour.RED) == "red"


def test_to_plain_renders_tuples_and_lists_as_lists():
    assert to_plain(("a", "b")) == ["a", "b"]
    assert to_plain(["a"]) == ["a"]


def test_to_plain_delegates_to_a_models_own_to_dict():
    """Which is what lets each model keep its custom schema — exclusions and computed keys
    stay visible at the model rather than being reflected over here."""
    assert to_plain(Nested("x")) == {"label": "x", "nested": True}


def test_to_plain_recurses_through_containers():
    assert to_plain({"k": [Colour.RED, Nested("y")]}) == {"k": ["red", {"label": "y", "nested": True}]}


def test_to_plain_keeps_dict_keys_as_they_are():
    assert to_plain({"vector": 0.5}) == {"vector": 0.5}


# ── dataclass_dict ────────────────────────────────────────────────────────────
def test_dataclass_dict_converts_every_field_in_declaration_order():
    data = dataclass_dict(make_sample())
    assert list(data) == ["name", "colour", "tags", "nested", "scores", "secret"]
    assert data["colour"] == "red"
    assert data["tags"] == ["a", "b"]
    assert data["nested"] == {"label": "x", "nested": True}
    json.dumps(data)


def test_exclude_drops_internal_fields():
    data = dataclass_dict(make_sample(), exclude=("secret",))
    assert "secret" not in data
    assert "name" in data


def test_extra_appends_computed_keys():
    data = dataclass_dict(make_sample(), extra={"computed": 42})
    assert data["computed"] == 42


def test_extra_overrides_a_field_of_the_same_name():
    """How a model keeps a legacy wire shape for one field without hand-rolling the rest."""
    data = dataclass_dict(make_sample(), extra={"tags": "raw"})
    assert data["tags"] == "raw"


def test_an_excluded_field_can_be_re_added_by_extra_in_a_custom_shape():
    data = dataclass_dict(make_sample(), exclude=("nested",), extra={"nested": "flattened"})
    assert data["nested"] == "flattened"
