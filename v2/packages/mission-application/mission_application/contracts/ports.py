"""The write-side collaborator ports commands depend on (ADR 0054, dependency-inverted).

A command depends on these **abstractions**, never a concrete class — so implementations swap and
multiply without changing a single command.

`ProjectionPort[T]` is the seam a command updates a read-side projection through **after** a subject
changes. It is **generic on purpose**: the contract is not tied to missions. The command calls
`project(subject)`; what the projection is (Mission List, Vendor, Knowledge, Dashboard, Analytics)
and how many exist behind it are invisible to the command. Concrete adapters are wired in the
composition root.
"""

from __future__ import annotations

from typing import Any, Protocol, TypeVar, runtime_checkable

from pipeline_contracts import TenantContext

T = TypeVar("T", contravariant=True)


@runtime_checkable
class ProjectionPort(Protocol[T]):
    """Update the read-side projection for a subject that just changed."""

    def project(self, subject: T) -> None: ...


@runtime_checkable
class MissionAccess(Protocol):
    """A command's read-for-write seam — it loads the mission through THIS, never the raw store.

    Behind it today: tenant-scoped loading (a missing or cross-tenant mission is `None`, fail-safe).
    Tomorrow: locking, optimistic concurrency, auditing, caching, or authorization hooks — added
    without changing a single command. Returns the Core `Mission` (typed `Any` — the Core ships no
    `py.typed`) or `None`.
    """

    def load_for_update(self, tenant_id: str, mission_id: str) -> Any | None: ...


@runtime_checkable
class MissionWorkflow(Protocol):
    """The write-operations seam over the Core (ADR 0044 transitions). A command drives a mission
    through THIS, never the raw `MissionEngine` — so audit, metrics, or a retry policy can wrap the
    engine later without changing a single command (the same inversion as `MissionAccess`).

    Each operation drives the transition on the given mission and persists it. `approver` is the
    acting tenant scope (the Core re-checks it, ADR 0040 §5). *(Retry is deliberately not here: with
    FAILED terminal in the Core, retry means "re-run = a new mission" — a create, not a transition —
    so it lands with the create flow in Slice S7, not as a `MissionWorkflow` op.)*
    """

    def approve_step(
        self, mission: Any, *, step_id: str, approver: TenantContext, comment: str = ""
    ) -> None: ...

    def reject_step(
        self, mission: Any, *, step_id: str, approver: TenantContext, comment: str = ""
    ) -> None: ...

    def start(self, mission: Any) -> None:
        """Begin the mission's execution (the product's **"Start mission"**; the Core op is
        `execute`). A write op over a loaded mission, so it lives here beside approve/reject — the
        `StartMissionCommand` drives it through the same `MissionCommand` template (Slice S7)."""
        ...


@runtime_checkable
class MissionDefinitionProvider(Protocol):
    """Turns the **product's** request — a Mission *type* + a *scope* — into the **Core's** mission
    *definition*: `(goal, plan)`. It is not "just a planner": a Mission type *is* a plan factory
    (ADR 0046 §4), and what it returns is the whole definition (the goal *and* the plan), the
    translation from product language to Core language. Behind it today: the bundled Mission
    Catalog; tomorrow an LLM planner or a per-tenant catalog, with no command change (Slice S7).
    Returns `(goal, Plan)` — `Plan` is the Core's, typed `Any` (the Core ships no `py.typed`)."""

    def define(self, mission_type: str, scope: str, tenant: TenantContext) -> tuple[str, Any]: ...


@runtime_checkable
class MissionCreator(Protocol):
    """Creates a new, planned mission from a definition — the first **create** behavior of the
    product (Slice S7). Composes the Core's `create` + `plan` behind one seam (as `EngineWorkflow`
    composes approve + resume), and is **idempotent**: a repeat with the same key returns the
    existing mission, never duplicated (ADR 0042 §12.7). Returns the Core `Mission` (`Any`)."""

    def create(
        self, goal: str, plan: Any, tenant: TenantContext, *, idempotency_key: str = ""
    ) -> Any: ...


@runtime_checkable
class DeliverableProvider(Protocol):
    """Builds the **base** Deliverable (sections · citations · confidence) from a completed
    mission — abstracted so a Result builder never calls `build_deliverable` directly. Caching,
    telemetry, flags, or a different builder version slot in behind this port with no change; and a
    Gap builder *enriches* this base (adds the gap matrix), not rebuilds the sections twice. Returns
    a `Deliverable` (typed `Any`)."""

    def build(self, mission: Any) -> Any: ...


@runtime_checkable
class FrameworkProvider(Protocol):
    """Supplies a framework (its controls) to a builder — abstracted so a builder never reaches for
    a concrete source. Today the adapter is the bundled library; tomorrow it may be a database, an
    external service, or a per-tenant catalog, and no builder changes. Returns a framework object
    with `.controls` (typed `Any` — the framework package's types are consumed loosely here)."""

    def get(self, framework_id: str) -> Any: ...
