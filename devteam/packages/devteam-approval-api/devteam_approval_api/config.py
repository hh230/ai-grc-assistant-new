"""Config for the Approval API — the one thing it needs is *where the shared approval store lives*.

The daemon writes the same file (that is the whole file-store + reconcile design). ``RASHEED_APPROVAL_STORE``
overrides the path; the default sits beside the lifecycle snapshot the daemon already keeps.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_DEFAULT_STORE = Path.home() / ".rasheed" / "approvals.json"


@dataclass(frozen=True)
class ApprovalApiConfig:
    store_path: Path


def load_config() -> ApprovalApiConfig:
    raw = os.environ.get("RASHEED_APPROVAL_STORE", "").strip()
    return ApprovalApiConfig(store_path=Path(raw) if raw else _DEFAULT_STORE)
