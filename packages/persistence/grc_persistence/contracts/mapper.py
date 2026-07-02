"""The Domain ↔ ORM translation contract.

Mappers are the **only** component permitted to translate between domain aggregates and
ORM models (the architectural rule enforced for this layer). Repositories orchestrate
persistence (query construction, optimistic concurrency, child synchronization, cache
hooks) and delegate every field-level translation to a mapper.

Two contracts are defined:

- :class:`AggregateMapper` for an aggregate root and its row.
- :class:`ChildMapper` for a child entity persisted in its own table and synchronized by a
  diff keyed on a *stable identifier* (e.g. a mission step's id).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

DOMAIN = TypeVar("DOMAIN")
ORM = TypeVar("ORM")
CHILD = TypeVar("CHILD")
CHILD_ORM = TypeVar("CHILD_ORM")


class AggregateMapper(ABC, Generic[DOMAIN, ORM]):
    """Bidirectional translation for a single aggregate root.

    ``to_orm`` builds a fresh row (insert path). ``update_orm`` copies the aggregate's
    current state onto an already-managed row (update path) — it must touch *root scalar
    columns only*; child collections are synchronized by the repository through
    :class:`ChildMapper`. ``to_domain`` rebuilds the aggregate from a loaded row.
    """

    @abstractmethod
    def to_orm(self, aggregate: DOMAIN) -> ORM:
        """Build a brand-new ORM row (including child rows) from an aggregate."""
        ...

    @abstractmethod
    def update_orm(self, model: ORM, aggregate: DOMAIN) -> None:
        """Copy root scalar/JSON columns from the aggregate onto a managed row."""
        ...

    @abstractmethod
    def to_domain(self, model: ORM) -> DOMAIN:
        """Reconstruct the aggregate (including children) from a loaded row."""
        ...


class ChildMapper(ABC, Generic[CHILD, CHILD_ORM]):
    """Translation + stable identity for a child entity kept in its own table.

    The repository diffs the desired (domain) children against the current (ORM) children
    using :meth:`identity`, then applies the result with :meth:`to_orm` /
    :meth:`update_orm`. ``position`` preserves the domain ordering of the collection.
    """

    @abstractmethod
    def identity(self, child: CHILD) -> str:
        """Stable identifier of a domain child (used as the diff key)."""
        ...

    @abstractmethod
    def orm_identity(self, model: CHILD_ORM) -> str:
        """Stable identifier of an ORM child (used as the diff key)."""
        ...

    @abstractmethod
    def to_orm(self, child: CHILD, parent_id: str, position: int) -> CHILD_ORM:
        """Build a fresh child row belonging to ``parent_id`` at ``position``."""
        ...

    @abstractmethod
    def update_orm(self, model: CHILD_ORM, child: CHILD, position: int) -> None:
        """Copy the child's state onto a managed child row at ``position``."""
        ...

    @abstractmethod
    def to_domain(self, model: CHILD_ORM) -> CHILD:
        """Reconstruct the domain child from a loaded child row."""
        ...
