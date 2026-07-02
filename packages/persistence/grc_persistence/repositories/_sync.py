"""Diff-based child synchronization keyed on stable identifiers.

Given the current ORM child rows and the desired domain children, this computes the minimal
add / update / remove set keyed on each child's *stable id* and applies it in place on the
ORM relationship collection. Appends and removals turn into INSERTs and (delete-orphan)
DELETEs at flush; ``position`` records the domain ordering. The per-row translation is
delegated to a :class:`ChildMapper` — this module performs *orchestration only*.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TypeVar

from ..contracts.mapper import ChildMapper

CHILD = TypeVar("CHILD")
CHILD_ORM = TypeVar("CHILD_ORM")


def sync_children(
    orm_children: list[CHILD_ORM],
    domain_children: Sequence[CHILD],
    mapper: ChildMapper[CHILD, CHILD_ORM],
    parent_id: str,
) -> None:
    """Reconcile ``orm_children`` to match ``domain_children`` (add / update / remove)."""
    existing = {mapper.orm_identity(model): model for model in orm_children}
    desired_ids: set[str] = set()

    for position, child in enumerate(domain_children):
        identity = mapper.identity(child)
        desired_ids.add(identity)
        current = existing.get(identity)
        if current is None:
            orm_children.append(mapper.to_orm(child, parent_id, position))
        else:
            mapper.update_orm(current, child, position)

    for identity, model in existing.items():
        if identity not in desired_ids:
            orm_children.remove(model)
