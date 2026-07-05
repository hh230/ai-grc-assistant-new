"""Puts this directory on ``sys.path`` so ``_fakes`` resolves by plain import.

Under ``--import-mode=importlib`` (repo-wide pytest config), a bare relative import
(``from ._fakes import ...``) resolves against whichever same-named ``tests`` package happens
to be cached first in ``sys.modules`` when the *whole* monorepo suite runs together — several
packages have a ``tests/`` directory, and only one dotted ``tests`` module can exist at a time.
Explicitly adding this directory to ``sys.path`` sidesteps that collision entirely.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
