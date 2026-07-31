"""The AI Organization Connectors framework — a read-only integration layer (§11).

A Job never talks to an external system directly: it requests a Connector from the registry
``fetch()``. A connector observes ONE kind of system (a website, GitHub, a report file, the runtime)
and returns a ``ConnectorResult`` — never an exception, never fabricated data. When a source is
unavailable it returns ``UNAVAILABLE`` with empty data, and the job opens no mission.

    Job → Connector → External System → Evidence → Mission

This module is the generic contract: the ``Connector`` protocol, the ``ConnectorResult``/``Health``/
``Status`` value types, and the ``ConnectorRegistry`` (with a TTL cache and per-connector
``ConnectorMetrics``) that jobs fetch through. The registry is the ONLY fetch path, so caching,
timing, metrics, health, and fail-safe wrapping live in one place.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol, runtime_checkable

from devteam_protocol import AgentRole


class ConnectorType(str, Enum):
    WEBSITE = "website"
    HTTP_SECURITY = "http_security"
    TLS = "tls"
    GITHUB = "github"
    PLAYWRIGHT = "playwright"
    TEST_REPORTS = "test_reports"
    VULNERABILITY = "vulnerability"
    SECRETS = "secrets"
    COMPLIANCE = "compliance"
    RUNTIME = "runtime"
    FILESYSTEM = "filesystem"


class ConnectorStatus(str, Enum):
    """The outcome of one fetch. ``UNAVAILABLE`` = the source could not be reached (no evidence, and
    NOT an error to escalate); ``ERROR`` = the fetch itself failed unexpectedly; ``DISABLED`` = the
    connector is off; ``UNKNOWN`` = not fetched yet."""

    OK = "ok"
    UNAVAILABLE = "unavailable"
    ERROR = "error"
    DISABLED = "disabled"
    UNKNOWN = "unknown"


class ConnectorHealth(str, Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


_STATUS_HEALTH: dict[ConnectorStatus, ConnectorHealth] = {
    ConnectorStatus.OK: ConnectorHealth.HEALTHY,
    ConnectorStatus.ERROR: ConnectorHealth.WARNING,
    ConnectorStatus.UNAVAILABLE: ConnectorHealth.UNAVAILABLE,
    ConnectorStatus.DISABLED: ConnectorHealth.UNKNOWN,
    ConnectorStatus.UNKNOWN: ConnectorHealth.UNKNOWN,
}


@dataclass(frozen=True)
class ConnectorResult:
    """The read-only outcome of one connector fetch. ``data`` is the observed evidence (empty unless
    ``OK``). Constructed through the classmethods so the no-fabrication invariants hold: only ``ok``
    carries data; ``unavailable`` and ``errored`` carry none."""

    status: ConnectorStatus
    data: Mapping[str, object] = field(default_factory=dict)
    latency_ms: float | None = None
    checked_at: float = 0.0
    detail: str = ""

    @property
    def ok(self) -> bool:
        return self.status is ConnectorStatus.OK

    @property
    def available(self) -> bool:
        """True when a real observation was made (OK). Anything else = no evidence to act on."""
        return self.status is ConnectorStatus.OK

    @property
    def health(self) -> ConnectorHealth:
        return _STATUS_HEALTH.get(self.status, ConnectorHealth.UNKNOWN)

    @classmethod
    def okay(
        cls, data: Mapping[str, object], *, latency_ms: float | None = None, detail: str = ""
    ) -> ConnectorResult:
        return cls(ConnectorStatus.OK, dict(data), latency_ms, 0.0, detail)

    @classmethod
    def unavailable(cls, detail: str) -> ConnectorResult:
        """The source could not be reached / is not configured. No evidence, no mission — safe."""
        return cls(ConnectorStatus.UNAVAILABLE, {}, None, 0.0, detail)

    @classmethod
    def disabled(cls) -> ConnectorResult:
        return cls(ConnectorStatus.DISABLED, {}, None, 0.0, "connector disabled")

    @classmethod
    def errored(cls, detail: str) -> ConnectorResult:
        return cls(ConnectorStatus.ERROR, {}, None, 0.0, detail)


@runtime_checkable
class Connector(Protocol):
    """A read-only observer of one external system. Declares its identity + owner and turns nothing
    into a ``ConnectorResult``. It must NEVER raise (the registry also guards) and never fabricate —
    an unreachable source is ``ConnectorResult.unavailable(...)``."""

    @property
    def id(self) -> str: ...

    @property
    def name(self) -> str: ...

    @property
    def type(self) -> ConnectorType: ...

    @property
    def owner(self) -> AgentRole: ...

    @property
    def enabled(self) -> bool: ...

    def fetch(self) -> ConnectorResult: ...


@dataclass
class ConnectorMetrics:
    """Per-connector counters the registry accumulates — never fabricated, just observed."""

    fetches: int = 0
    failures: int = 0
    cache_hits: int = 0
    total_latency_ms: float = 0.0

    @property
    def avg_latency_ms(self) -> float | None:
        timed = self.fetches - self.cache_hits
        return self.total_latency_ms / timed if timed > 0 else None

    def to_dict(self) -> dict[str, object]:
        return {
            "fetches": self.fetches,
            "failures": self.failures,
            "cache_hits": self.cache_hits,
            "avg_latency_ms": self.avg_latency_ms,
        }


@dataclass
class ConnectorState:
    """The live state of one connector — what the Dashboard's Connectors panel renders. Mutated only
    by the registry's fetch fold."""

    id: str
    name: str
    type: ConnectorType
    owner: AgentRole
    enabled: bool
    health: ConnectorHealth = ConnectorHealth.UNKNOWN
    status: ConnectorStatus = ConnectorStatus.UNKNOWN
    last_check: float | None = None
    latency_ms: float | None = None
    detail: str = ""
    metrics: ConnectorMetrics = field(default_factory=ConnectorMetrics)

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type.value,
            "owner": self.owner.value,
            "enabled": self.enabled,
            "health": self.health.value,
            "status": self.status.value,
            "last_check": self.last_check,
            "latency_ms": self.latency_ms,
            "detail": self.detail,
            "metrics": self.metrics.to_dict(),
        }


