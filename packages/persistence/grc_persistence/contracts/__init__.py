"""Persistence-layer contracts — the stable seams of the infrastructure layer.

These abstractions decouple the moving parts of the persistence layer from one another so
each can evolve independently (CLAUDE.md §5 "AI as an isolated, swappable layer" applied to
storage):

- :class:`AggregateMapper` / :class:`ChildMapper` — the Domain ↔ ORM translation contract.
  Concrete mappers live in :mod:`grc_persistence.mappers`; nothing else may translate.
- :class:`RepositoryCache` / :class:`NullRepositoryCache` — an optional read-through cache
  the repositories consult through hooks. The default is the null object.
- :class:`Outbox` / :class:`IntegrationEvent` — the transactional outbox seam: the single
  source of integration events.
- :class:`AggregateTracker` — how repositories register touched aggregates so the Unit of
  Work can collect their recorded domain events.
"""

from __future__ import annotations

from .cache import CacheKey, NullRepositoryCache, RepositoryCache
from .mapper import AggregateMapper, ChildMapper
from .outbox import IntegrationEvent, Outbox
from .tracking import AggregateTracker

__all__ = [
    "AggregateMapper",
    "ChildMapper",
    "RepositoryCache",
    "NullRepositoryCache",
    "CacheKey",
    "Outbox",
    "IntegrationEvent",
    "AggregateTracker",
]
