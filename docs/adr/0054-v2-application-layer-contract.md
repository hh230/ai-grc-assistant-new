# ADR 0054: The Application layer contract — policies, CQRS dependencies, and `CommandResult`

- Status: **Accepted — closed** (2026-07-22). The Application-layer *language* is frozen here; it
  changes only for a strong reason surfaced by a future Vertical Slice.
- Date: 2026-07-22
- Deciders: Product Owner (these shape dozens of future commands — reserved to the owner),
  Architecture
- Related: ADR 0052 (`grc-api` = Composition Root + HTTP adapter), ADR 0053 (read models &
  Application-layer projection), ADR 0042/0044 (the Mission Engine + human approval the commands
  drive), `mission-application` (this layer), `V1_EXECUTION_PLAN.md` (S2).

---

## Context

Slice S2 extracted the product **Application layer** (`mission-application`): `MissionDetailQuery`
made the HTTP route thin. The next step is the write side — approve / reject / retry. Before writing
them, three decisions must be settled, because they will govern **every** future command and query,
not just S2's three.

## Decision

### 1. The Application layer holds **policies**, not a facade

A command is **not** a one-line passthrough to the engine. The **Core** protects *domain* rules (an
aggregate rejects an illegal transition); the **Application** coordinates the *use case*. A command's
`execute` is responsible for, in order:

1. **Authorization** — is this *principal* allowed to run this command? (e.g. approve/reject require
   the **Approver** role — RBAC lives above the aggregate, ADR 0044 assumption 3.)
2. **Precondition** — surface an illegal use case as a typed error (the engine still enforces the
   domain rule as defence-in-depth).
3. **Drive the Core** — call the Mission Engine to perform the transition.
4. **Project on success** — update the read model via the projector (ADR 0053) so lists reflect the
   new status.
5. **Emit** — (later) an audit event / notification. Wired when needed, not pre-built.

If a command ever becomes just `engine.x()`, that is a smell — the policy belongs here.

### 2. CQRS separation is enforced by **dependencies**, not just folder names

- **Queries** (`queries/`) depend only on **read** ports: `MissionStore.get` and **read models**.
  A query never touches the Mission Engine.
- **Commands** (`commands/`) depend only on **write** collaborators: the **Mission Engine**, the
  **projector**, and (later) an **event publisher**. A command never *reads* a read model. (It
  *writes* a projection via the projector — that is the write side, not a read.)

This is real CQRS: the read and write sides cannot bleed into each other by construction.

### 3. Commands return a typed `CommandResult`; failures are typed Application errors

Every command's `execute(...)` returns a stable, framework-free result so REST, CLI, workers, and
tests consume the same thing without understanding the Core:

```python
@dataclass(frozen=True)
class CommandResult:
    mission_id: str
    status: str              # the mission's status AFTER the command (MissionStatus value)
    approval_pending: bool   # is a human gate now active?
```

**Failure is not a `success=False` flag** — it is a typed **Application error** the command raises,
which the HTTP host maps to a status code (and a CLI maps to an exit code):

- `NotAuthorized` → 403 · `MissionNotFound` → 404 (absent *or* cross-tenant, fail-closed) ·
  `IllegalCommand` → 409 (not valid in the current state).

So callers branch on success by *catching*, not by inspecting a boolean — and a `CommandResult` in
hand always means the command succeeded.

### 4. Every command/query takes a `CommandContext` — not loose parameters

Threading `tenant`, `principal`, `correlation_id`, … through 20 signatures means re-editing all 20
when the next cross-cutting concern appears. Instead, one ambient context is the first argument:

```python
@dataclass(frozen=True)
class CommandContext:
    tenant_id: str
    principal_id: str                   # explicit — a tenant is NOT a user (see below)
    roles: tuple[str, ...] = ()
    correlation_id: str = ""            # audit
    request_id: str = ""                # events
    clock: Callable[[], float] = _now   # injectable timestamps (testable)

ApproveMissionStepCommand().execute(context, mission_id, step_id)
```

