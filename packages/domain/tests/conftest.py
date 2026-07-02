"""Pytest setup for the pure domain layer.

Makes ``grc_domain`` importable without installing the package (it is pure stdlib), so the
suite runs with ``python -m pytest packages/domain/tests`` from the repo root.
"""
from __future__ import annotations

import pathlib
import sys

_DOMAIN_ROOT = pathlib.Path(__file__).resolve().parents[1]  # packages/domain
if str(_DOMAIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_DOMAIN_ROOT))
