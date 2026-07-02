"""Plugin Management capability."""

from __future__ import annotations

from .dtos import PluginDTO
from .service import PluginApplicationService

__all__ = ["PluginApplicationService", "PluginDTO"]
