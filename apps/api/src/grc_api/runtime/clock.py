"""System clock adapter for the application's ``Clock`` port."""

from __future__ import annotations

from datetime import datetime, timezone

from grc_services.shared.ports import Clock


class SystemClock(Clock):
    """Returns timezone-aware UTC now. The single source of 'now' for wired use cases."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)
