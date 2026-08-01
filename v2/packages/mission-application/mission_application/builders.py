"""The **builder family** behind a Result (Slice S3, the Builder Capability Gate).

There is not one builder but a family: `build_deliverable` is generic (any mission);
`build_gap_matrix` is Gap-Assessment-only. So the builder choice must not be an
`if mission.type == GAP` in the route — it is a **registry** keyed by mission type. `ResultQuery`
asks the registry; the route and the Presenter never branch on type. Adding a
`VendorAssessmentBuilder` in S4 is one `register(...)` call.

This module holds the **abstraction** — the `DeliverableBuilder` protocol and the registry. The
concrete builders wrap the `deliverables` package and are wired in the composition root, so this
layer stays free of rendering/framework libraries (the Use-Case boundary, ADR 0054 §6).
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from mission_application.result_views import ResultContent


@runtime_checkable
class DeliverableBuilder(Protocol):
    """Build a mission's Result **content** — not the whole view. The Trust Bar, title, and metadata
    are the *frame*, assembled by `ResultQuery`, not here; so a builder never re-derives them and
    cannot drift into a 'disguised Presenter'. One builder per mission-type family."""

    def build_content(self, mission: Any) -> ResultContent: ...


class DeliverableBuilderRegistry:
    """Maps a mission type to its builder, with a default for types that have no special builder.
    *Result adapts to the mission, not the mission to the Result* — this is where that happens."""

    def __init__(
        self,
        *,
        default: DeliverableBuilder,
        by_type: dict[str, DeliverableBuilder] | None = None,
    ) -> None:
        self._default = default
        self._by_type = dict(by_type or {})

    def register(self, mission_type: str, builder: DeliverableBuilder) -> None:
        self._by_type[mission_type] = builder

    def for_mission(self, mission: Any, mission_type: str) -> DeliverableBuilder:
        """Select the builder for a mission. It takes the **whole mission** (not just its type), so
        the selection can grow beyond type later — framework, capability, version, tenant flags —
        without changing this signature or any caller. Today it keys on `mission_type` alone."""
        return self._by_type.get(mission_type, self._default)
