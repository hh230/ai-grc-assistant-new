"""The **Export** Application service (Slice S3) — export goes through a contract, not `if fmt ==`.

The route never branches on format: it calls `ExportService.export(mission, fmt)`. The service holds
one `Exporter` per format (Markdown / DOCX / PDF today; more later) and routes to it — the same
registry shape as the builders, `ProjectionPort`, `MissionWorkflow`, `MissionAccess`. Each exporter
is an **abstraction**; the concrete ones (wrapping the `deliverables` render/export functions, which
pull rendering libraries) are wired in the composition root, so this layer's Use-Case boundary stays
clean (ADR 0054 §6).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from mission_application.contracts import UnsupportedFormat
from mission_application.result_views import ResultView


@dataclass(frozen=True)
class ExportedFile:
    """A rendered export: the bytes plus what a client needs to receive them."""

    content: bytes
    media_type: str
    filename: str


@runtime_checkable
class Exporter(Protocol):
    """Render a **`ResultView`** — what the user sees — to one format's bytes. Export renders the
    result, not the mission, so it is independent of how the result was built."""

    def export(self, result: ResultView) -> ExportedFile: ...


class ExportService:
    """Routes an export request to the `Exporter` for its format. Adding a format is one entry in
    the map; the route and callers never change. Exports the `ResultView` (product truth), not the
    Mission (an internal data source)."""

    def __init__(self, exporters: dict[str, Exporter]) -> None:
        self._exporters = dict(exporters)

    def formats(self) -> tuple[str, ...]:
        return tuple(self._exporters)

    def export(self, result: ResultView, fmt: str) -> ExportedFile:
        exporter = self._exporters.get(fmt)
        if exporter is None:
            raise UnsupportedFormat(f"unsupported export format: {fmt!r}")
        return exporter.export(result)
