"""UUID generator adapter for the application's ``IdGenerator`` port."""

from __future__ import annotations

import uuid

from grc_services.shared.ports import IdGenerator


class UuidGenerator(IdGenerator):
    """Generates random UUID4 identifiers as strings."""

    def new_id(self) -> str:
        return str(uuid.uuid4())
