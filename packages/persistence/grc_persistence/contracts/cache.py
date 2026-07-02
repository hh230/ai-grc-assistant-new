"""Repository cache abstraction.

Repositories expose *cache hooks* (consult on read, invalidate on write) so a read-through
cache can be introduced later for hot, slow-changing aggregates (e.g. framework
definitions) without touching repository logic. The default binding is
:class:`NullRepositoryCache`, which makes every lookup a miss — preserving strict
read-your-writes and optimistic-concurrency semantics out of the box.

A cache implementation is responsible for returning **disconnected** values (e.g. fresh
copies); aggregates handed back from a repository are mutable and tracked for events, so a
real cache must never share a single instance across units of work.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class CacheKey:
    """A stable, namespaced cache key: ``<entity>:<tenant>:<identity>``.

    ``tenant`` is ``None`` for globally-scoped aggregates (frameworks, platform
    descriptors). Keeping the tenant in the key guarantees a cache can never serve one
    tenant's aggregate to another (CLAUDE.md §20).
    """

    __slots__ = ("entity", "tenant", "identity")

    def __init__(self, entity: str, identity: str, *, tenant: str | None = None) -> None:
        self.entity = entity
        self.tenant = tenant
        self.identity = identity

    def __str__(self) -> str:
        return f"{self.entity}:{self.tenant or '-'}:{self.identity}"

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"CacheKey({self!s})"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, CacheKey) and str(other) == str(self)

    def __hash__(self) -> int:
        return hash(str(self))


class RepositoryCache(ABC):
    """An optional read-through cache for aggregates, keyed by :class:`CacheKey`."""

    @abstractmethod
    async def get(self, key: CacheKey) -> Any | None: ...

    @abstractmethod
    async def set(self, key: CacheKey, value: Any) -> None: ...

    @abstractmethod
    async def invalidate(self, key: CacheKey) -> None: ...


class NullRepositoryCache(RepositoryCache):
    """The default no-op cache: every read misses, every write is dropped."""

    async def get(self, key: CacheKey) -> Any | None:
        return None

    async def set(self, key: CacheKey, value: Any) -> None:
        return None

    async def invalidate(self, key: CacheKey) -> None:
        return None
