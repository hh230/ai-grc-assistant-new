"""The three S3 contracts before the concrete adapters: `DeliverableProvider` + `FrameworkProvider`
(a builder's sources, abstracted) and `ExportService` (export the `ResultView` via a contract)."""

from __future__ import annotations

from typing import Any

import pytest
from mission_application import (
    DeliverableProvider,
    ExportedFile,
    Exporter,
    ExportService,
    FrameworkProvider,
    GenericContent,
    ResultView,
    TrustBar,
    UnsupportedFormat,
)


def _result() -> ResultView:
    return ResultView(
        mission_id="m1",
        title="Result",
        trust=TrustBar(evidence_count=0, human_review="Not required", updated_at=1.0),
        content=GenericContent(sections=()),
    )


def test_framework_provider_is_structural() -> None:
    class _BundledProvider:
        def get(self, framework_id: str) -> Any:
            return {"id": framework_id, "controls": ()}

    provider = _BundledProvider()
    assert isinstance(provider, FrameworkProvider)  # runtime_checkable structural port
    assert provider.get("framework:iso_27001")["id"] == "framework:iso_27001"


def test_deliverable_provider_is_structural() -> None:
    class _BundledDeliverableProvider:
        def build(self, mission: Any) -> Any:
            return {"sections": ()}

    assert isinstance(_BundledDeliverableProvider(), DeliverableProvider)


class _FakeExporter:
    """Exports a ResultView (what the user sees), never the mission."""

    def __init__(self, media_type: str) -> None:
        self._media_type = media_type

    def export(self, result: ResultView) -> ExportedFile:
        return ExportedFile(content=b"bytes", media_type=self._media_type, filename=result.title)


def test_export_service_routes_by_format() -> None:
    service = ExportService(
        {
            "md": _FakeExporter("text/markdown"),
            "pdf": _FakeExporter("application/pdf"),
        }
    )
    assert set(service.formats()) == {"md", "pdf"}
    out = service.export(_result(), fmt="pdf")
    assert isinstance(out, ExportedFile)
    assert out.media_type == "application/pdf" and out.content == b"bytes"


def test_exporter_is_structural() -> None:
    assert isinstance(_FakeExporter("text/markdown"), Exporter)


def test_unknown_format_raises_unsupported_format() -> None:
    service = ExportService({"md": _FakeExporter("text/markdown")})
    with pytest.raises(UnsupportedFormat):
        service.export(_result(), fmt="xlsx")