@dataclass(frozen=True)
class _CacheEntry:
    result: ConnectorResult
    expires_at: float


class ConnectorCache:
    """A per-connector TTL cache of the last fetch. Jobs reuse a fresh cached value, so a
    slow source is not hammered every tick. TTL is configurable (0 disables caching)."""

    def __init__(
        self, *, ttl_seconds: float = 60.0, clock: Callable[[], float] = time.time
    ) -> None:
        self._ttl = ttl_seconds
        self._clock = clock
        self._entries: dict[str, _CacheEntry] = {}

    def get(self, key: str) -> ConnectorResult | None:
        if self._ttl <= 0:
            return None
        entry = self._entries.get(key)
        if entry is None or self._clock() >= entry.expires_at:
            return None
        return entry.result

    def put(self, key: str, result: ConnectorResult) -> None:
        if self._ttl > 0:
            self._entries[key] = _CacheEntry(result, self._clock() + self._ttl)

    def clear(self) -> None:
        self._entries.clear()


class ConnectorRegistry:
    """The single place jobs fetch connectors. It owns caching, timing, metrics, health, and the
    fail-safe guard: even if a connector's ``fetch`` raised, ``fetch`` here returns an ``ERROR``
    result rather than propagating. Jobs call ``fetch(connector_id)``; never instantiate one
    a connector directly."""

    def __init__(
        self,
        *,
        cache: ConnectorCache | None = None,
        clock: Callable[[], float] = time.time,
        monotonic: Callable[[], float] = time.perf_counter,
    ) -> None:
        self._connectors: dict[str, Connector] = {}
        self._states: dict[str, ConnectorState] = {}
        self._cache = cache if cache is not None else ConnectorCache(clock=clock)
        self._clock = clock
        self._monotonic = monotonic

    def register(self, connector: Connector) -> None:
        self._connectors[connector.id] = connector
        self._states[connector.id] = ConnectorState(
            id=connector.id,
            name=connector.name,
            type=connector.type,
            owner=connector.owner,
            enabled=connector.enabled,
            status=ConnectorStatus.DISABLED if not connector.enabled else ConnectorStatus.UNKNOWN,
            health=ConnectorHealth.UNKNOWN,
        )

    def get(self, connector_id: str) -> Connector | None:
        return self._connectors.get(connector_id)

    def has(self, connector_id: str) -> bool:
        return connector_id in self._connectors

    def states(self) -> list[ConnectorState]:
        return list(self._states.values())

    def state(self, connector_id: str) -> ConnectorState | None:
        return self._states.get(connector_id)

    def fetch(self, connector_id: str, *, use_cache: bool = True) -> ConnectorResult:
        """Fetch through the registry: disabled → DISABLED; a fresh cache hit → the cached result; a
        real fetch is timed, guarded (an exception becomes an ERROR result), cached,
        and folded into the connector's live state + metrics."""
        connector = self._connectors.get(connector_id)
        if connector is None:
            return ConnectorResult.unavailable(f"no connector {connector_id!r}")
        state = self._states[connector_id]
        if not connector.enabled:
            return self._fold(state, ConnectorResult.disabled(), cache_hit=False)

        if use_cache:
            cached = self._cache.get(connector_id)
            if cached is not None:
                return self._fold(state, cached, cache_hit=True)

        started = self._monotonic()
        try:
            result = connector.fetch()
        except Exception as exc:  # a connector must never crash a job — the registry guards it
            result = ConnectorResult.errored(repr(exc))
        latency = (self._monotonic() - started) * 1000.0
        stamped = ConnectorResult(
            status=result.status,
            data=result.data,
            latency_ms=result.latency_ms if result.latency_ms is not None else latency,
            checked_at=self._clock(),
            detail=result.detail,
        )
        self._cache.put(connector_id, stamped)
        return self._fold(state, stamped, cache_hit=False)

    def _fold(
        self, state: ConnectorState, result: ConnectorResult, *, cache_hit: bool
    ) -> ConnectorResult:
        state.status = result.status
        state.health = result.health
        state.last_check = result.checked_at or self._clock()
        state.latency_ms = result.latency_ms
        state.detail = result.detail
        state.metrics.fetches += 1
        if cache_hit:
            state.metrics.cache_hits += 1
        else:
            if result.latency_ms is not None:
                state.metrics.total_latency_ms += result.latency_ms
            if result.status is ConnectorStatus.ERROR:
                state.metrics.failures += 1
        return result
