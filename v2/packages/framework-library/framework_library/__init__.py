"""Rasheed V2 Framework Library (ADR 0050) — the first real GRC tool.

Compliance frameworks as **data** (CLAUDE.md §13): a `FrameworkLibrary` loads framework definitions
from JSON data files, and `ControlLibraryTool` exposes a deterministic, read-only lookup over them
(by code, theme, or title keyword) as a registered `Tool`. A new framework is a new data file — no
code change. Bundled: the complete ISO/IEC 27001:2022 Annex A catalog (93 controls).
"""

from framework_library.errors import (
    FrameworkLibraryError,
    FrameworkNotFound,
    InvalidFrameworkDefinition,
)
from framework_library.library import (
    FrameworkLibrary,
    framework_from_dict,
    framework_from_file,
)
from framework_library.models import (
    Control,
    EvidenceExpectation,
    Framework,
    Requirement,
)
from framework_library.tool import (
    CONTROL_LIBRARY_TOOL,
    DEFAULT_FRAMEWORK_ID,
    ControlLibraryTool,
)

__all__ = [
    # domain
    "Framework",
    "Control",
    "Requirement",
    "EvidenceExpectation",
    # library
    "FrameworkLibrary",
    "framework_from_dict",
    "framework_from_file",
    # tool
    "ControlLibraryTool",
    "CONTROL_LIBRARY_TOOL",
    "DEFAULT_FRAMEWORK_ID",
    # errors
    "FrameworkLibraryError",
    "FrameworkNotFound",
    "InvalidFrameworkDefinition",
]
