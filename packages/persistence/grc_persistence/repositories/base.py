"""Base repository: the reusable persistence mechanics shared by every repository.

Per the layer's rules, a repository performs only: query construction, persistence
orchestration, optimistic concurrency, aggregate tracking, child synchronization and cache
hooks. All field-level translation is delegated to a mapper. This base centralizes the
mechanics so the concrete repositories contain almost nothing but their *queries*.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Generic, Protocol, TypeVar

from grc_services.shared.exceptions import ConcurrencyError
from sqlalchemy import ColumnElement, ColumnExpressionArgument, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..contracts.cache import CacheKey, RepositoryCache
from ..contracts.mapper import AggregateMapper
from ..contracts.tracking import AggregateTracker


class _HasTablename(Protocol):
    __tablename__: str


D = TypeVar("D")
M = TypeVar("M", bound=_HasTablename)


class SqlAlchemyAggregateRepository(Generic[D, M]):
    """Mechanics for an aggregate persisted as one root row (+ optional child tables)."""

    def __init__(
        self,
        session: AsyncSession,
        mapper: AggregateMapper[D, M],
        tracker: AggregateTracker,
        cache: RepositoryCache,
        model: type[M],
    ) -> None:
        self._session = session
        self._mapper = mapper
        self._tracker = tracker
        self._cache = cache
        self._model = model
        self._entity = model.__tablename__
        # Strong references to the ORM rows loaded in this unit of work. SQLAlchemy's
        # identity map is *weak*; without this the loaded row could be garbage-collected and
        # a later save() would re-read the current version, defeating optimistic concurrency.
        # Keeping the row pinned is what makes the version loaded at read time authoritative.
        self._loaded: list[M] = []

    # --- cache hooks ----------------------------------------------------------------
    def _key(self, identity: str, tenant: str | None = None) -> CacheKey:
        return CacheKey(self._entity, identity, tenant=tenant)

    # --- aggregate tracking ---------------------------------------------------------
    def _track(self, aggregate: D) -> None:
        self._tracker.track(aggregate)  # type: ignore[arg-type]

    # --- query construction ---------------------------------------------------------
    async def _fetch_one(self, *where: ColumnElement[bool]) -> M | None:
        result = await self._session.execute(select(self._model).where(*where))
        return result.scalar_one_or_none()

    async def _fetch_all(
        self, *where: ColumnElement[bool], order_by: ColumnExpressionArgument[Any] | None = None
    ) -> list[M]:
        stmt = select(self._model).where(*where)
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    def _materialize(self, model: M) -> D:
        self._loaded.append(model)  # pin the row (see __init__) so its version stays authoritative
        aggregate = self._mapper.to_domain(model)
        self._track(aggregate)
        return aggregate

    # --- read (with cache hook) -----------------------------------------------------
    async def _get_by(self, key: CacheKey, *where: ColumnElement[bool]) -> D | None:
        cached = await self._cache.get(key)
        if cached is not None:
            return cached  # type: ignore[no-any-return]
        model = await self._fetch_one(*where)
        if model is None:
            return None
        aggregate = self._materialize(model)
        await self._cache.set(key, aggregate)
        return aggregate

    async def _list_by(
        self, *where: ColumnElement[bool], order_by: ColumnExpressionArgument[Any] | None = None
    ) -> list[D]:
        rows = await self._fetch_all(*where, order_by=order_by)
        return [self._materialize(model) for model in rows]

    # --- write ----------------------------------------------------------------------
    async def _insert(self, aggregate: D, key: CacheKey) -> None:
        self._session.add(self._mapper.to_orm(aggregate))
        self._track(aggregate)
        await self._cache.invalidate(key)

    async def _update(
        self,
        aggregate: D,
        key: CacheKey,
        *,
        pk: object,
        tenant: str | None = None,
        tenant_attr: str = "organization_id",
        sync: Callable[[M], None] | None = None,
    ) -> None:
        # Retrieve the *managed* row via the identity map (no refreshing SELECT), so the
        # version pinned at load time is preserved — that is what makes optimistic
        # concurrency detect a concurrent writer at commit. ``session.get`` is PK-only, so
        # we re-check the tenant defensively for the rare save-without-prior-get path.
        model: M | None = await self._session.get(self._model, pk)
        if model is None:
            raise ConcurrencyError(
                f"{self._entity} '{aggregate.id}' no longer exists or is not visible "  # type: ignore[attr-defined]
                "to this tenant"
            )
        if tenant is not None and getattr(model, tenant_attr) != tenant:
            raise ConcurrencyError(
                f"{self._entity} '{aggregate.id}' is not visible to this tenant"  # type: ignore[attr-defined]
            )
        self._mapper.update_orm(model, aggregate)
        if sync is not None:
            sync(model)
        self._track(aggregate)
        await self._cache.invalidate(key)