**Identity is explicit, never derived from the tenant.** A tenant is not a user: Alice
(Practitioner), Bob (Approver), and Charlie (Admin) share tenant `acme` with different roles. If
`roles` were read off the tenant, the contract would break the day per-user roles matter — so
`principal_id`/`roles` are first-class now (even while the dev identity provider returns a fixed
principal). `context.tenant_context()` bridges to the Core's `TenantContext` for store/engine calls.
Locale/timezone/tracing join the context later **without changing a single service signature** — the
same reason `MissionDetailView` exists: freeze the boundary so churn stays out of the callers.

### 5. Commands depend on **abstract, generic collaborator ports**, not concrete classes

A command depends on **abstractions**, never on concrete lower-layer classes:

- a **generic `ProjectionPort[T]`**, never a concrete `MissionProjector` (tomorrow there may be
  Vendor, Knowledge, Dashboard, or Analytics projections; a command must know neither which nor how
  many);
- a **`MissionAccess`** to load (§7), never the raw store;
- a **`MissionWorkflow`** to drive transitions (approve/reject), never the raw `MissionEngine` — so
  audit, metrics, or a retry policy can wrap the engine later without touching a command. *(Retry is
  not a workflow op: with FAILED terminal in the Core, retry means "re-run = a new mission" — a
  create, landing with the create flow in Slice S7 — an S2 finding, owner-decided.)*

The concrete adapters are wired in the composition root.

### 6. The Application layer is **Use Cases only** — a hard boundary

`mission-application` orchestrates use cases; it does not touch any I/O or delivery mechanism. This is
obvious today, but with a larger team someone will eventually reach for SQL inside a command — this
rule in the ADR is what stops it.

- **Forbidden here:** SQL, HTTP, JWT, FastAPI, React/HTML, `pgvector`, `psycopg`, or any driver /
  framework / transport.
- **Belongs here:** orchestration, authorization, projections (via ports), policies, validation —
  the use cases themselves.

Persistence and transport live *outside*, behind the ports and adapters the layer depends on.

### 7. A command loads through a `MissionAccess` port, never the raw store

A command is not a repository. It reads the mission for a write through
`MissionAccess.load_for_update(tenant_id, mission_id)` — so locking, optimistic concurrency,
auditing, caching, or authorization hooks can be added behind that seam without changing a single
command (the same inversion as `ProjectionPort`).

### 8. Every mutating command is a Template Method (`MissionCommand`)

The use-case sequence is fixed once, in a base class, and never rewritten across the dozens of
commands to come (Approve, Reject, Retry, Cancel, Archive, Replan, Publish, …):

```python
class MissionCommand(ABC, Generic[Inputs]):
    def execute(self, context, mission_id, inputs) -> CommandResult:
        self.authorize(context, inputs)                       # hook
        mission = self._access.load_for_update(context.tenant_id, mission_id)  # None → MissionNotFound
        self.validate(context, mission, inputs)               # hook (optional)
        self.invoke(context, mission, inputs)                 # hook — drives the engine
        self._projection.project(mission)
        return CommandResult(mission.id, mission.status.value, mission.has_active_approval)
```

A concrete command fills only `authorize` / `validate` / `invoke`. The flow — load, project, build
the result, fail-closed on a missing mission — is written once.

### Layout: the shared language lives in `contracts/`

`mission-application` is `queries/` + `commands/` (with the `MissionCommand` base) + `views.py` +
**`contracts/`** — the last holding `CommandContext`, `CommandResult`, the error taxonomy, and the
collaborator `Port`s (`ProjectionPort`, `MissionAccess`, `MissionWorkflow`). Dozens of services will
come and go; the vocabulary in `contracts/` is what unifies them and changes rarely.

*Validation of the language:* the three S2 commands (`ApproveMissionStepCommand`,
`RejectMissionStepCommand`, `RetryMissionCommand`) were written on this contract **without changing
any of it** — each is ~30 lines of three hooks. That is the evidence the Application-layer language is
mature.

## Consequences

- **Positive.** The Application layer earns its place (policies, projection, audit seam); the HTTP
  host stays thin; read/write cannot entangle; every command/query has the same `execute(...) →
  result | typed error` shape, so adding the next one is mechanical.
- **Follow-ups.** The event-publisher dependency and audit emission are added when a use case needs
  them (not pre-built). A `status`-only projection update on the read model may be added so a command
  can re-project without reading type/scope (kept a write-side concern).
- **Freeze.** Additive; no Foundational Document contradicted, no Core change.
